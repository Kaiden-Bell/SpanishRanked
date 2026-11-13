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

# Assessment grading (Milestone D). `fingerprint` identifies identical questions + answers so a
# retake pays no extra XP; `grading_error` explains why a SUBMITTED attempt is still ungraded.
SCHEMA_V4 = """
ALTER TABLE assessments ADD COLUMN fingerprint TEXT;
ALTER TABLE assessments ADD COLUMN grading_error TEXT;
ALTER TABLE assessments ADD COLUMN graded_at TEXT;
CREATE INDEX idx_assessments_user ON assessments (user_id, id DESC);
"""

# Word bank (docs/ROADMAP.md Phase 1).
# - lexemes: one dictionary headword (an infinitive for verbs). Shared data, refined by online lookups;
#   an inflected headword that turns out to be a form of another (maletas -> maleta) redirects to it.
# - bank_entries: what the learner is learning, one row per word (lexeme) or phrase. Each entry owns a
#   concept, so practice evidence can be recorded against it; the SRS columns schedule its reviews.
# - bank_entry_concepts: which logged study terms refer to an entry. role TERM = typed as the term
#   itself, IN_PHRASE = a word inside a typed phrase.
# - bank_forms: the exact forms the learner has met and what each means grammatically.
SCHEMA_V5 = f"""
CREATE TABLE lexemes (
    id INTEGER PRIMARY KEY,
    language_code TEXT NOT NULL,
    lemma TEXT NOT NULL,
    pos TEXT,
    senses_json TEXT NOT NULL DEFAULT '[]',
    redirect_lexeme_id INTEGER REFERENCES lexemes(id),
    enrich_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (enrich_status IN ('pending', 'ok', 'not_found', 'unavailable', 'offline')),
    enriched_at TEXT,
    created_at TEXT NOT NULL {_TS_DEFAULT},
    UNIQUE (language_code, lemma)
);

CREATE TABLE bank_entries (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    kind TEXT NOT NULL CHECK (kind IN ('WORD', 'PHRASE')),
    lexeme_id INTEGER REFERENCES lexemes(id),
    phrase_text TEXT,
    auto_translation TEXT,
    translation_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (translation_status IN ('pending', 'ok', 'not_found', 'unavailable', 'offline')),
    user_translation TEXT,
    note TEXT,
    box INTEGER NOT NULL DEFAULT 0,
    due_at TEXT,
    last_tested_at TEXT,
    last_outcome TEXT CHECK (last_outcome IN ('HIT', 'PARTIAL', 'MISS')),
    hits INTEGER NOT NULL DEFAULT 0,
    partials INTEGER NOT NULL DEFAULT 0,
    misses INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL {_TS_DEFAULT},
    UNIQUE (user_id, concept_id),
    CHECK ((kind = 'WORD' AND lexeme_id IS NOT NULL) OR (kind = 'PHRASE' AND phrase_text IS NOT NULL))
);
CREATE INDEX idx_bank_entries_due ON bank_entries (user_id, due_at);

CREATE TABLE bank_entry_concepts (
    bank_entry_id INTEGER NOT NULL REFERENCES bank_entries(id) ON DELETE CASCADE,
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    role TEXT NOT NULL CHECK (role IN ('TERM', 'IN_PHRASE')),
    PRIMARY KEY (bank_entry_id, concept_id)
);
CREATE INDEX idx_bank_entry_concepts_concept ON bank_entry_concepts (concept_id);

CREATE TABLE bank_forms (
    bank_entry_id INTEGER NOT NULL REFERENCES bank_entries(id) ON DELETE CASCADE,
    form TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    first_seen_at TEXT NOT NULL {_TS_DEFAULT},
    PRIMARY KEY (bank_entry_id, form)
);

CREATE TABLE example_sentences (
    id INTEGER PRIMARY KEY,
    lexeme_id INTEGER NOT NULL REFERENCES lexemes(id) ON DELETE CASCADE,
    es_text TEXT NOT NULL,
    en_text TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('TATOEBA', 'WIKTIONARY')),
    source_ref TEXT,
    UNIQUE (lexeme_id, es_text)
);

CREATE TABLE lookup_cache (
    source TEXT NOT NULL,
    key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'missing', 'error')),
    body_json TEXT,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (source, key)
);
"""

