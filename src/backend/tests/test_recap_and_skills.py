"""Daily recap, warm-up and the skill profile."""

import json

from fastapi.testclient import TestClient

from app import rules
from app.main import create_app

from conftest import BOOTSTRAP_PASSWORD, NEW_PASSWORD, set_owner_password, sign_in
from test_assessments import FakeGrammar, FakeModel, correct_answer, log_study, xp_events  # noqa: F401
import pytest


@pytest.fixture
def model():
    return FakeModel()


@pytest.fixture
def api(settings, model):
    with TestClient(create_app(settings, model=model, grammar=FakeGrammar())) as c:
        set_owner_password(settings, BOOTSTRAP_PASSWORD)
        sign_in(c, BOOTSTRAP_PASSWORD)
        c.post("/api/auth/change-password", json={"current_password": BOOTSTRAP_PASSWORD, "new_password": NEW_PASSWORD})
        yield c


def finish(api, raw_db, quiz, wrong=()):
    body = quiz
    for item in quiz["items"]:
        text = "zzz" if item["id"] in wrong else correct_answer(raw_db, item)
        body = api.post(f"/api/assessments/{quiz['id']}/answers", json={"item_id": item["id"], "text": text}).json()
    return body


# ---------------------------------------------------------------- recap


def test_recap_with_no_history_is_an_honest_empty_state(api):
    assert api.get("/api/recap").json() == {"empty": True, "warmup_done_today": False}


def test_recap_shows_last_sessions_words_and_what_is_due(api):
    log_study(api, context_text="Canción: Te extraño", terms=["extrañan", "te extrañan mucho", "poder"])
    r = api.get("/api/recap").json()
    assert not r["empty"] and r["sessions"][0]["context_text"] == "Canción: Te extraño"
    assert {e["headword"] for e in r["sessions"][0]["entries"]} == {"extrañar", "te extrañan mucho", "poder"}
    assert r["due_count"] >= 3 and r["weak"] == [] and r["warmup_done_today"] is False
    assert r["last_quiz"] is None


def test_a_learner_back_after_a_week_still_sees_their_material(api, raw_db):
    log_study(api)
    raw_db.execute("UPDATE study_sessions SET created_at = '2026-01-01T10:00:00Z'")
    raw_db.commit()
    r = api.get("/api/recap").json()
    assert len(r["sessions"]) == 1 and r["sessions"][0]["entries"]


def test_missed_words_show_up_as_weak_in_the_recap(api, raw_db):
    log_study(api)
    q = api.post("/api/assessments", json={"focus": "MIXED"}).json()
    missed = next(i for i in q["items"] if i["item_type"] != "WRITE")
    finish(api, raw_db, q, wrong={missed["id"]})
    r = api.get("/api/recap").json()
    assert missed["entry_id"] in [w["id"] for w in r["weak"]]
    assert r["last_quiz"]["total"] == len(q["items"]) and r["last_quiz"]["correct"] == len(q["items"]) - 1


def test_reading_the_recap_pays_nothing(api, raw_db):
    log_study(api)
    before = raw_db.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0]
    api.get("/api/recap")
    assert raw_db.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0] == before


# ---------------------------------------------------------------- warm-up


def test_warmup_is_code_checked_and_works_with_the_model_down(api, model, raw_db):
    log_study(api)
    model.state = "down"
    w = api.post("/api/warmups", json={"listening": True})
    assert w.status_code == 201
    w = w.json()
    assert w["kind"] == "WARMUP" and w["items"] and all(i["item_type"] != "WRITE" for i in w["items"])
    done = finish(api, raw_db, w)
    assert done["status"] == "GRADED"
    assert model.count("grade") == 0


def test_only_the_first_warmup_of_the_day_pays_but_every_one_counts(api, raw_db):
    log_study(api)
    first = finish(api, raw_db, api.post("/api/warmups").json())
    n = len(first["items"])
    assert first["award"]["base_xp"] == rules.WARMUP_COMPLETION_XP + n * rules.WARMUP_XP_PER_CORRECT
    second = finish(api, raw_db, api.post("/api/warmups").json())
    assert second["award"]["base_xp"] == 0 and second["award"]["awarded_xp"] == 0
    assert len(xp_events(raw_db, "WARMUP")) == 2  # both recorded: the streak counts them
    assert api.get("/api/recap").json()["warmup_done_today"] is True
    # Warm-up XP has its own cap and does not use up quiz XP.
    assert first["award"]["awarded_xp"] <= rules.DAILY_XP_CAP["WARMUP"]


def test_warmup_needs_material(api):
    assert api.post("/api/warmups").status_code == 409


# ---------------------------------------------------------------- skills


def test_skills_start_unassessed_and_speaking_always_is(api):
    s = api.get("/api/progress/skills").json()
    assert {k["key"]: k["status"] for k in s["skills"]} == {
        "READING": "NOT_ASSESSED", "LISTENING": "NOT_ASSESSED", "WRITING": "NOT_ASSESSED", "SPEAKING": "NOT_ASSESSED"}
    assert all(k["score"] is None for k in s["skills"])


def test_each_skill_is_scored_from_its_own_answers(api, raw_db):
    log_study(api, terms=["poder", "viajar", "comer", "vivir", "hablar"])
    for _ in range(12):
        reading = api.get("/api/progress/skills").json()["skills"][0]
        if reading["answers"] >= rules.QUIZ_ITEMS + 8:
            break
        q = api.post("/api/assessments", json={"focus": "READING", "listening": False}).json()
        finish(api, raw_db, q, wrong={q["items"][0]["id"]})
    s = api.get("/api/progress/skills").json()
    reading = next(k for k in s["skills"] if k["key"] == "READING")
    assert reading["status"] == "ASSESSED" and 0 < reading["score"] < 1
    listening = next(k for k in s["skills"] if k["key"] == "LISTENING")
    assert listening["status"] == "NOT_ASSESSED" and listening["answers"] == 0  # reading never counts as listening
    grammar = next(a for a in s["areas"] if a["key"] == "GRAMMAR")
    assert grammar["answers"] > 0
    assert all(w["correct"] < w["total"] for w in grammar["weakest"])


def test_answer_keys_record_the_tense_for_grammar_questions(api, raw_db):
    log_study(api)
    q = api.post("/api/assessments", json={"focus": "GRAMMAR"}).json()
    for item in q["items"]:
        key = json.loads(raw_db.execute("SELECT answer_json FROM assessment_items WHERE id = ?", (item["id"],)).fetchone()[0])
        if item["item_type"] in ("FORM_ID", "CONJUGATE"):
            assert key["tense"]
