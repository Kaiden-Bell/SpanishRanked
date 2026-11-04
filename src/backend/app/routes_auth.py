import logging
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import db
from .deps import SESSION_COOKIE, CurrentUser, current_user, get_db
from .security import DUMMY_HASH, hash_password, hash_token, new_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

OWNER_USERNAME = "owner"


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


def user_payload(user: CurrentUser) -> dict:
    return {
        "username": user.username,
        "must_change_password": user.must_change_password,
        "csrf_token": user.csrf_token,
    }


def bootstrap_owner(conn: sqlite3.Connection) -> str | None:
    """On first run, create the owner with a random one-time password and return it."""
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return None
    password = secrets.token_urlsafe(16)
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (OWNER_USERNAME, hash_password(password)),
        )
    return password


def announce_bootstrap(password: str) -> None:
    logging.getLogger("uvicorn.error").warning(
        "\n=== First run: sign in as '%s' with password '%s' ===\n"
        "You will be asked to change it immediately. This is shown only once.",
        OWNER_USERNAME,
        password,
    )


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, conn=Depends(get_db)):
    settings = request.app.state.settings
    row = conn.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    password_ok = verify_password(body.password, row["password_hash"] if row else DUMMY_HASH)
    if row is None or not password_ok:
        raise HTTPException(401, "Invalid username or password.")

    token, csrf = new_token(), new_token()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=settings.session_ttl_hours)
    with conn:
        conn.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (db.utc_timestamp(now),))
        conn.execute(
            "INSERT INTO auth_sessions (user_id, token_hash, csrf_token, expires_at) VALUES (?, ?, ?, ?)",
            (row["id"], hash_token(token), csrf, db.utc_timestamp(expires)),
        )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )
    return {
        "username": row["username"],
        "must_change_password": bool(row["must_change_password"]),
        "csrf_token": csrf,
    }


@router.get("/me")
def me(user: CurrentUser = Depends(current_user)):
    return user_payload(user)


@router.post("/logout", status_code=204)
def logout(response: Response, user: CurrentUser = Depends(current_user), conn=Depends(get_db)):
    with conn:
        conn.execute("DELETE FROM auth_sessions WHERE id = ?", (user.auth_session_id,))
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.post("/change-password")
def change_password(
    body: ChangePasswordIn, user: CurrentUser = Depends(current_user), conn=Depends(get_db)
):
    stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()
    if not verify_password(body.current_password, stored["password_hash"]):
        raise HTTPException(400, "Current password is incorrect.")
    if body.new_password == body.current_password:
        raise HTTPException(400, "New password must be different from the current one.")
    if body.new_password.casefold() == user.username.casefold():
        raise HTTPException(400, "Password must not be your username.")
    with conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (hash_password(body.new_password), user.id),
        )
        # Sign out every other device; this one stays signed in.
        conn.execute(
            "DELETE FROM auth_sessions WHERE user_id = ? AND id != ?", (user.id, user.auth_session_id)
        )
    return user_payload(CurrentUser(user.id, user.username, False, user.csrf_token, user.auth_session_id))
