"""Background grading: free sentences are graded off the request, so the learner can keep using the app."""

import dataclasses
import time

import pytest
from fastapi.testclient import TestClient

from app.assessment.worker import Grader
from app.clients.model import ModelUnavailable
from app.main import create_app

from conftest import BOOTSTRAP_PASSWORD, NEW_PASSWORD, set_owner_password, sign_in
from test_assessments import FakeGrammar, FakeModel, answers, log_study, new_quiz


@pytest.fixture
def model():
    return FakeModel()


@pytest.fixture
def bg_settings(settings):
    return dataclasses.replace(settings, background_grading=True)


@pytest.fixture
def manual_worker(monkeypatch):
    """The worker thread never starts; tests run it by hand with app.state.grader.run_pending()."""
    monkeypatch.setattr(Grader, "start", lambda self: None)


def _client(settings, model):
    return TestClient(create_app(settings, model=model, grammar=FakeGrammar()))


@pytest.fixture
def bg(bg_settings, model, manual_worker):
    with _client(bg_settings, model) as c:
        set_owner_password(bg_settings, BOOTSTRAP_PASSWORD)
        sign_in(c, BOOTSTRAP_PASSWORD)
        assert c.post("/api/auth/change-password",
                      json={"current_password": BOOTSTRAP_PASSWORD, "new_password": NEW_PASSWORD}).status_code == 200
        yield c


def _answer_all(c, quiz):
    out = None
    for a in answers(quiz)["answers"]:
        out = c.post(f"/api/assessments/{quiz['id']}/answers", json=a)
        assert out.status_code == 200, out.text
    return out.json()


def test_a_sentence_quiz_comes_back_at_once_and_is_graded_in_the_background(bg, model):
    log_study(bg)
    quiz = new_quiz(bg)
    done = _answer_all(bg, quiz)
    assert done["status"] == "SUBMITTED" and done["grading"] is True and done["grading_error"] is None
    assert model.count("grade") == 0  # nothing graded inside the request

    since = bg.get("/api/assessments/activity").json()
    assert since["grading"] == [quiz["id"]] and since["graded"] == []

    assert bg.app.state.grader.run_pending() == 1
    graded = bg.get(f"/api/assessments/{quiz['id']}").json()
    assert graded["status"] == "GRADED" and graded["grading"] is False and graded["award"]["awarded_xp"] > 0

    later = bg.get("/api/assessments/activity", params={"since": since["now"]}).json()
    assert later["grading"] == []
    assert [g["id"] for g in later["graded"]] == [quiz["id"]]
    assert later["graded"][0]["correct"] == len(quiz["items"])


def test_a_code_checked_quiz_still_grades_inside_the_request(bg, model):
    log_study(bg)
    r = bg.post("/api/warmups", json={"listening": False})
    assert r.status_code == 201, r.text
    quiz = r.json()
    assert all(i["item_type"] != "WRITE" for i in quiz["items"])
    assert _answer_all(bg, quiz)["status"] == "GRADED"


def test_a_failure_leaves_the_queue_and_a_retry_queues_it_again(bg, model):
    log_study(bg)
    quiz = new_quiz(bg)
    _answer_all(bg, quiz)
    model.queue = [ModelUnavailable("The model is not running.")]
    bg.app.state.grader.run_pending()
    failed = bg.get(f"/api/assessments/{quiz['id']}").json()
    assert failed["status"] == "SUBMITTED" and failed["grading"] is False and failed["grading_error"]
    assert bg.app.state.grader.run_pending() == 0  # out of the queue until the learner retries

    retried = bg.post(f"/api/assessments/{quiz['id']}/grade").json()
    assert retried["grading"] is True and retried["grading_error"] is None
    bg.app.state.grader.run_pending()
    assert bg.get(f"/api/assessments/{quiz['id']}").json()["status"] == "GRADED"


def test_a_quiz_queued_before_a_restart_is_graded_after_it(bg, bg_settings, model, monkeypatch):
    log_study(bg)
    quiz = new_quiz(bg)
    _answer_all(bg, quiz)
    monkeypatch.undo()  # the real worker thread starts with the next app
    with _client(bg_settings, model) as again:
        sign_in(again, NEW_PASSWORD)
        deadline = time.monotonic() + 5
        while again.get(f"/api/assessments/{quiz['id']}").json()["status"] != "GRADED":
            assert time.monotonic() < deadline, "the queued quiz was not graded after the restart"
            time.sleep(0.05)
