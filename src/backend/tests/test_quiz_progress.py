"""The recap at the end of a quiz: what that quiz changed in XP and skills."""

from test_assessments import answers, api, app_factory, grammar, log_study, model, new_quiz  # noqa: F401  (fixtures)


def _graded(api, focus="SENTENCES"):
    quiz = new_quiz(api, focus)
    r = api.post(f"/api/assessments/{quiz['id']}/submit", json=answers(quiz))
    assert r.json()["status"] == "GRADED", r.text
    return r.json()


def test_a_graded_quiz_reports_xp_before_and_after_from_the_ledger(api):
    log_study(api)
    before = api.get("/api/progress").json()["total_xp"]
    done = _graded(api)
    xp = done["progress"]["xp"]
    assert xp["before"] == before and xp["after"] == before + done["award"]["awarded_xp"]
    assert xp["gained"] == done["award"]["awarded_xp"] > 0
    assert xp["band_min"] == 0 and xp["band_max"] > xp["after"] and xp["next_rank"]
    assert done["progress"]["rank_up"] is None


def test_only_the_skills_the_quiz_touched_are_reported_with_their_answer_counts(api):
    log_study(api)
    done = _graded(api)
    keys = {s["key"] for s in done["progress"]["skills"]}
    assert "WRITING" in keys and "LISTENING" not in keys and "SPEAKING" not in keys
    writing = next(s for s in done["progress"]["skills"] if s["key"] == "WRITING")
    assert writing["before"]["answers_needed"] > writing["after"]["answers_needed"]


def test_reopening_an_older_quiz_shows_what_it_changed_then(api):
    log_study(api)
    first = _graded(api)
    log_study(api, terms=["comer", "vivir", "hablar"])
    _graded(api)
    again = api.get(f"/api/assessments/{first['id']}").json()
    assert again["progress"] == first["progress"]


def test_lists_and_unfinished_quizzes_carry_no_progress(api):
    log_study(api)
    quiz = new_quiz(api)
    assert api.get(f"/api/assessments/{quiz['id']}").json()["progress"] is None
    _graded(api)
    assert "progress" not in api.get("/api/assessments").json()["items"][0]
