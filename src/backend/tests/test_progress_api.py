import pytest
from fastapi.testclient import TestClient

from app import db, progression
from app.config import Settings
from app.main import create_app

from conftest import set_owner_password
from test_study_sessions import payload


def log(client, minutes=30):
    r = client.post("/api/study-sessions", json=payload(duration_minutes=minutes))
    assert r.status_code == 201, r.text
    return r.json()


def test_progress_requires_sign_in_and_a_changed_password(client):
    assert client.get("/api/progress").status_code == 401
    from conftest import BOOTSTRAP_PASSWORD, sign_in
    sign_in(client, BOOTSTRAP_PASSWORD)
    assert client.get("/api/progress").status_code == 403


def test_empty_dashboard(authed):
    body = authed.get("/api/progress").json()
    assert body["total_xp"] == 0
    assert body["rank"] == {"name": "Pre-Learner I", "min_xp": 0}
    assert body["next_rank"] == {"name": "Pre-Learner II", "min_xp": 120}
    assert body["xp_to_next"] == 120
    assert body["streak"] == {"current": 0, "active_today": False, "next_multiplier": 1.0}
    assert body["today"]["study_xp"] == 0 and body["today"]["study_xp_cap"] == 100


def test_logging_a_30_minute_session_awards_30_xp_and_starts_a_streak(authed):
    award = log(authed)["award"]
    assert award == {"base_xp": 30, "multiplier": 1.0, "awarded_xp": 30, "capped": False}
    body = authed.get("/api/progress").json()
    assert body["total_xp"] == 30 and body["xp_to_next"] == 90
    assert body["streak"] == {"current": 1, "active_today": True, "next_multiplier": 1.0}
    assert body["today"]["study_xp"] == 30


def test_the_daily_study_cap_is_reported_to_the_learner(authed):
    awards = [log(authed)["award"] for _ in range(5)]
    assert [a["awarded_xp"] for a in awards] == [30, 30, 30, 10, 0]
    assert [a["capped"] for a in awards] == [False, False, False, True, True]
    body = authed.get("/api/progress").json()
    assert body["total_xp"] == 100 and body["today"]["study_xp"] == 100
    assert body["streak"]["current"] == 1  # capped sessions don't inflate the streak


def test_total_xp_is_derived_from_the_ledger_and_survives_restart(settings, authed, raw_db):
    log(authed); log(authed)
    assert raw_db.execute("SELECT SUM(awarded_xp) FROM xp_events").fetchone()[0] == 60
    with TestClient(create_app(settings)) as again:
        from conftest import NEW_PASSWORD, sign_in
        sign_in(again, NEW_PASSWORD)
        assert again.get("/api/progress").json()["total_xp"] == 60


def test_startup_awards_sessions_that_predate_xp(settings, authed, raw_db):
    with raw_db:
        raw_db.execute(
            "INSERT INTO study_sessions (user_id, language_code, mode, activity_type, duration_minutes, context_text)"
            " VALUES (1, 'es', 'SELF_STUDY', 'READING', 30, 'legacy')"
        )
    assert authed.get("/api/progress").json()["total_xp"] == 0
    with TestClient(create_app(settings)) as restarted:
        from conftest import NEW_PASSWORD, sign_in
        sign_in(restarted, NEW_PASSWORD)
        assert restarted.get("/api/progress").json()["total_xp"] == 30
    with TestClient(create_app(settings)) as restarted_again:  # and not paid a second time
        sign_in(restarted_again, NEW_PASSWORD)
        assert restarted_again.get("/api/progress").json()["total_xp"] == 30


def test_a_failure_while_awarding_saves_neither_session_nor_xp(authed, raw_db, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("ledger offline")

    monkeypatch.setattr(progression, "award_xp", boom)
    with TestClient(authed.app, raise_server_exceptions=False, cookies=authed.cookies,
                    headers={"X-CSRF-Token": authed.headers["X-CSRF-Token"]}) as c:
        assert c.post("/api/study-sessions", json=payload()).status_code == 500
    assert raw_db.execute("SELECT COUNT(*) FROM study_sessions").fetchone()[0] == 0
    assert raw_db.execute("SELECT COUNT(*) FROM study_terms").fetchone()[0] == 0


def test_day_boundaries_follow_the_timezone_setting(tmp_path):
    from dataclasses import replace
    s = replace(Settings(data_dir=tmp_path / "d", frontend_dist=tmp_path / "n"), timezone="Asia/Tokyo")
    with TestClient(create_app(s)) as c:
        set_owner_password(s, "bootstrap-password")
        c.post("/api/auth/login", json={"username": "owner", "password": "bootstrap-password"})
        c.headers["X-CSRF-Token"] = c.get("/api/auth/me").json()["csrf_token"]
        c.post("/api/auth/change-password", json={"current_password": "bootstrap-password", "new_password": "a-much-better-password"})
        log(c)
        today = c.get("/api/progress").json()["today"]["date"]
    from datetime import datetime
    from zoneinfo import ZoneInfo
    assert today == datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()


def test_invalid_timezone_fails_fast_with_a_clear_message(monkeypatch):
    monkeypatch.setenv("LANGUAGEAI_TIMEZONE", "Mars/Olympus")
    with pytest.raises(ValueError, match="LANGUAGEAI_TIMEZONE"):
        Settings.from_env()


def test_timezone_defaults_to_utc(monkeypatch):
    monkeypatch.delenv("LANGUAGEAI_TIMEZONE", raising=False)
    assert Settings.from_env().timezone == "UTC"
