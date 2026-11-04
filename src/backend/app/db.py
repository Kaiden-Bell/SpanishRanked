"""

SQLite schema + migrations

Timestamps are UTC TEXT. Enum-like columns carry CHECK constraints in addition
to application validation. Foreign keys are enabled on every connection.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_TS_DEFAULT = "DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"

SCHEMA_V1 = f"""
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
    created_at TEXT NOT NULL {_TS_DEFAULT}
);

CREATE TABLE study_sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    language_code TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('SELF_STUDY', 'GUIDED_STUDY')),
    activity_type TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    context_text TEXT NOT NULL,
    created_at TEXT NOT NULL {_TS_DEFAULT},
    completed_at TEXT
);

CREATE TABLE concepts (
    id INTEGER PRIMARY KEY,
    language_code TEXT NOT NULL,
    token TEXT NOT NULL,
    category TEXT NOT NULL,
    UNIQUE (language_code, category, token)
);

CREATE TABLE study_terms (
    id INTEGER PRIMARY KEY,
    study_session_id INTEGER NOT NULL REFERENCES study_sessions(id) ON DELETE CASCADE,
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    original_text TEXT NOT NULL
);

CREATE TABLE study_sentences (
    id INTEGER PRIMARY KEY,
    study_session_id INTEGER NOT NULL REFERENCES study_sessions(id) ON DELETE CASCADE,
    sentence_text TEXT NOT NULL
);

CREATE TABLE assessments (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    language_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('GENERATED', 'SUBMITTED', 'GRADED', 'FAILED')),
    created_at TEXT NOT NULL {_TS_DEFAULT},
    submitted_at TEXT
);

CREATE TABLE assessment_items (
    id INTEGER PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    expected_criteria_json TEXT NOT NULL,
    response_text TEXT,
    feedback_json TEXT,
    checker_findings_json TEXT
);

CREATE TABLE concept_evidence (
    id INTEGER PRIMARY KEY,
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    study_session_id INTEGER REFERENCES study_sessions(id),
    assessment_item_id INTEGER REFERENCES assessment_items(id),
    modality TEXT NOT NULL CHECK (modality IN ('READING', 'WRITING', 'LISTENING', 'SPEAKING')),
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('EXPOSURE', 'PRACTICE', 'ASSESSMENT')),
    outcome TEXT NOT NULL CHECK (outcome IN ('HIT', 'PARTIAL', 'MISS', 'NOT_ASSESSED')),
    assistance_level TEXT NOT NULL CHECK (assistance_level IN ('ASSISTED', 'UNASSISTED', 'UNKNOWN')),
    response_time_ms INTEGER,
    created_at TEXT NOT NULL {_TS_DEFAULT},
    CHECK (study_session_id IS NOT NULL OR assessment_item_id IS NOT NULL)
);

CREATE TABLE xp_events (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    source_type TEXT NOT NULL CHECK (source_type IN ('STUDY_SESSION', 'ASSESSMENT')),
    source_id INTEGER NOT NULL,
    base_xp INTEGER NOT NULL CHECK (base_xp >= 0),
    multiplier REAL NOT NULL CHECK (multiplier >= 1),
    awarded_xp INTEGER NOT NULL CHECK (awarded_xp >= 0),
    created_at TEXT NOT NULL {_TS_DEFAULT},
    UNIQUE (user_id, source_type, source_id)
);
"""

SCHEMA_V2 = f"""
CREATE TABLE auth_sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL {_TS_DEFAULT},
    expires_at TEXT NOT NULL
);

CREATE INDEX idx_study_sessions_user ON study_sessions (user_id, id DESC);
"""

# The local calendar day an award counted toward (in the configured timezone at the time), so
# streaks and daily caps never shift if the timezone setting changes later. No XP was awarded
# before this migration, so the '' default only exists to satisfy NOT NULL.
SCHEMA_V3 = """
ALTER TABLE xp_events ADD COLUMN local_date TEXT NOT NULL DEFAULT '';
CREATE INDEX idx_xp_events_user_day ON xp_events (user_id, local_date);
"""

# Append new migrations; never edit one that has shipped. user_version is the count applied.
MIGRATIONS = [SCHEMA_V1, SCHEMA_V2, SCHEMA_V3]


def utc_timestamp(moment: datetime | None = None) -> str:
    """UTC timestamp in the same format as the column defaults (sorts lexicographically)."""
    return (moment or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: Path | str, *, check_same_thread: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]

def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations, each in its own transaction. Returns the schema version."""
    for number, sql in enumerate(MIGRATIONS[schema_version(conn):], start=schema_version(conn) + 1):
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
        except sqlite3.Error:
            conn.rollback()
            raise
    return schema_version(conn)
