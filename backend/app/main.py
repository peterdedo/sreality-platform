from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from sqlmodel import Session

from app.api import analytics, analytics_advanced, export, listings, locations, scraping
from app.core.config import settings
from app.core.db import engine, init_db
from app.core.logging import configure_logging
from app.core.timing import TimingMiddleware
from app.scheduler import scheduler, start_scheduler
from app.analytics.advanced.pipeline import reconcile_orphaned_analytics_runs
from app.scraping.orphan_runs import (
    any_scrape_lock_held,
    clear_scrape_shutdown_request,
    drain_scrape_locks,
    reconcile_orphaned_scrape_runs,
    request_scrape_shutdown,
)

logger = logging.getLogger(__name__)


def _init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        traces_sample_rate=0.05,
        environment=settings.app_env,
    )
    logger.info("Sentry initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    _init_sentry()
    # init_db() runs SQLModel.metadata.create_all() -- a local/dev bootstrap
    # convenience only. In production Alembic migrations are the sole schema
    # authority, so create_all() is skipped there to avoid masking model/
    # migration drift (see app/core/db.py and the audit's Theme 4).
    if not settings.is_production:
        init_db()
    clear_scrape_shutdown_request()
    try:
        with Session(engine) as session:
            reconcile_orphaned_scrape_runs(session)
            reconcile_orphaned_analytics_runs(session)
    except Exception:
        logger.exception("Startup DB reconcile failed; serving /live in degraded mode")
    try:
        start_scheduler()
    except Exception:
        logger.exception("Scheduler failed to start")
    yield
    # Graceful drain on redeploy/SIGTERM: ask scrape to stop after the current
    # page, then wait briefly for locks to clear (Railway single-service model).
    if scheduler.running:
        scheduler.shutdown(wait=False)
    request_scrape_shutdown()
    drained = await drain_scrape_locks()
    if not drained:
        logger.warning("Shutdown proceeding while scrape work may still be active")


app = FastAPI(
    title="Sreality Platform API",
    description="Realitní analytická platforma nad daty sreality.cz",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://sreality-platform(-[a-z0-9-]+)?\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimingMiddleware)
# Large JSON payloads (map markers for the full dataset are ~30 MB raw) are
# highly compressible; without this they dominate page load time.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.include_router(listings.router, prefix=settings.api_prefix)
app.include_router(analytics.router, prefix=settings.api_prefix)
app.include_router(analytics_advanced.router, prefix=settings.api_prefix)
app.include_router(locations.router, prefix=settings.api_prefix)
app.include_router(scraping.router, prefix=settings.api_prefix)
app.include_router(export.router, prefix=settings.api_prefix)


@app.get("/live")
def live():
    """Railway edge liveness. Always 200 while the process can accept HTTP."""
    return {"status": "live"}


@app.get("/health")
def health():
    """Readiness for the Vercel rewrite/proxy (`/health`, `/api/*`)."""
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
            scrape_busy = any_scrape_lock_held(session)
        return {
            "status": "ok",
            "database": "connected",
            "scrape_busy": scrape_busy,
        }
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable", "scrape_busy": False},
        )
