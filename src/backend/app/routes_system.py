import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from . import db
from .deps import CurrentUser, get_grammar, get_model, ready_user
from .schemas import SystemStatus

router = APIRouter(prefix="/api/system", tags=["system"])

CACHE_SECONDS = 10.0


@router.get("/status", response_model=SystemStatus)
def system_status(
    request: Request,
    user: CurrentUser = Depends(ready_user),
    model=Depends(get_model),
    grammar=Depends(get_grammar),
):
    """Health of each dependency, cached briefly so a dashboard poll never hammers the sidecars."""
    cached = getattr(request.app.state, "status_cache", None)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        with closing(db.connect(request.app.state.settings.db_path)) as conn:
            conn.execute("SELECT 1")
        database = "ok"
    except sqlite3.Error:
        database = "down"
    payload = SystemStatus(
        database=database,
        languagetool=grammar.status(),
        model=model.status(),
        checked_at=db.utc_timestamp(datetime.now(timezone.utc)),
    )
    request.app.state.status_cache = (time.monotonic(), payload)
    return payload
