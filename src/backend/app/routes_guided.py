"""Guided study (docs/GUIDED_STUDY.md): the syllabus with the learner's progress, unit lessons from
content packs, and unit quizzes. A lesson is logged through the ordinary study-session endpoint with
mode GUIDED_STUDY and its unit_id."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from . import user_settings
from .curriculum import packs as content
from .curriculum import progress, syllabus
from .deps import CurrentUser, get_db, get_model, ready_user
from .lexicon.grammar_terms import NON_FINITE, TENSES
from .practice.compose import NotEnoughMaterial, compose_unit
from .routes_assessments import _load as load_assessment
from .schemas import AssessmentOut

router = APIRouter(prefix="/api/guided", tags=["guided"])


def _tense_label(key: str) -> str:
    return TENSES[key]["label"] if key in TENSES else NON_FINITE.get(key, key)


def _unit_json(s: progress.UnitStatus, packset: content.PackSet) -> dict:
    u = s.unit
    return {
        "id": u.id, "n": u.n, "stage": u.stage, "title": u.title, "summary": u.summary, "confidence": u.confidence,
        "prereqs": list(u.prereqs), "tenses": [_tense_label(t) for t in u.tenses], "lemmas": list(u.lemmas),
        "status": s.status, "unlocked": s.unlocked, "lessons": s.lessons, "words_known": s.words_known,
        "answers": s.answers, "score": s.score, "has_lesson": bool(packset.covering(u.id)),
    }


@router.get("")
def overview(request: Request, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    syl = syllabus.load()
    packset: content.PackSet = request.app.state.packs
    statuses = progress.unit_statuses(conn, user.id, syl)
    pick = progress.suggest(statuses)
    return {
        "stages": list(syl.stages),
        "units": [_unit_json(s, packset) for s in statuses],
        "suggestion": {"unit_id": pick.status.unit.id, "reason": pick.reason} if pick else None,
        "packs": [{"id": p.id, "title": p.title, "bundled": p.bundled, "units": len(p.units)} for p in packset.packs],
    }


@router.get("/units/{unit_id}")
def unit_lesson(request: Request, unit_id: str, pack: str | None = Query(None, max_length=64),
                user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    syl = syllabus.load()
    if syl.get(unit_id) is None:
        raise HTTPException(404, "Unit not found.")
    packset: content.PackSet = request.app.state.packs
    status = next(s for s in progress.unit_statuses(conn, user.id, syl) if s.unit.id == unit_id)
    covering = packset.covering(unit_id)
    chosen = next((p for p in covering if p.id == pack), None) or (covering[0] if covering else None)
    lesson = None
    if chosen:
        m = chosen.manifest
        lesson = {
            "pack": {"id": chosen.id, "title": chosen.title, "attribution": chosen.attribution(),
                     "license": m["license"], "source_url": m.get("source_url")},
            "sections": [
                {"path": sec.path, "title": sec.title, "kind": sec.kind, "license": sec.license,
                 "source_url": sec.source_url, "extra_attribution": sec.extra_attribution, "markdown": sec.text()}
                for sec in content.lesson_sections(chosen, unit_id)
            ],
        }
    return {
        "unit": _unit_json(status, packset),
        "lesson": lesson,
        "other_packs": [{"id": p.id, "title": p.title} for p in covering if p is not chosen],
    }


@router.post("/units/{unit_id}/quiz", status_code=201, response_model=AssessmentOut)
def unit_quiz(request: Request, unit_id: str, user: CurrentUser = Depends(ready_user), conn=Depends(get_db),
              model=Depends(get_model)):
    unit = syllabus.load().get(unit_id)
    if unit is None:
        raise HTTPException(404, "Unit not found.")
    prefs = user_settings.load(conn, user.id)
    try:
        assessment_id = compose_unit(conn, request.app.state.verbs, user.id, unit, listening=prefs.listening,
                                     model_ok=model.status() == "ok", n=prefs.quiz_items)
    except NotEnoughMaterial as exc:
        raise HTTPException(409, str(exc))
    return load_assessment(conn, user.id, assessment_id)
