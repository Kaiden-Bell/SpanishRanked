import sqlite3
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import Settings
from .routes_auth import announce_bootstrap, bootstrap_owner, router as auth_router
from .routes_sessions import router as sessions_router

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with closing(db.connect(settings.db_path)) as conn:
            db.migrate(conn)
            bootstrap_password = bootstrap_owner(conn)
        if bootstrap_password:
            announce_bootstrap(bootstrap_password)
        yield

    app = FastAPI(title="Language AI", lifespan=lifespan)
    app.state.settings = settings

    app.include_router(auth_router)
    app.include_router(sessions_router)

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
