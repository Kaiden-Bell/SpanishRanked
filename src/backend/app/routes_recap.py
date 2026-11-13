"""Daily recap and warm-up (docs/ROADMAP.md Phase 3).

The recap is read-only: what you studied last time, what you got wrong, what is due. It pays no XP and
does not count for the streak. The warm-up is a short code-checked quiz built from due and weak
words; the first one of each day pays a little XP.
"""

import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from . import db, progression, rules, user_settings
from .deps import CurrentUser, get_db, ready_user
from .lexicon import bank
from .practice.compose import NotEnoughMaterial, compose
from .practice.context import short_gloss
from .routes_assessments import _load
from .schemas import AssessmentOut

router = APIRouter(prefix="/api", tags=["recap"])

RECAP_SESSIONS = 3
RECAP_WORDS = 8


class WarmupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    listening: bool = True


def _local_date(ts: str, tz) -> str:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(tz).date().isoformat()


def _entry_brief(conn, row) -> dict:
    s = bank.summary(conn, row)
    out = {k: s[k] for k in ("id", "kind", "headword", "translation", "strength")}
    if s["kind"] == "WORD":
        out["translation"] = short_gloss(s["translation"])  # a chip, not a dictionary entry
    return out


def recap(conn: sqlite3.Connection, user_id: int, now: datetime, tz) -> dict:
    today = now.astimezone(tz).date().isoformat()
    sessions = conn.execute(
        "SELECT id, created_at, activity_type, context_text FROM study_sessions WHERE user_id = ? ORDER BY id DESC LIMIT 50",
        (user_id,),
    ).fetchall()
    warmup_today = progression.xp_earned_count(conn, user_id, "WARMUP", now.astimezone(tz).date()) > 0
    if not sessions:
        return {"empty": True, "warmup_done_today": warmup_today}

    # "Last time" = the most recent day before today you studied, plus anything already logged today.
    # By sessions, not calendar days, so a learner back after a week away still sees their material.
    days = [_local_date(s["created_at"], tz) for s in sessions]
    previous = next((d for d in days if d < today), None)
    since = [s for s, d in zip(sessions, days) if d == today or d == previous]
    if len(since) < RECAP_SESSIONS:
        since = sessions[:RECAP_SESSIONS]  # newest first, so this still includes every session above
    out_sessions = []
    for s in since[:5]:
        terms = conn.execute(
            f"{bank.ENTRY_SELECT} WHERE e.user_id = ? AND e.id IN (SELECT b.bank_entry_id FROM bank_entry_concepts b"
            " JOIN study_terms st ON st.concept_id = b.concept_id WHERE st.study_session_id = ? AND b.role = 'TERM')",
            (user_id, s["id"]),
        ).fetchall()
        out_sessions.append({
            "id": s["id"], "created_at": s["created_at"], "local_date": _local_date(s["created_at"], tz),
            "activity_type": s["activity_type"], "context_text": s["context_text"],
            "entries": [_entry_brief(conn, r) for r in terms],
        })

    stamp = db.utc_timestamp(now)
    usable = "AND COALESCE(l.pos, '') != 'FUNCTION'"
    weak = conn.execute(
        f"{bank.ENTRY_SELECT} WHERE e.user_id = ? AND e.last_outcome IN ('MISS', 'PARTIAL') {usable}"
        " ORDER BY e.last_tested_at DESC LIMIT ?", (user_id, RECAP_WORDS)).fetchall()
    due = conn.execute(
        f"SELECT COUNT(*) FROM bank_entries e LEFT JOIN lexemes l ON l.id = e.lexeme_id"
        f" WHERE e.user_id = ? AND (e.due_at IS NULL OR e.due_at <= ?) {usable}", (user_id, stamp)).fetchone()[0]
    untested = conn.execute(
        f"SELECT COUNT(*) FROM bank_entries e LEFT JOIN lexemes l ON l.id = e.lexeme_id"
        f" WHERE e.user_id = ? AND e.hits + e.partials + e.misses = 0 {usable}", (user_id,)).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM bank_entries WHERE user_id = ?", (user_id,)).fetchone()[0]
    last = conn.execute(
        "SELECT id, kind, graded_at, (SELECT COUNT(*) FROM assessment_items i WHERE i.assessment_id = a.id) AS total"
        " FROM assessments a WHERE user_id = ? AND status = 'GRADED' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    last_quiz = None
    if last:
        correct = sum(
            1 for r in conn.execute("SELECT feedback_json FROM assessment_items WHERE assessment_id = ?", (last["id"],))
            if r["feedback_json"] and all(e["outcome"] == "HIT" for e in json.loads(r["feedback_json"])["evidence"])
        )
        last_quiz = {"id": last["id"], "kind": last["kind"], "graded_at": last["graded_at"],
                     "correct": correct, "total": last["total"]}
    streak = progression.progress(conn, user_id, now, tz)["streak"]
    return {
        "empty": False,
        "previous_day": previous,
        "sessions": out_sessions,
        "weak": [_entry_brief(conn, r) for r in weak],
        "due_count": due,
        "untested_count": untested,
        "bank_size": total,
        "last_quiz": last_quiz,
        "streak": streak,
        "warmup_done_today": warmup_today,
        "warmup_items": user_settings.load(conn, user_id).warmup_items,
    }


@router.get("/recap")
def get_recap(request: Request, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    return recap(conn, user.id, datetime.now(timezone.utc), request.app.state.settings.tz)


@router.post("/warmups", status_code=201, response_model=AssessmentOut)
def create_warmup(
    request: Request,
    body: WarmupIn | None = Body(None),
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
):
    """Always code-checked (no free sentences), so it works with the model down."""
    body = body or WarmupIn()
    try:
        prefs = user_settings.load(conn, user.id)
        assessment_id = compose(conn, request.app.state.verbs, user.id, kind="WARMUP", focus="MIXED",
                                listening=body.listening and prefs.listening, model_ok=False, n=prefs.warmup_items)
    except NotEnoughMaterial as exc:
        raise HTTPException(409, str(exc))
    return _load(conn, user.id, assessment_id)
