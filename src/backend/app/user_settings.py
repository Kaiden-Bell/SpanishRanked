"""Learner settings: what the Settings tab saves on the server.

Voice and speaking speed are not here: Spanish voices differ per device, so the browser keeps those.
"""

import json
import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import db, rules, themes


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiz_items: int = Field(rules.QUIZ_ITEMS, ge=3, le=10)
    warmup_items: int = Field(rules.WARMUP_ITEMS, ge=3, le=10)
    # Off: quizzes, warm-ups and boss battles ask no listening questions, on any device.
    listening: bool = True
    # 'system' follows the device's reduced-motion setting; 'reduce' always turns motion off.
    motion: Literal["system", "reduce"] = "system"
    # One of themes.THEMES, unlocked by rank. Checked against the held rank when saved and when read.
    theme: str = themes.DEFAULT


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiz_items: int | None = Field(None, ge=3, le=10)
    warmup_items: int | None = Field(None, ge=3, le=10)
    listening: bool | None = None
    motion: Literal["system", "reduce"] | None = None
    theme: str | None = Field(None, max_length=40)


class ThemeLocked(ValueError):
    pass


def held_index(conn: sqlite3.Connection, user_id: int) -> int:
    from .practice import boss  # late import: boss builds on the quiz modules

    return boss.held_rank_index(conn, user_id, 0)


def load(conn: sqlite3.Connection, user_id: int) -> Settings:
    row = conn.execute("SELECT settings_json FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    stored = json.loads(row["settings_json"]) if row else {}
    known = {k: v for k, v in stored.items() if k in Settings.model_fields}
    try:
        out = Settings(**known)
    except ValueError:
        out = Settings()  # a stored value went out of range after a rules change: fall back
    if out.theme != themes.DEFAULT and not themes.is_unlocked(out.theme, held_index(conn, user_id)):
        out = out.model_copy(update={"theme": themes.DEFAULT})  # e.g. after resetting all data
    return out


def save(conn: sqlite3.Connection, user_id: int, patch: SettingsPatch) -> Settings:
    """Raises ThemeLocked for a theme the learner's rank hasn't unlocked."""
    if patch.theme is not None and not themes.is_unlocked(patch.theme, held_index(conn, user_id)):
        raise ThemeLocked("That theme isn't unlocked yet." if patch.theme in themes.BY_ID else "Unknown theme.")
    merged = load(conn, user_id).model_copy(update=patch.model_dump(exclude_none=True))
    merged = Settings(**merged.model_dump())  # re-validate
    with conn:
        conn.execute(
            "INSERT INTO user_settings (user_id, settings_json, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT (user_id) DO UPDATE SET settings_json = excluded.settings_json, updated_at = excluded.updated_at",
            (user_id, merged.model_dump_json(), db.utc_timestamp()),
        )
    return merged


# Everything the learner made, in an order the foreign keys accept. Shared dictionary data (lexemes,
# example sentences, the lookup cache, verb tables) and the account itself are kept.
_RESET = [
    "DELETE FROM boss_passes WHERE user_id = :u",
    "DELETE FROM boss_attempts WHERE user_id = :u",
    "DELETE FROM concept_evidence WHERE assessment_item_id IN (SELECT i.id FROM assessment_items i"
    " JOIN assessments a ON a.id = i.assessment_id WHERE a.user_id = :u)"
    " OR study_session_id IN (SELECT id FROM study_sessions WHERE user_id = :u)",
    "DELETE FROM assessments WHERE user_id = :u",
    "DELETE FROM xp_events WHERE user_id = :u",
    "DELETE FROM bank_entries WHERE user_id = :u",
    "DELETE FROM study_sessions WHERE user_id = :u",
]


def reset_all(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    """Delete the learner's study history, word bank, quizzes, XP, ranks and streak. One transaction."""
    counts = {
        "study_sessions": conn.execute("SELECT COUNT(*) FROM study_sessions WHERE user_id = ?", (user_id,)).fetchone()[0],
        "words": conn.execute("SELECT COUNT(*) FROM bank_entries WHERE user_id = ?", (user_id,)).fetchone()[0],
        "quizzes": conn.execute("SELECT COUNT(*) FROM assessments WHERE user_id = ?", (user_id,)).fetchone()[0],
    }
    with conn:
        for sql in _RESET:
            conn.execute(sql, {"u": user_id})
    return counts