# Question engine (docs/ROADMAP.md Phase 2). Items now have a type. Only WRITE items go to the model;
# every other type carries a server-only answer key (answer_json) and is checked by code. Rows that
# already exist are Level 1 writing items, hence the defaults.
# xp_events is rebuilt because SQLite can't change a CHECK in place: it now also allows the warm-up
# and boss-battle sources. Every row is copied unchanged.
SCHEMA_V6 = """
ALTER TABLE assessments ADD COLUMN kind TEXT NOT NULL DEFAULT 'QUICK' CHECK (kind IN ('QUICK', 'WARMUP', 'BOSS'));
ALTER TABLE assessments ADD COLUMN focus TEXT NOT NULL DEFAULT 'SENTENCES';
ALTER TABLE assessments ADD COLUMN boss_attempt_id INTEGER;

ALTER TABLE assessment_items ADD COLUMN item_type TEXT NOT NULL DEFAULT 'WRITE';
ALTER TABLE assessment_items ADD COLUMN modality TEXT NOT NULL DEFAULT 'WRITING'
    CHECK (modality IN ('READING', 'WRITING', 'LISTENING', 'SPEAKING'));
ALTER TABLE assessment_items ADD COLUMN skill TEXT NOT NULL DEFAULT 'WRITING';
ALTER TABLE assessment_items ADD COLUMN stage TEXT;
ALTER TABLE assessment_items ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE assessment_items ADD COLUMN answer_json TEXT;
ALTER TABLE assessment_items ADD COLUMN bank_entry_id INTEGER REFERENCES bank_entries(id) ON DELETE SET NULL;
ALTER TABLE assessment_items ADD COLUMN answered_at TEXT;

CREATE TABLE xp_events_v6 (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    source_type TEXT NOT NULL CHECK (source_type IN ('STUDY_SESSION', 'ASSESSMENT', 'WARMUP', 'BOSS')),
    source_id INTEGER NOT NULL,
    base_xp INTEGER NOT NULL CHECK (base_xp >= 0),
    multiplier REAL NOT NULL CHECK (multiplier >= 1),
    awarded_xp INTEGER NOT NULL CHECK (awarded_xp >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    local_date TEXT NOT NULL DEFAULT '',
    UNIQUE (user_id, source_type, source_id)
);
INSERT INTO xp_events_v6 (id, user_id, source_type, source_id, base_xp, multiplier, awarded_xp, created_at, local_date)
    SELECT id, user_id, source_type, source_id, base_xp, multiplier, awarded_xp, created_at, local_date FROM xp_events;
DROP TABLE xp_events;
ALTER TABLE xp_events_v6 RENAME TO xp_events;
CREATE INDEX idx_xp_events_user_day ON xp_events (user_id, local_date);
"""

# Boss battles (docs/ROADMAP.md Phase 5). A rank above the first is held only once its boss is passed.
# Ranks a learner already reached by XP when this migration runs are recorded as passed
# (grandfathered), so nobody loses a rank. The thresholds are written out here on purpose: they are
# the ones in force when bosses shipped, and later changes to rules.RANKS must not re-run this.
SCHEMA_V7 = f"""
CREATE TABLE boss_attempts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    rank_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('IN_PROGRESS', 'PASSED', 'FAILED')),
    assessment_id INTEGER REFERENCES assessments(id),
    stage_results_json TEXT,
    started_at TEXT NOT NULL {_TS_DEFAULT},
    finished_at TEXT,
    cooldown_until TEXT
);
CREATE INDEX idx_boss_attempts_user ON boss_attempts (user_id, id DESC);

CREATE TABLE boss_passes (
    user_id INTEGER NOT NULL REFERENCES users(id),
    rank_name TEXT NOT NULL,
    passed_at TEXT NOT NULL {_TS_DEFAULT},
    grandfathered INTEGER NOT NULL DEFAULT 0 CHECK (grandfathered IN (0, 1)),
    attempt_id INTEGER REFERENCES boss_attempts(id),
    PRIMARY KEY (user_id, rank_name)
);

INSERT INTO boss_passes (user_id, rank_name, grandfathered)
SELECT u.id, r.name, 1
FROM users u
JOIN (SELECT 120 AS min_xp, 'Pre-Learner II' AS name UNION ALL SELECT 300, 'Pre-Learner III'
      UNION ALL SELECT 550, 'Learner I' UNION ALL SELECT 900, 'Learner II' UNION ALL SELECT 1300, 'Learner III') r
WHERE (SELECT COALESCE(SUM(awarded_xp), 0) FROM xp_events e WHERE e.user_id = u.id) >= r.min_xp;
"""

# One-off maintenance jobs the app runs once at startup, then deletes. The first: re-read every logged
# term now that "phrase: ... - English meaning" style input is parsed (lexicon/parse.py).
SCHEMA_V8 = """
CREATE TABLE pending_jobs (name TEXT PRIMARY KEY);
INSERT INTO pending_jobs (name) VALUES ('reparse_word_bank');
"""

# Learner settings (Settings tab). One JSON document per user; user_settings.py owns the keys and
# their defaults, so adding a setting needs no migration.
SCHEMA_V9 = f"""
CREATE TABLE user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    settings_json TEXT NOT NULL DEFAULT '{{}}',
    updated_at TEXT NOT NULL {_TS_DEFAULT}
);
"""

# Append new migrations; never edit one that has shipped. user_version is the count applied.
MIGRATIONS = [SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5, SCHEMA_V6, SCHEMA_V7, SCHEMA_V8, SCHEMA_V9]


def utc_timestamp(moment: datetime | None = None) -> str:
    """UTC timestamp in the same format as the column defaults (sorts lexicographically)."""
    return (moment or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: Path | str, *, check_same_thread: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Word lookups write from a background thread; wait briefly for a lock instead of failing.
    conn.execute("PRAGMA busy_timeout = 5000")
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
