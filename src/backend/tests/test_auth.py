import logging

from fastapi.testclient import TestClient

from app import db
from app.main import create_app
from app.routes_auth import bootstrap_owner
from app.security import verify_password

from conftest import BOOTSTRAP_PASSWORD, NEW_PASSWORD, set_owner_password, sign_in

PROTECTED = [
    ("get", "/api/auth/me"),
    ("post", "/api/auth/logout"),
    ("post", "/api/auth/change-password"),
    ("get", "/api/study-sessions"),
    ("post", "/api/study-sessions"),
    ("get", "/api/study-sessions/1"),
]


def test_anonymous_requests_are_rejected(client):
    for method, path in PROTECTED:
        assert getattr(client, method)(path).status_code == 401, (method, path)


def test_bootstrap_password_is_unique_per_installation(tmp_path):
    passwords = []
    for name in ("a", "b"):
        conn = db.connect(tmp_path / f"{name}.db")
        db.migrate(conn)
        passwords.append(bootstrap_owner(conn))
        stored = conn.execute("SELECT password_hash, must_change_password FROM users").fetchone()
        assert verify_password(passwords[-1], stored["password_hash"])
        assert stored["must_change_password"] == 1
        assert bootstrap_owner(conn) is None  # never re-bootstraps once a user exists
        conn.close()
    assert passwords[0] != passwords[1]


def test_bootstrap_credential_is_announced_once(settings, caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        with TestClient(create_app(settings)):
            pass
        assert "First run" in caplog.text
        caplog.clear()
        with TestClient(create_app(settings)):
            pass
    assert "First run" not in caplog.text


def test_password_is_stored_hashed_not_plaintext(client, raw_db):
    stored = raw_db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("scrypt$")
    assert BOOTSTRAP_PASSWORD not in stored


def test_wrong_password_and_unknown_user_look_identical(client):
    bad_pw = client.post("/api/auth/login", json={"username": "owner", "password": "nope"})
    no_user = client.post("/api/auth/login", json={"username": "ghost", "password": "nope"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()
    assert "set-cookie" not in bad_pw.headers


def test_login_sets_a_hardened_cookie_and_stores_only_a_token_hash(client, raw_db):
    response = sign_in(client, BOOTSTRAP_PASSWORD)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" not in cookie
    token = client.cookies.get("languageai_session")
    stored = raw_db.execute("SELECT token_hash FROM auth_sessions").fetchone()[0]
    assert token and stored != token


def test_cookie_is_secure_when_configured(settings):
    from dataclasses import replace

    secure = replace(settings, secure_cookies=True)
    with TestClient(create_app(secure)) as c:
        set_owner_password(secure, BOOTSTRAP_PASSWORD)
        r = c.post("/api/auth/login", json={"username": "owner", "password": BOOTSTRAP_PASSWORD})
    assert "secure" in r.headers["set-cookie"].lower()


def test_first_login_requires_a_password_change_before_anything_else(client):
    assert sign_in(client, BOOTSTRAP_PASSWORD).json()["must_change_password"] is True
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/study-sessions").status_code == 403
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": BOOTSTRAP_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    assert client.get("/api/study-sessions").status_code == 200


def test_change_password_rules(client):
    sign_in(client, BOOTSTRAP_PASSWORD)

    def change(current, new):
        return client.post("/api/auth/change-password", json={"current_password": current, "new_password": new})

    assert change("wrong-current", NEW_PASSWORD).status_code == 400
    assert change(BOOTSTRAP_PASSWORD, BOOTSTRAP_PASSWORD).status_code == 400  # unchanged
    assert change(BOOTSTRAP_PASSWORD, "short").status_code == 422
    assert client.get("/api/study-sessions").status_code == 403  # still locked: nothing succeeded


def test_old_password_stops_working_after_change(authed):
    authed.cookies.clear()
    old = authed.post("/api/auth/login", json={"username": "owner", "password": BOOTSTRAP_PASSWORD})
    new = authed.post("/api/auth/login", json={"username": "owner", "password": NEW_PASSWORD})
    assert old.status_code == 401 and new.status_code == 200


def test_changing_password_signs_out_other_devices(client, settings):
    sign_in(client, BOOTSTRAP_PASSWORD)
    with TestClient(client.app) as other:
        sign_in(other, BOOTSTRAP_PASSWORD)
        client.post(
            "/api/auth/change-password",
            json={"current_password": BOOTSTRAP_PASSWORD, "new_password": NEW_PASSWORD},
        )
        assert other.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me").status_code == 200


def test_state_changing_requests_need_the_csrf_token(authed):
    token = authed.headers.pop("X-CSRF-Token")
    assert authed.post("/api/auth/logout").status_code == 403
    authed.headers["X-CSRF-Token"] = "forged"
    assert authed.post("/api/auth/logout").status_code == 403
    authed.headers["X-CSRF-Token"] = token
    assert authed.get("/api/auth/me").status_code == 200  # safe methods don't need it
    assert authed.post("/api/auth/logout").status_code == 204


def test_logout_invalidates_the_session_server_side(authed):
    stolen = dict(authed.cookies)
    assert authed.post("/api/auth/logout").status_code == 204
    with TestClient(authed.app) as replay:
        replay.cookies.update(stolen)
        assert replay.get("/api/auth/me").status_code == 401


def test_expired_sessions_are_rejected(authed, raw_db):
    with raw_db:
        raw_db.execute("UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00Z'")
    assert authed.get("/api/auth/me").status_code == 401


def test_me_survives_a_page_refresh(authed):
    """The frontend recovers its CSRF token from /me after a reload."""
    body = authed.get("/api/auth/me").json()
    assert body["username"] == "owner" and body["csrf_token"] == authed.headers["X-CSRF-Token"]
