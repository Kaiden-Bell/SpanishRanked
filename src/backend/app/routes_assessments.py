import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from . import progression
from .assessment import grade as grading
from .assessment.generate import NotEnoughMaterial, QuizGenerationError, generate_quiz
from .clients.model import ModelUnavailable
from .deps import CurrentUser, get_db, get_grammar, get_model, ready_user
from .schemas import (
    AssessmentItemOut,
    AssessmentOut,
    AssessmentPage,
    AssessmentSummary,
    AwardOut,
    EvidenceOut,
    SubmitIn,
)

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


def _correct_count(items: list[AssessmentItemOut]) -> int:
    return sum(1 for i in items if i.evidence and all(e.outcome == "HIT" for e in i.evidence))


def _load(conn: sqlite3.Connection, user_id: int, assessment_id: int) -> AssessmentOut:
    row = conn.execute(
        "SELECT id, status, created_at, submitted_at, graded_at, grading_error FROM assessments"
        " WHERE id = ? AND user_id = ?",
        (assessment_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Quiz not found.")
    items, hints_missing = [], False
    for r in conn.execute(
        "SELECT id, prompt, expected_criteria_json, response_text, feedback_json, checker_findings_json"
        " FROM assessment_items WHERE assessment_id = ? ORDER BY id",
        (assessment_id,),
    ):
        feedback = json.loads(r["feedback_json"]) if r["feedback_json"] else None
        if r["checker_findings_json"] and json.loads(r["checker_findings_json"]).get("status") != "ok":
            hints_missing = True
        items.append(
            AssessmentItemOut(
                id=r["id"],
                prompt=r["prompt"],
                concepts=[c["token"] for c in json.loads(r["expected_criteria_json"])["concepts"]],
                response_text=r["response_text"],
                feedback=feedback["feedback"] if feedback else None,
                evidence=[EvidenceOut(**e) for e in feedback["evidence"]] if feedback else [],
            )
        )
    graded = row["status"] == "GRADED"
    award = progression.existing_award(conn, user_id, "ASSESSMENT", assessment_id) if graded else None
    return AssessmentOut(
        id=row["id"],
        status=row["status"],
        created_at=row["created_at"],
        submitted_at=row["submitted_at"],
        graded_at=row["graded_at"],
        grading_error=row["grading_error"] if row["status"] == "SUBMITTED" else None,
        grammar_hints_unavailable=hints_missing,
        correct=_correct_count(items) if graded else None,
        items=items,
        award=AwardOut(**vars(award)) if award else None,
    )


@router.post("", status_code=201, response_model=AssessmentOut)
def create_assessment(
    user: CurrentUser = Depends(ready_user), conn=Depends(get_db), model=Depends(get_model)
):
    try:
        assessment_id = generate_quiz(conn, user.id, model)
    except NotEnoughMaterial as exc:
        raise HTTPException(409, str(exc))
    except ModelUnavailable:
        raise HTTPException(503, "Quizzes are unavailable right now. You can still log study sessions.")
    except QuizGenerationError:
        raise HTTPException(502, "The model did not produce a usable quiz. Please try again.")
    return _load(conn, user.id, assessment_id)


@router.get("", response_model=AssessmentPage)
def list_assessments(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
):
    """Newest first. Quizzes that were generated but never submitted are left out."""
    total = conn.execute(
        "SELECT COUNT(*) FROM assessments WHERE user_id = ? AND status != 'GENERATED'", (user.id,)
    ).fetchone()[0]
    ids = [
        r[0]
        for r in conn.execute(
            "SELECT id FROM assessments WHERE user_id = ? AND status != 'GENERATED' ORDER BY id DESC LIMIT ? OFFSET ?",
            (user.id, limit, offset),
        )
    ]
    summaries = []
    for assessment_id in ids:
        a = _load(conn, user.id, assessment_id)
        summaries.append(
            AssessmentSummary(
                id=a.id, status=a.status, created_at=a.created_at, graded_at=a.graded_at,
                correct=a.correct, total=len(a.items),
            )
        )
    return AssessmentPage(total=total, items=summaries)


@router.get("/{assessment_id}", response_model=AssessmentOut)
def get_assessment(assessment_id: int, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    return _load(conn, user.id, assessment_id)


def _grade(request: Request, conn, user: CurrentUser, assessment_id: int, model, grammar) -> AssessmentOut:
    try:
        grading.grade_assessment(
            conn, user.id, assessment_id, model, grammar,
            request.app.state.settings.tz, datetime.now(timezone.utc),
        )
    except grading.WrongState as exc:
        raise HTTPException(409, str(exc))
    # Grading may have failed. That is not an HTTP error: the answers are saved and the response
    # reports "SUBMITTED" with a grading_error so the client can offer a retry.
    return _load(conn, user.id, assessment_id)


@router.post("/{assessment_id}/submit", response_model=AssessmentOut)
def submit_assessment(
    assessment_id: int,
    body: SubmitIn,
    request: Request,
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
    model=Depends(get_model),
    grammar=Depends(get_grammar),
):
    _load(conn, user.id, assessment_id)  # 404 for someone else's quiz
    answers = {a.item_id: a.text for a in body.answers}
    if len(answers) != len(body.answers):
        raise HTTPException(422, "Answer each question once.")
    try:
        grading.save_answers(conn, user.id, assessment_id, answers, datetime.now(timezone.utc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except grading.WrongState as exc:
        raise HTTPException(409, str(exc))
    return _grade(request, conn, user, assessment_id, model, grammar)


@router.post("/{assessment_id}/grade", response_model=AssessmentOut)
def retry_grading(
    assessment_id: int,
    request: Request,
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
    model=Depends(get_model),
    grammar=Depends(get_grammar),
):
    _load(conn, user.id, assessment_id)
    return _grade(request, conn, user, assessment_id, model, grammar)
