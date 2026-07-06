"""Admin/control endpoints backing the Správa scrapingu (scraping admin) panel."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps import require_api_key
from app.api.rate_limit import heavy_endpoint_limiter
from app.core.db import engine, get_session
from app.models import RunItemLog, ScrapingRun
from app.schemas.scraping import (
    ReconcileOrphansResponse,
    RunItemLogRead,
    ScrapingRunRead,
    TriggerRunResponse,
)
from app.scraping.orphan_runs import reconcile_orphaned_scrape_runs
from app.scraping.pipeline import run_incremental_scrape, run_missing_detail_backfill

router = APIRouter(prefix="/scraping", tags=["scraping"])


def _vacuum_rawpayload() -> None:
    from sqlalchemy import text

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("VACUUM ANALYZE rawpayload"))


@router.get("/runs", response_model=list[ScrapingRunRead], summary="Historie scrapovacích běhů")
def list_runs(limit: int = 50, session: Session = Depends(get_session)):
    reconcile_orphaned_scrape_runs(session)
    stmt = select(ScrapingRun).order_by(ScrapingRun.started_at.desc()).limit(limit)
    return session.exec(stmt).all()


@router.post(
    "/reconcile-orphaned-runs",
    response_model=ReconcileOrphansResponse,
    summary="Uzavřít osiřelé scrapovací běhy",
    dependencies=[Depends(require_api_key)],
)
def reconcile_orphaned_runs(session: Session = Depends(get_session)):
    closed = reconcile_orphaned_scrape_runs(session)
    return ReconcileOrphansResponse(
        reconciled_count=len(closed),
        run_ids=[run.id for run in closed],
    )


@router.post(
    "/prune-raw-payloads",
    summary="Smazat archivní list raw payloady a uvolnit místo v DB",
    dependencies=[Depends(require_api_key)],
)
def prune_raw_payloads(session: Session = Depends(get_session)):
    """Drop list-type raw JSON blobs — structured fields already live in listing."""
    from sqlalchemy import text

    deleted = session.execute(text("DELETE FROM rawpayload WHERE payload_type = 'list'")).rowcount or 0
    session.commit()
    _vacuum_rawpayload()
    return {"deleted_rows": deleted, "message": f"Smazáno {deleted} řádků rawpayload (list)."}


@router.get("/runs/{run_id}/items", response_model=list[RunItemLogRead], summary="Chyby jednotlivých položek daného běhu")
def list_run_items(run_id: int, limit: int = Query(200, ge=1, le=2000), session: Session = Depends(get_session)):
    run = session.get(ScrapingRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scrapovací běh nebyl nalezen")

    stmt = (
        select(RunItemLog)
        .where(RunItemLog.run_id == run_id)
        .order_by(RunItemLog.created_at.desc())
        .limit(limit)
    )
    return session.exec(stmt).all()


async def _run_in_background():
    with Session(engine) as session:
        await run_incremental_scrape(session)


async def _run_missing_detail_backfill_in_background():
    with Session(engine) as session:
        await run_missing_detail_backfill(session)


@router.post(
    "/trigger",
    response_model=TriggerRunResponse,
    summary="Spustit scraping",
    dependencies=[Depends(require_api_key), Depends(heavy_endpoint_limiter)],
)
def trigger_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_in_background)
    return TriggerRunResponse(message="Scraping byl spuštěn na pozadí.")


@router.post(
    "/backfill-missing-details",
    response_model=TriggerRunResponse,
    summary="Doplnit chybějící detaily u aktivních nabídek",
    dependencies=[Depends(require_api_key), Depends(heavy_endpoint_limiter)],
)
def trigger_missing_detail_backfill(background_tasks: BackgroundTasks):
    """Re-runnable/idempotent: selects every active listing without a
    ListingDetail row at call time and backfills it. Safe to trigger again if
    a previous run was interrupted -- it only ever re-targets what's still
    missing, and is guarded by the same advisory lock as the auto-chained
    backfill so it can't run twice at once."""
    background_tasks.add_task(_run_missing_detail_backfill_in_background)
    return TriggerRunResponse(message="Doplnění chybějících detailů bylo spuštěno na pozadí.")
