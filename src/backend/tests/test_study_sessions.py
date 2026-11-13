import copy

import pytest
from fastapi.testclient import TestClient

from app import routes_sessions
from app.main import create_app

VALID = {
    "mode": "SELF_STUDY",
    "activity_type": "READING",
    "duration_minutes": 25,
    "context_text": "Leí un artículo sobre viajes.",
    "terms": ["poder", "viajar", "la maleta"],
    "sentences": ["Puedo viajar mañana.", "Necesito la maleta."],
}


def payload(**overrides):
    body = copy.deepcopy(VALID)
    body.update(overrides)
    return body


def test_valid_session_is_saved_and_returned(authed, raw_db):
    r = authed.post("/api/study-sessions", json=payload(mode="GUIDED_STUDY"))
    assert r.status_code == 201
    body = r.json()
    assert body["mode"] == "GUIDED_STUDY" and body["language_code"] == "es"
    assert body["terms"] == VALID["terms"] and body["sentences"] == VALID["sentences"]
    assert body["completed_at"] and body["created_at"]
    assert body.pop("award")
    assert authed.get(f"/api/study-sessions/{body['id']}").json() == body
    assert raw_db.execute("SELECT COUNT(*) FROM study_terms").fetchone()[0] == 3


def test_original_text_is_preserved_and_concepts_are_shared(authed, raw_db):
    authed.post("/api/study-sessions", json=payload(terms=["  Poder ", "viajar", "la maleta"]))
    authed.post("/api/study-sessions", json=payload(terms=["PODER", "comer", "el  tren"]))
    originals = [r[0] for r in raw_db.execute("SELECT original_text FROM study_terms ORDER BY id")]
    assert originals[0] == "Poder" and originals[3] == "PODER"  # as typed (trimmed), not normalised
    tokens = [r[0] for r in raw_db.execute("SELECT token FROM concepts WHERE category = 'VOCABULARY' ORDER BY id")]
    assert tokens.count("poder") == 1
    assert "el tren" in tokens  # inner whitespace collapsed
    assert len(tokens) == 5


INVALID = {
    "too few terms": {"terms": ["a", "b"]},
    "too many terms": {"terms": list("abcdef")},
    "too few sentences": {"sentences": ["Uno."]},
    "too many sentences": {"sentences": ["Uno.", "Dos.", "Tres.", "Cuatro."]},
    "blank term": {"terms": ["poder", "   ", "viajar"]},
    "duplicate terms": {"terms": ["Poder", "poder", "viajar"]},
    "overlong term": {"terms": ["x" * 201, "b", "c"]},
    "overlong sentence": {"sentences": ["x" * 301, "ok."]},
    "empty context": {"context_text": "   "},
    "overlong context": {"context_text": "x" * 2001},
    "zero duration": {"duration_minutes": 0},
    "over a day": {"duration_minutes": 1441},
    "string duration": {"duration_minutes": "25"},
    "boolean duration": {"duration_minutes": True},
    "unknown mode": {"mode": "FREESTYLE"},
    "unknown activity": {"activity_type": "SLEEPING"},
    "unsupported language": {"language_code": "fr"},
    "control character": {"context_text": "hola\x00mundo"},
    "unexpected field": {"user_id": 99},
}


@pytest.mark.parametrize("overrides", INVALID.values(), ids=INVALID.keys())
def test_invalid_input_is_rejected_and_nothing_is_saved(authed, raw_db, overrides):
    assert authed.post("/api/study-sessions", json=payload(**overrides)).status_code == 422
    for table in ("study_sessions", "study_terms", "study_sentences", "concepts"):
        assert raw_db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert raw_db.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0] == 0


def test_missing_fields_are_rejected(authed):
    body = payload()
    del body["terms"]
    assert authed.post("/api/study-sessions", json=body).status_code == 422


def test_a_failure_midway_saves_nothing(settings, authed, raw_db, monkeypatch):
    calls = []

    def boom(text):
        calls.append(text)
        if len(calls) == 2:
            raise RuntimeError("disk on fire")
        return text.lower()

    monkeypatch.setattr(routes_sessions, "normalize_token", boom)
    with TestClient(authed.app, raise_server_exceptions=False, cookies=authed.cookies,
                    headers={"X-CSRF-Token": authed.headers["X-CSRF-Token"]}) as c:
        assert c.post("/api/study-sessions", json=payload()).status_code == 500
    assert raw_db.execute("SELECT COUNT(*) FROM study_sessions").fetchone()[0] == 0
    assert raw_db.execute("SELECT COUNT(*) FROM concepts").fetchone()[0] == 0
    assert raw_db.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0] == 0


def test_history_is_newest_first_with_stored_inputs(authed):
    for n in (1, 2, 3):
        authed.post("/api/study-sessions", json=payload(context_text=f"entry {n}"))
    page = authed.get("/api/study-sessions").json()
    assert page["total"] == 3
    assert [i["context_text"] for i in page["items"]] == ["entry 3", "entry 2", "entry 1"]
    assert page["items"][0]["terms"] == VALID["terms"]


def test_history_pagination(authed):
    for n in range(5):
        authed.post("/api/study-sessions", json=payload(context_text=f"entry {n}"))
    first = authed.get("/api/study-sessions", params={"limit": 2}).json()
    second = authed.get("/api/study-sessions", params={"limit": 2, "offset": 2}).json()
    assert first["total"] == second["total"] == 5
    assert [i["context_text"] for i in first["items"] + second["items"]] == [f"entry {n}" for n in (4, 3, 2, 1)]
    assert authed.get("/api/study-sessions", params={"limit": 0}).status_code == 422
    assert authed.get("/api/study-sessions", params={"limit": 101}).status_code == 422


def test_empty_history(authed):
    assert authed.get("/api/study-sessions").json() == {"total": 0, "items": []}


def test_unknown_session_is_404_and_other_users_sessions_are_hidden(authed, raw_db):
    assert authed.get("/api/study-sessions/999").status_code == 404
    with raw_db:
        other = raw_db.execute("INSERT INTO users (username, password_hash) VALUES ('other', 'x')").lastrowid
        sid = raw_db.execute(
            "INSERT INTO study_sessions (user_id, language_code, mode, activity_type, duration_minutes, context_text)"
            " VALUES (?, 'es', 'SELF_STUDY', 'reading', 5, 'private')", (other,)
        ).lastrowid
    assert authed.get(f"/api/study-sessions/{sid}").status_code == 404
    assert authed.get("/api/study-sessions").json()["total"] == 0


def test_creating_requires_csrf_token(authed):
    del authed.headers["X-CSRF-Token"]
    assert authed.post("/api/study-sessions", json=payload()).status_code == 403
