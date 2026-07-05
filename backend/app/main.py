from contextlib import asynccontextmanager

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
from app.scheduler import start_scheduler
from app.analytics.advanced.pipeline import reconcile_orphaned_analytics_runs
from app.scraping.orphan_runs import reconcile_orphaned_scrape_runs


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # init_db() runs SQLModel.metadata.create_all() -- a local/dev bootstrap
    # convenience only. In production Alembic migrations are the sole schema
    # authority, so create_all() is skipped there to avoid masking model/
    # migration drift (see app/core/db.py and the audit's Theme 4).
    if not settings.is_production:
        init_db()
    with Session(engine) as session:
        reconcile_orphaned_scrape_runs(session)
        reconcile_orphaned_analytics_runs(session)
    start_scheduler()
    yield


app = FastAPI(
    title="Sreality Platform API",
    description="Realitní analytická platforma nad daty sreality.cz",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://([a-z0-9-]+\.)*vercel\.app",
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


@app.get("/health")
def health():
    """Liveness + DB readiness for Railway/Vercel proxy checks."""
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )
