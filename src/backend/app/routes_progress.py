from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from . import progression
from .deps import CurrentUser, get_db, ready_user
from .schemas import ProgressOut

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def get_progress(request: Request, user: CurrentUser = Depends(ready_user), conn=Depends(get_db)):
    return progression.progress(conn, user.id, datetime.now(timezone.utc), request.app.state.settings.tz)
