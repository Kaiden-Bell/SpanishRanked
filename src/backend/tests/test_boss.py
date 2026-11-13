"""Boss battles gate rank-ups."""

import pytest
from fastapi.testclient import TestClient

from app import db, rules
from app.main import create_app

from conftest import BOOTSTRAP_PASSWORD, NEW_PASSWORD, set_owner_password, sign_in
from test_assessments import FakeGrammar, FakeModel, correct_answer, log_study, xp_events

WORDS = [["poder", "viajar", "comer", "vivir", "hablar"], ["tener", "salir", "volver", "la maleta", "dormir"]]


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


def give_xp(raw_db, amount):
    raw_db.execute("INSERT INTO xp_events (user_id, source_type, source_id, base_xp, multiplier, awarded_xp, local_date)"
                   " VALUES (1, 'STUDY_SESSION', 9999, ?, 1, ?, '2026-01-01')", (amount, amount))
    raw_db.commit()


def ready(api, raw_db):
    for terms in WORDS:
        log_study(api, terms=terms)
    give_xp(raw_db, rules.RANKS[1][0])


def fight(api, raw_db, model, win=True):
    started = api.post("/api/boss", json={"listening": True})
    assert started.status_code == 201, started.text
    quiz = started.json()["assessment"]
    if not win:
        model.outcomes = {t: "MISS" for i in quiz["items"] for t in i["concepts"]}
    body = quiz
    for item in quiz["items"]:
        text = correct_answer(raw_db, item) if win else "zzz"
        body = api.post(f"/api/assessments/{quiz['id']}/answers", json={"item_id": item["id"], "text": text}).json()
    return quiz, body


def test_no_boss_until_the_next_ranks_xp_is_reached(api, raw_db):
    assert api.get("/api/boss").json()["status"] == "NONE"
    assert api.post("/api/boss").status_code == 409
    log_study(api)
    give_xp(raw_db, rules.RANKS[1][0])
    b = api.get("/api/boss").json()
    assert b["rank"] == rules.RANKS[1][1] and b["status"] == "NEEDS_WORDS" and b["words_needed"] > 0


def test_reaching_the_xp_opens_the_boss_but_the_rank_waits(api, raw_db):
    ready(api, raw_db)
    p = api.get("/api/progress").json()
    assert p["rank"]["name"] == rules.RANKS[0][1]  # not promoted yet
    assert p["xp_to_next"] == 0 and p["boss"]["status"] == "READY" and p["boss"]["rank"] == rules.RANKS[1][1]


def test_a_boss_has_a_stage_per_skill_built_from_different_words(api, raw_db):
    ready(api, raw_db)
    quiz = api.post("/api/boss", json={"listening": True}).json()["assessment"]
    assert quiz["kind"] == "BOSS"
    stages = [i["stage"] for i in quiz["items"]]
    assert {"LISTENING", "GRAMMAR", "WRITING"} <= set(stages)
    write = [i for i in quiz["items"] if i["item_type"] == "WRITE"]
    assert len(write) == 1 and "Write one or two Spanish sentences" in write[0]["prompt"]
    # Resuming returns the same battle rather than a new one.
    again = api.post("/api/boss", json={"listening": True}).json()["assessment"]
    assert again["id"] == quiz["id"]


def test_without_a_spanish_voice_the_listening_stage_is_skipped_and_said_so(api, raw_db):
    ready(api, raw_db)
    r = api.post("/api/boss", json={"listening": False}).json()
    assert "LISTENING" not in {i["stage"] for i in r["assessment"]["items"]}
    skipped = raw_db.execute("SELECT stage_results_json FROM boss_attempts").fetchone()[0]
    assert "no Spanish voice" in skipped


def test_boss_needs_the_model_for_its_writing_stage(api, raw_db, model):
    ready(api, raw_db)
    model.state = "down"
    assert api.post("/api/boss").status_code == 503
    assert raw_db.execute("SELECT COUNT(*) FROM boss_attempts").fetchone()[0] == 0


def test_winning_grants_the_rank_and_pays_boss_xp(api, raw_db, model):
    ready(api, raw_db)
    quiz, body = fight(api, raw_db, model, win=True)
    assert body["status"] == "GRADED"
    p = api.get("/api/progress").json()
    assert p["rank"]["name"] == rules.RANKS[1][1] and p["boss"]["status"] == "NONE"
    assert xp_events(raw_db, "BOSS")[0]["base_xp"] == len(quiz["items"]) * rules.BOSS_XP_PER_CORRECT
    latest = api.get("/api/boss").json()["latest"]
    assert latest["status"] == "PASSED" and latest["rank"] == rules.RANKS[1][1] and latest["overall"] == 1


def test_losing_starts_a_cooldown_and_sends_missed_words_back_to_review(api, raw_db, model):
    ready(api, raw_db)
    quiz, _ = fight(api, raw_db, model, win=False)
    b = api.get("/api/boss").json()
    assert b["status"] == "COOLDOWN" and b["cooldown_until"]
    assert b["last_result"]["status"] == "FAILED" and not any(s["passed"] for s in b["last_result"]["stages"])
    assert api.get("/api/progress").json()["rank"]["name"] == rules.RANKS[0][1]
    assert api.post("/api/boss").status_code == 409
    now = db.utc_timestamp()
    for item in quiz["items"]:
        due = raw_db.execute("SELECT due_at FROM bank_entries WHERE id = ?", (item["entry_id"],)).fetchone()[0]
        assert due <= now
    # After the cooldown the boss can be fought again.
    raw_db.execute("UPDATE boss_attempts SET cooldown_until = '2000-01-01T00:00:00Z'")
    raw_db.commit()
    assert api.get("/api/boss").json()["status"] == "READY"


def test_ranks_reached_before_bosses_existed_are_kept(tmp_path):
    conn = db.connect(tmp_path / "g.db")
    for number, sql in enumerate(db.MIGRATIONS[:6], start=1):
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    conn.execute("INSERT INTO users (username, password_hash) VALUES ('owner', 'x')")
    conn.execute("INSERT INTO xp_events (user_id, source_type, source_id, base_xp, multiplier, awarded_xp, local_date)"
                 " VALUES (1, 'STUDY_SESSION', 1, 350, 1, 350, '2026-11-01')")
    conn.commit()
    db.migrate(conn)
    passes = {r[0]: r[1] for r in conn.execute("SELECT rank_name, grandfathered FROM boss_passes")}
    assert passes == {"Pre-Learner II": 1, "Pre-Learner III": 1}
    from app.practice.boss import held_rank_index

    assert rules.RANKS[held_rank_index(conn, 1, 350)][1] == "Pre-Learner III"
