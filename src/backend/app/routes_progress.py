from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from . import progression
from .deps import CurrentUser, get_db, ready_user
from .practice import skills
from .schemas import ProgressOut

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def get_progress(request: Request, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    return progression.progress(conn, user.id, datetime.now(timezone.utc), request.app.state.settings.tz)


@router.get("/skills")
def get_skills(user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    """Per-skill estimates from your own answers (docs/ROADMAP.md Phase 4)."""
    return skills.profile(conn, user.id)
