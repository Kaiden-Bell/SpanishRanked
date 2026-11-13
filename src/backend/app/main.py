import sqlite3
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, progression
from .clients.grammar import GrammarChecker, LanguageToolClient
from .clients.model import LanguageModel, OllamaClient
from .config import Settings
from .lexicon import bank
from .lexicon.enrich import Enricher, reset_offline
from .lexicon.sources import LexiconSources
from .lexicon.verbs import VerbData
from .routes_assessments import router as assessments_router
from .routes_bank import router as bank_router
from .routes_settings import router as settings_router
from .routes_boss import router as boss_router
from .routes_recap import router as recap_router
from .routes_auth import announce_bootstrap, bootstrap_owner, router as auth_router
from .routes_progress import router as progress_router
from .routes_sessions import router as sessions_router
from .routes_system import router as system_router

def create_app(
    settings: Settings | None = None,
    *,
    model: LanguageModel | None = None,
    grammar: GrammarChecker | None = None,
    sources: LexiconSources | None = None,
    enrich_inline: bool = False,
) -> FastAPI:
    """``model``, ``grammar`` and ``sources`` default to the configured HTTP clients; tests pass fakes.
    ``enrich_inline`` runs word lookups synchronously instead of on the background worker."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with closing(db.connect(settings.db_path)) as conn:
            db.migrate(conn)
            bootstrap_password = bootstrap_owner(conn)
            # Sessions saved before XP existed (or by an interrupted run) get their awards here.
            progression.award_missing_sessions(conn, settings.tz)
            if conn.execute("SELECT 1 FROM pending_jobs WHERE name = 'reparse_word_bank'").fetchone():
                bank.reparse_all(conn, app.state.verbs)
                with conn:
                    conn.execute("DELETE FROM pending_jobs WHERE name = 'reparse_word_bank'")
            # Terms logged before the word bank existed (or while it failed) are added now.
            bank.ingest_missing(conn, app.state.verbs)
            if app.state.sources.enabled:
                reset_offline(conn)
        if bootstrap_password:
            announce_bootstrap(bootstrap_password)
        app.state.enricher.start()
        app.state.enricher.kick()
        yield
        app.state.enricher.stop()

    app = FastAPI(title="Language AI", lifespan=lifespan)
    app.state.settings = settings
    app.state.model = model or OllamaClient(settings.ollama_url, settings.model_name, settings.model_timeout)
    app.state.grammar = grammar or LanguageToolClient(settings.languagetool_url, settings.languagetool_timeout)
    app.state.verbs = VerbData(settings.verb_data_path)
    app.state.sources = sources or LexiconSources(
        settings.online_lookups, settings.lookup_timeout, contact=settings.lookup_contact
    )
    app.state.enricher = Enricher(settings.db_path, app.state.sources, app.state.verbs, inline=enrich_inline)

    app.include_router(auth_router)
    app.include_router(sessions_router)
    app.include_router(progress_router)
    app.include_router(assessments_router)
    app.include_router(system_router)
    app.include_router(bank_router)
    app.include_router(recap_router)
    app.include_router(boss_router)
    app.include_router(settings_router)

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
