import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from . import db, progression
from .deps import CurrentUser, get_db, ready_user
from .schemas import AwardOut, StudySessionCreated, StudySessionIn, StudySessionOut, StudySessionPage, normalize_token

router = APIRouter(prefix="/api/study-sessions", tags=["study-sessions"])

TERM_CATEGORY = "VOCABULARY"


def _hydrate(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[StudySessionOut]:
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    terms: dict[int, list[str]] = {i: [] for i in ids}
    sentences: dict[int, list[str]] = {i: [] for i in ids}
    if ids:
        for r in conn.execute(
            f"SELECT study_session_id, original_text FROM study_terms WHERE study_session_id IN ({marks}) ORDER BY id", ids
        ):
            terms[r["study_session_id"]].append(r["original_text"])
        for r in conn.execute(
            f"SELECT study_session_id, sentence_text FROM study_sentences WHERE study_session_id IN ({marks}) ORDER BY id", ids
        ):
            sentences[r["study_session_id"]].append(r["sentence_text"])
    return [
        StudySessionOut(**{k: r[k] for k in r.keys()}, terms=terms[r["id"]], sentences=sentences[r["id"]])
        for r in rows
    ]


_COLUMNS = (
    "id, language_code, mode, activity_type, duration_minutes, context_text, created_at, completed_at"
)


@router.post("", status_code=201, response_model=StudySessionCreated)
def create_study_session(
    body: StudySessionIn, request: Request, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)
):
    now = datetime.now(timezone.utc)
    # One transaction: the session, its terms/concepts, its sentences and its XP award are saved
    # together or not at all.
    with conn:
        session_id = conn.execute(
            "INSERT INTO study_sessions (user_id, language_code, mode, activity_type, duration_minutes,"
            " context_text, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user.id, body.language_code, body.mode, body.activity_type,
                body.duration_minutes, body.context_text, db.utc_timestamp(now),
            ),
        ).lastrowid
        for term in body.terms:
            conn.execute(
                "INSERT OR IGNORE INTO concepts (language_code, token, category) VALUES (?, ?, ?)",
                (body.language_code, normalize_token(term), TERM_CATEGORY),
            )
            concept_id = conn.execute(
                "SELECT id FROM concepts WHERE language_code = ? AND category = ? AND token = ?",
                (body.language_code, TERM_CATEGORY, normalize_token(term)),
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO study_terms (study_session_id, concept_id, original_text) VALUES (?, ?, ?)",
                (session_id, concept_id, term),
            )
        for sentence in body.sentences:
            conn.execute(
                "INSERT INTO study_sentences (study_session_id, sentence_text) VALUES (?, ?)",
                (session_id, sentence),
            )
        award = progression.award_xp(
            conn, user.id, "STUDY_SESSION", session_id,
            progression.session_base_xp(body.duration_minutes), now, request.app.state.settings.tz,
        )
    row = conn.execute(f"SELECT {_COLUMNS} FROM study_sessions WHERE id = ?", (session_id,)).fetchone()
    created = _hydrate(conn, [row])[0]
    return StudySessionCreated(**created.model_dump(), award=AwardOut(**vars(award)))


@router.get("", response_model=StudySessionPage)
def list_study_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
):
    """Newest first."""
    total = conn.execute("SELECT COUNT(*) FROM study_sessions WHERE user_id = ?", (user.id,)).fetchone()[0]
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM study_sessions WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
        (user.id, limit, offset),
    ).fetchall()
    return StudySessionPage(total=total, items=_hydrate(conn, rows))


@router.get("/{session_id}", response_model=StudySessionOut)
def get_study_session(session_id: int, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM study_sessions WHERE id = ? AND user_id = ?", (session_id, user.id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Study session not found.")
    return _hydrate(conn, [row])[0]
