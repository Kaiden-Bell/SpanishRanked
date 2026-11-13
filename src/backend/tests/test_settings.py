"""Settings tab: practice preferences, motion, account actions, reset."""

import pytest
from fastapi.testclient import TestClient

from app import rules
from app.main import create_app

from conftest import NEW_PASSWORD, sign_in
from test_assessments import FakeGrammar, FakeModel, correct_answer, log_study
from test_recap_and_skills import api, finish, model  # noqa: F401  (fixtures)

LISTENING = {"LISTEN_PICK", "DICTATION"}


def test_defaults_and_validation(api):
    s = api.get("/api/settings").json()
    assert s == {"quiz_items": rules.QUIZ_ITEMS, "warmup_items": rules.WARMUP_ITEMS, "listening": True, "motion": "system"}
    assert api.patch("/api/settings", json={"quiz_items": 2}).status_code == 422
    assert api.patch("/api/settings", json={"quiz_items": 11}).status_code == 422
    assert api.patch("/api/settings", json={"theme": "light"}).status_code == 422
    assert api.patch("/api/settings", json={"motion": "reduce"}).json()["motion"] == "reduce"
    assert api.get("/api/settings").json()["motion"] == "reduce"  # saved, other keys untouched
    assert api.get("/api/settings").json()["quiz_items"] == rules.QUIZ_ITEMS


def test_quiz_and_warmup_lengths_follow_the_settings(api, raw_db):
    log_study(api, terms=["poder", "viajar", "comer", "vivir", "hablar"])
    log_study(api, terms=["tener", "salir", "volver", "dormir", "pensar"])
    api.patch("/api/settings", json={"quiz_items": 8, "warmup_items": 3})
    assert len(api.post("/api/assessments", json={"focus": "MIXED"}).json()["items"]) == 8
    assert len(api.post("/api/assessments", json={"focus": "SENTENCES"}).json()["items"]) == rules.SENTENCE_QUIZ_ITEMS
    assert api.get("/api/recap").json()["warmup_items"] == 3
    assert len(api.post("/api/warmups").json()["items"]) == 3


def test_listening_off_applies_even_when_the_device_has_a_voice(api):
    log_study(api, terms=["poder", "viajar", "comer", "vivir", "hablar"])
    api.patch("/api/settings", json={"listening": False})
    for _ in range(6):
        q = api.post("/api/assessments", json={"focus": "MIXED", "listening": True}).json()
        assert not LISTENING & {i["item_type"] for i in q["items"]}
        w = api.post("/api/warmups", json={"listening": True}).json()
        assert not LISTENING & {i["item_type"] for i in w["items"]}


def test_sign_out_other_devices_keeps_this_one(api, settings):
    with TestClient(create_app(settings, model=FakeModel(), grammar=FakeGrammar())) as other:
        sign_in(other, NEW_PASSWORD)
        assert other.get("/api/progress").status_code == 200
        assert api.post("/api/settings/sign-out-others").json() == {"signed_out": 1}
        assert other.get("/api/progress").status_code == 401
    assert api.get("/api/progress").status_code == 200


def test_reset_needs_the_password_and_the_word_reset(api, raw_db):
    log_study(api)
    assert api.post("/api/settings/reset", json={"password": NEW_PASSWORD, "confirm": "reset me"}).status_code == 400
    assert api.post("/api/settings/reset", json={"password": "wrong-password!", "confirm": "RESET"}).status_code == 400
    assert raw_db.execute("SELECT COUNT(*) FROM study_sessions").fetchone()[0] == 1


def test_reset_starts_over_but_keeps_the_account_settings_and_dictionary(api, raw_db):
    log_study(api, terms=["poder", "viajar", "comer", "vivir", "hablar"])
    finish(api, raw_db, api.post("/api/assessments", json={"focus": "MIXED"}).json())
    api.patch("/api/settings", json={"quiz_items": 6})
    lexemes = raw_db.execute("SELECT COUNT(*) FROM lexemes").fetchone()[0]
    r = api.post("/api/settings/reset", json={"password": NEW_PASSWORD, "confirm": "RESET"})
    assert r.status_code == 200 and r.json()["deleted"]["study_sessions"] == 1
    for table in ("study_sessions", "study_terms", "assessments", "assessment_items", "concept_evidence",
                  "xp_events", "bank_entries", "bank_forms", "boss_attempts", "boss_passes"):
        assert raw_db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    p = api.get("/api/progress").json()
    assert p["total_xp"] == 0 and p["streak"]["current"] == 0 and p["rank"]["name"] == rules.RANKS[0][1]
    assert api.get("/api/recap").json()["empty"] is True
    assert api.get("/api/settings").json()["quiz_items"] == 6
    assert raw_db.execute("SELECT COUNT(*) FROM lexemes").fetchone()[0] == lexemes  # shared dictionary data stays
    log_study(api)  # and the learner can start again straight away


@pytest.mark.parametrize("path", ["/api/settings", "/api/settings/sign-out-others", "/api/settings/reset"])
def test_settings_need_a_signed_in_user(client, path):
    call = client.get if path == "/api/settings" else client.post
    assert call(path).status_code in (401, 403)
