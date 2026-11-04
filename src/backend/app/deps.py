"""Request dependencies: database connection, authentication, CSRF."""

import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from . import db
from .security import hash_token

SESSION_COOKIE = "languageai_session"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_db(request: Request):
    # check_same_thread=False: FastAPI may run the dependency and the endpoint on different
    # worker threads, but a connection is only ever used by one request at a time.
    conn = db.connect(request.app.state.settings.db_path, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    must_change_password: bool
    csrf_token: str
    auth_session_id: int


def current_user(request: Request, conn=Depends(get_db)) -> CurrentUser:
    """Authenticated user (may still owe a password change). Enforces CSRF on unsafe methods."""
    token = request.cookies.get(SESSION_COOKIE)
    row = None
    if token:
        row = conn.execute(
            "SELECT u.id, u.username, u.must_change_password, s.id AS auth_session_id, s.csrf_token"
            " FROM auth_sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token_hash = ? AND s.expires_at > ?",
            (hash_token(token), db.utc_timestamp()),
        ).fetchone()
    if row is None:
        raise HTTPException(401, "Not signed in.")
    if request.method not in _SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(sent.encode(), row["csrf_token"].encode()):
            raise HTTPException(403, "Missing or invalid CSRF token.")
    return CurrentUser(
        id=row["id"],
        username=row["username"],
        must_change_password=bool(row["must_change_password"]),
        csrf_token=row["csrf_token"],
        auth_session_id=row["auth_session_id"],
    )


def ready_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """Authenticated user who has already replaced the bootstrap password."""
    if user.must_change_password:
        raise HTTPException(403, "Password change required.")
    return user
