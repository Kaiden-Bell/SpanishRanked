"""Boss battles (docs/ROADMAP.md Phase 5)."""

import json

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from . import progression, user_settings
from .deps import CurrentUser, get_db, get_model, ready_user
from .practice import boss
from .practice.compose import NeedsModel, NotEnoughMaterial
from .routes_assessments import _load

router = APIRouter(prefix="/api/boss", tags=["boss"])


class BossIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    listening: bool = True


def _state(conn, user_id: int) -> dict:
    out = boss.state(conn, user_id, progression.total_xp(conn, user_id), datetime.now(timezone.utc))
    out.pop("held_index")
    # The most recent finished battle, whatever rank it was for: after a win the open boss moves on.
    latest = conn.execute(
        "SELECT id, rank_name, status, stage_results_json, cooldown_until, assessment_id FROM boss_attempts"
        " WHERE user_id = ? AND status != 'IN_PROGRESS' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    out["latest"] = {
        "id": latest["id"], "rank": latest["rank_name"], "status": latest["status"],
        "assessment_id": latest["assessment_id"], "cooldown_until": latest["cooldown_until"],
        **json.loads(latest["stage_results_json"] or "{}"),
    } if latest else None
    return out


@router.get("")
def get_boss(user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    return _state(conn, user.id)


@router.post("", status_code=201)
def start_boss(
    request: Request,
    body: BossIn | None = Body(None),
    user: CurrentUser = Depends(ready_user),
    conn=Depends(get_db),
    model=Depends(get_model),
):
    """Start the battle for the next rank, or resume the one in progress."""
    body = body or BossIn()
    try:
        boss.start(conn, request.app.state.verbs, user.id, progression.total_xp(conn, user.id),
                   listening=body.listening and user_settings.load(conn, user.id).listening,
                   model_ok=model.status() == "ok")
    except NotEnoughMaterial as exc:
        raise HTTPException(409, str(exc))
    except NeedsModel as exc:
        raise HTTPException(503, str(exc))
    state = _state(conn, user.id)
    return {"boss": state, "assessment": _load(conn, user.id, state["assessment_id"])}
