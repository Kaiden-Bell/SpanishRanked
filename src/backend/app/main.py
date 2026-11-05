import sqlite3
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, progression
from .clients.grammar import GrammarChecker, LanguageToolClient
from .clients.model import LanguageModel, OllamaClient
from .config import Settings
from .routes_assessments import router as assessments_router
from .routes_auth import announce_bootstrap, bootstrap_owner, router as auth_router
from .routes_progress import router as progress_router
from .routes_sessions import router as sessions_router
from .routes_system import router as system_router

def create_app(
    settings: Settings | None = None,
    *,
    model: LanguageModel | None = None,
    grammar: GrammarChecker | None = None,
) -> FastAPI:
    """``model`` and ``grammar`` default to the configured HTTP clients; tests pass fakes."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with closing(db.connect(settings.db_path)) as conn:
            db.migrate(conn)
            bootstrap_password = bootstrap_owner(conn)
            # Sessions saved before XP existed (or by an interrupted run) get their awards here.
            progression.award_missing_sessions(conn, settings.tz)
        if bootstrap_password:
            announce_bootstrap(bootstrap_password)
        yield

    app = FastAPI(title="Language AI", lifespan=lifespan)
    app.state.settings = settings
    app.state.model = model or OllamaClient(settings.ollama_url, settings.model_name, settings.model_timeout)
    app.state.grammar = grammar or LanguageToolClient(settings.languagetool_url, settings.languagetool_timeout)

    app.include_router(auth_router)
    app.include_router(sessions_router)
    app.include_router(progress_router)
    app.include_router(assessments_router)
    app.include_router(system_router)

    @app.get("/api/health")
    def health():
        try:
            with closing(db.connect(settings.db_path)) as conn:
                return {"status": "ok", "schema_version": db.schema_version(conn)}
        except sqlite3.Error:
            return JSONResponse({"status": "error"}, status_code=503)

    # Mounted last so it never shadows /api routes.
    if settings.frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")

    return app

app = create_app()
