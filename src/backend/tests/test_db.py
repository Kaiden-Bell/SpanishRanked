import sqlite3

import pytest

from app import db


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    db.migrate(connection)
    yield connection
    connection.close()


def add_user(conn, username="owner"):
    return conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, 'x')", (username,)
    ).lastrowid


def add_session(conn, user_id):
    return conn.execute(
        "INSERT INTO study_sessions (user_id, language_code, mode, activity_type, duration_minutes, context_text)"
        " VALUES (?, 'es', 'SELF_STUDY', 'reading', 20, 'notes')",
        (user_id,),
    ).lastrowid


def add_concept(conn, token="poder"):
    return conn.execute(
        "INSERT INTO concepts (language_code, token, category) VALUES ('es', ?, 'GRAMMAR')", (token,)
    ).lastrowid


def test_migrate_is_idempotent(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    assert db.migrate(connection) == len(db.MIGRATIONS)
    assert db.migrate(connection) == len(db.MIGRATIONS)
    connection.close()


def test_failed_migration_rolls_back_completely(tmp_path, monkeypatch):
    # Second statement fails, so the first must not survive either.
    broken = "CREATE TABLE half_done (id INTEGER); CREATE TABLE users (id INTEGER);"
    monkeypatch.setattr(db, "MIGRATIONS", [*db.MIGRATIONS, broken])
    connection = db.connect(tmp_path / "test.db")
    with pytest.raises(sqlite3.OperationalError):
        db.migrate(connection)
    assert db.schema_version(connection) == len(db.MIGRATIONS) - 1
    assert connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'half_done'").fetchone() is None
    assert not connection.in_transaction
    connection.close()


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        add_session(conn, user_id=999)


def test_new_user_must_change_password(conn):
    user_id = add_user(conn)
    row = conn.execute("SELECT must_change_password FROM users WHERE id = ?", (user_id,)).fetchone()
    assert row["must_change_password"] == 1


def test_study_session_rejects_unknown_mode_and_zero_duration(conn):
    user_id = add_user(conn)
    for mode, minutes in (("FREESTYLE", 20), ("SELF_STUDY", 0)):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO study_sessions (user_id, language_code, mode, activity_type, duration_minutes, context_text)"
                " VALUES (?, 'es', ?, 'reading', ?, 'notes')",
                (user_id, mode, minutes),
            )


def test_concept_is_unique_per_language_category_token(conn):
    add_concept(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_concept(conn)


def test_evidence_must_trace_to_a_session_or_item(conn):
    concept_id = add_concept(conn)
    insert = (
        "INSERT INTO concept_evidence (concept_id, study_session_id, assessment_item_id, modality,"
        " evidence_type, outcome, assistance_level) VALUES (?, ?, NULL, 'WRITING', 'EXPOSURE', 'NOT_ASSESSED', 'UNKNOWN')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, (concept_id, None))
    session_id = add_session(conn, add_user(conn))
    conn.execute(insert, (concept_id, session_id))


def test_evidence_rejects_unknown_outcome(conn):
    concept_id = add_concept(conn)
    session_id = add_session(conn, add_user(conn))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO concept_evidence (concept_id, study_session_id, modality, evidence_type, outcome,"
            " assistance_level) VALUES (?, ?, 'WRITING', 'ASSESSMENT', 'CORRECT', 'UNKNOWN')",
            (concept_id, session_id),
        )


def test_xp_cannot_be_awarded_twice_for_the_same_source(conn):
    user_id = add_user(conn)
    award = (
        "INSERT INTO xp_events (user_id, source_type, source_id, base_xp, multiplier, awarded_xp)"
        " VALUES (?, 'ASSESSMENT', 7, 10, 1.0, 10)"
    )
    conn.execute(award, (user_id,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(award, (user_id,))


def test_deleting_a_session_removes_its_terms_and_sentences(conn):
    session_id = add_session(conn, add_user(conn))
    conn.execute(
        "INSERT INTO study_terms (study_session_id, concept_id, original_text) VALUES (?, ?, 'poder')",
        (session_id, add_concept(conn)),
    )
    conn.execute("INSERT INTO study_sentences (study_session_id, sentence_text) VALUES (?, 'Puedo ir.')", (session_id,))
    conn.execute("DELETE FROM study_sessions WHERE id = ?", (session_id,))
    assert conn.execute("SELECT COUNT(*) FROM study_terms").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM study_sentences").fetchone()[0] == 0
