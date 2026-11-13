"""Deleting a study session from History."""

from app import rules

from test_assessments import log_study
from test_boss import fight, ready  # noqa: F401
from test_recap_and_skills import api, finish, model  # noqa: F401  (fixtures)


def heads(api):
    return {i["headword"] for i in api.get("/api/bank", params={"limit": 200}).json()["items"]} | {
        i["headword"] for i in api.get("/api/bank", params={"limit": 200, "kind": "PHRASE"}).json()["items"]}


def test_delete_removes_the_session_its_xp_and_the_words_only_it_added(api, raw_db):
    keep = log_study(api, terms=["poder", "viajar", "comer"])
    gone = log_study(api, terms=["poder", "te extrañan mucho", "dormir"], sentences=["Uno.", "Dos."])
    before = api.get("/api/progress").json()["total_xp"]
    r = api.delete(f"/api/study-sessions/{gone['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["xp_removed"] == gone["award"]["awarded_xp"] > 0
    assert api.get("/api/progress").json()["total_xp"] == before - body["xp_removed"]
    assert api.get(f"/api/study-sessions/{gone['id']}").status_code == 404
    assert api.get("/api/study-sessions").json()["total"] == 1
    for table in ("study_terms", "study_sentences"):
        assert raw_db.execute(f"SELECT COUNT(*) FROM {table} WHERE study_session_id = ?", (gone["id"],)).fetchone()[0] == 0
    words = heads(api)
    assert {"poder", "viajar", "comer"} <= words  # poder was also logged in the session that stays
    assert not words & {"dormir", "extrañar", "mucho", "te extrañan mucho"}
    assert body["entries_removed"] == 4
    assert keep["id"] in [s["id"] for s in api.get("/api/study-sessions").json()["items"]]


def test_quiz_history_stays_after_a_delete(api, raw_db):
    s = log_study(api, terms=["poder", "viajar", "comer", "vivir", "hablar"])
    quiz = finish(api, raw_db, api.post("/api/assessments", json={"focus": "MIXED"}).json())
    quiz_xp = quiz["award"]["awarded_xp"]
    evidence = raw_db.execute("SELECT COUNT(*) FROM concept_evidence").fetchone()[0]
    api.delete(f"/api/study-sessions/{s['id']}")
    assert api.get("/api/progress").json()["total_xp"] == quiz_xp  # the quiz's XP was earned by answering
    assert raw_db.execute("SELECT COUNT(*) FROM concept_evidence").fetchone()[0] == evidence
    assert api.get(f"/api/assessments/{quiz['id']}").json()["status"] == "GRADED"


def test_delete_and_relog_does_not_earn_twice(api):
    first = log_study(api)
    api.delete(f"/api/study-sessions/{first['id']}")
    second = log_study(api)
    assert api.get("/api/progress").json()["total_xp"] == second["award"]["awarded_xp"]


def test_the_streak_follows_the_remaining_activity(api):
    s = log_study(api)
    assert api.get("/api/progress").json()["streak"]["active_today"] is True
    api.delete(f"/api/study-sessions/{s['id']}")
    streak = api.get("/api/progress").json()["streak"]
    assert streak["active_today"] is False and streak["current"] == 0


def test_a_rank_won_in_a_boss_battle_is_kept(api, raw_db, model):
    ready(api, raw_db)
    fight(api, raw_db, model, win=True)
    assert api.get("/api/progress").json()["rank"]["name"] == rules.RANKS[1][1]
    raw_db.execute("DELETE FROM xp_events WHERE source_id = 9999")  # as if the XP that unlocked it was deleted
    raw_db.commit()
    for s in api.get("/api/study-sessions").json()["items"]:
        api.delete(f"/api/study-sessions/{s['id']}")
    p = api.get("/api/progress").json()
    assert p["rank"]["name"] == rules.RANKS[1][1] and p["total_xp"] < rules.RANKS[1][0]


def test_only_your_own_sessions_can_be_deleted(api):
    s = log_study(api)
    assert api.delete("/api/study-sessions/99999").status_code == 404
    token = api.headers.pop("X-CSRF-Token")
    assert api.delete(f"/api/study-sessions/{s['id']}").status_code == 403  # CSRF protected
    api.headers["X-CSRF-Token"] = token
    assert api.get("/api/study-sessions").json()["total"] == 1


def test_a_deleted_session_leaves_the_recap(api):
    log_study(api, context_text="Real study")
    oops = log_study(api, context_text="Logged by mistake")
    api.delete(f"/api/study-sessions/{oops['id']}")
    assert [s["context_text"] for s in api.get("/api/recap").json()["sessions"]] == ["Real study"]

