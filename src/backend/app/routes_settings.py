"""Settings tab: practice preferences, motion, account actions and resetting all data."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import user_settings
from .deps import CurrentUser, get_db, ready_user
from .security import verify_password

router = APIRouter(prefix="/api/settings", tags=["settings"])

RESET_PHRASE = "RESET"


class ResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=256)
    confirm: str = Field(max_length=20)


@router.get("", response_model=user_settings.Settings)
def get_settings(user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    return user_settings.load(conn, user.id)


@router.patch("", response_model=user_settings.Settings)
def patch_settings(body: user_settings.SettingsPatch, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    return user_settings.save(conn, user.id, body)


@router.post("/sign-out-others")
def sign_out_others(user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    """End every sign-in except this one (a lost phone, a shared computer)."""
    with conn:
        ended = conn.execute(
            "DELETE FROM auth_sessions WHERE user_id = ? AND id != ?", (user.id, user.auth_session_id)
        ).rowcount
    return {"signed_out": ended}


@router.post("/reset")
def reset_all_data(body: ResetIn, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    """Start over. Needs the password and the word RESET typed out, because it can't be undone."""
    if body.confirm.strip() != RESET_PHRASE:
        raise HTTPException(400, f"Type {RESET_PHRASE} to confirm.")
    stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()
    if not verify_password(body.password, stored["password_hash"]):
        raise HTTPException(400, "Password is incorrect.")
    return {"deleted": user_settings.reset_all(conn, user.id)}
