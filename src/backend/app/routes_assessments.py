import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from . import progression, user_settings
from .assessment import grade as grading
from .deps import CurrentUser, get_db, get_grammar, get_model, ready_user
from .practice import answer as answering
from .practice.compose import NeedsModel, NotEnoughMaterial, compose
from .schemas import (
    AnswerIn,
    AssessmentItemOut,
    AssessmentOut,
    AssessmentPage,
    AssessmentSummary,
    AwardOut,
    CreateAssessmentIn,
    EvidenceOut,
    SubmitIn,
)

_WORST = ("MISS", "PARTIAL", "HIT")

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


def _correct_count(items: list[AssessmentItemOut]) -> int:
    return sum(1 for i in items if i.evidence and all(e.outcome == "HIT" for e in i.evidence))


def _load(conn: sqlite3.Connection, user_id: int, assessment_id: int) -> AssessmentOut:
    row = conn.execute(
        "SELECT id, kind, focus, status, created_at, submitted_at, graded_at, grading_error FROM assessments"
        " WHERE id = ? AND user_id = ?",
        (assessment_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Quiz not found.")
    items, hints_missing = [], False
    for r in conn.execute("SELECT * FROM assessment_items WHERE assessment_id = ? ORDER BY id", (assessment_id,)):
        feedback = json.loads(r["feedback_json"]) if r["feedback_json"] else None
        if r["checker_findings_json"] and json.loads(r["checker_findings_json"]).get("status") != "ok":
            hints_missing = True
        evidence = [EvidenceOut(**e) for e in feedback["evidence"]] if feedback else []
        outcomes = {e.outcome for e in evidence}
        items.append(
            AssessmentItemOut(
                id=r["id"],
                prompt=r["prompt"],
                concepts=[c["token"] for c in json.loads(r["expected_criteria_json"])["concepts"]],
                response_text=r["response_text"],
                feedback=feedback["feedback"] if feedback else None,
                evidence=evidence,
                item_type=r["item_type"], modality=r["modality"], skill=r["skill"], stage=r["stage"],
                payload=json.loads(r["payload_json"] or "{}"),
                entry_id=r["bank_entry_id"],
                answer=feedback.get("answer") if feedback else None,
                outcome=next((o for o in _WORST if o in outcomes), None),
            )
        )
    graded = row["status"] == "GRADED"
    source = grading.xp_source(row["kind"])
    award = progression.existing_award(conn, user_id, source, assessment_id) if graded else None
    return AssessmentOut(
        id=row["id"],
        kind=row["kind"],
        focus=row["focus"],
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
    request: Request,
    body: CreateAssessmentIn | None = None,
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
    model=Depends(get_model),
):
    """Built from the word bank by code, instantly. The model is only asked whether it is up, to decide
    whether a free-sentence question can be included."""
    body = body or CreateAssessmentIn()
    prefs = user_settings.load(conn, user.id)
    try:
        assessment_id = compose(
            conn, request.app.state.verbs, user.id, focus=body.focus, listening=body.listening and prefs.listening,
            model_ok=model.status() == "ok", n=None if body.focus == "SENTENCES" else prefs.quiz_items,
        )
    except NotEnoughMaterial as exc:
        raise HTTPException(409, str(exc))
    except NeedsModel as exc:
        raise HTTPException(503, str(exc))
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
                id=a.id, kind=a.kind, status=a.status, created_at=a.created_at, graded_at=a.graded_at,
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


@router.post("/{assessment_id}/answers", response_model=AssessmentOut)
def answer_one(
    assessment_id: int,
    body: AnswerIn,
    request: Request,
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
    model=Depends(get_model),
    grammar=Depends(get_grammar),
):
    """Answer one question. Code-checked questions come back checked at once; after the last answer
    the quiz is submitted and graded (free sentences by the model)."""
    try:
        complete = answering.answer_item(
            conn, user.id, assessment_id, body.item_id, body.text, datetime.now(timezone.utc), grading.fingerprint
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except answering.Closed as exc:
        raise HTTPException(409, str(exc))
    if complete:
        return _grade(request, conn, user, assessment_id, model, grammar)
    return _load(conn, user.id, assessment_id)


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
