"""Detect and close scrape runs left in ``running`` after a worker dies.

A run is considered orphaned when:
- its DB status is still ``running``,
- it is not registered as active in this process,
- the expected Postgres advisory lock is not held (released when the worker
  connection died), and
- it is older than a short grace window (avoids races at trigger time).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.scraping_run import RunStatus, RunType, ScrapingRun
from app.scraping.locks import BACKFILL_LOCK_ID, SWEEP_LOCK_ID

logger = logging.getLogger(__name__)

ORPHAN_RUN_MESSAGE = (
    "Běh byl přerušen (restart nebo pád backendu). Worker již neběží; "
    "data ingestovaná před přerušením zůstávají v datasetu."
)

_active_run_ids: set[int] = set()

# Default wait on SIGTERM / lifespan shutdown while a scrape still holds a lock.
DRAIN_TIMEOUT_SECONDS = 90
DRAIN_POLL_SECONDS = 2


def register_active_run(run_id: int) -> None:
    _active_run_ids.add(run_id)


def unregister_active_run(run_id: int) -> None:
    _active_run_ids.discard(run_id)


def is_active_in_process(run_id: int) -> bool:
    return run_id in _active_run_ids


def _lock_id_for_run(run: ScrapingRun) -> int:
    if run.run_type == RunType.detail_backfill:
        return BACKFILL_LOCK_ID
    return SWEEP_LOCK_ID


def _is_advisory_lock_held(session: Session, lock_id: int) -> bool:
    get_bind = getattr(session, "get_bind", None)
    if get_bind is None:
        return False
    bind = get_bind()
    dialect = getattr(bind, "dialect", None) if bind is not None else None
    if dialect is None or getattr(dialect, "name", None) != "postgresql":
        return False

    classid = (lock_id >> 32) & 0xFFFFFFFF
    objid = lock_id & 0xFFFFFFFF
    return bool(
        session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_locks
                    WHERE locktype = 'advisory'
                      AND classid = :classid
                      AND objid = :objid
                      AND granted = true
                )
                """
            ),
            {"classid": classid, "objid": objid},
        ).scalar()
    )


def any_scrape_lock_held(session: Session) -> bool:
    """True if a sweep or detail-backfill advisory lock is currently held."""
    return _is_advisory_lock_held(session, SWEEP_LOCK_ID) or _is_advisory_lock_held(
        session, BACKFILL_LOCK_ID
    )


async def drain_scrape_locks(
    *,
    timeout_seconds: float = DRAIN_TIMEOUT_SECONDS,
    poll_seconds: float = DRAIN_POLL_SECONDS,
) -> bool:
    """Wait until scrape locks are released, or until timeout.

    Returns True if drained cleanly, False if still busy after timeout.
    Used on process shutdown so Railway redeploy gives an in-flight sweep a
    brief chance to finish (or at least release the session lock) before kill.
    """
    from app.core.db import engine

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while True:
        with Session(engine) as session:
            busy = any_scrape_lock_held(session)
        if not busy and not _active_run_ids:
            logger.info("Scrape drain complete — no active locks or in-process runs")
            return True
        if loop.time() >= deadline:
            logger.warning(
                "Scrape drain timed out after %.0fs (locks/active still held); "
                "orphan reconciliation will close stale runs on next startup",
                timeout_seconds,
            )
            return False
        logger.info(
            "Waiting for scrape drain (active_in_process=%s)…",
            sorted(_active_run_ids),
        )
        await asyncio.sleep(poll_seconds)


def _protected_running_run_ids(session: Session, running_runs: list[ScrapingRun]) -> set[int]:
    """Runs that must stay ``running`` while a worker holds the advisory lock.

    When the lock is held we cannot tell which DB row is the live worker, so we
    keep only the newest ``running`` row per lock family (plus any row registered
    in-process). Older ``running`` rows from crashed/restarted workers are stale.
    """
    protected = {run.id for run in running_runs if is_active_in_process(run.id)}
    for lock_id in (SWEEP_LOCK_ID, BACKFILL_LOCK_ID):
        if not _is_advisory_lock_held(session, lock_id):
            continue
        family = [run for run in running_runs if _lock_id_for_run(run) == lock_id]
        if family:
            protected.add(max(family, key=lambda run: run.id).id)
    return protected


def reconcile_orphaned_scrape_runs(
    session: Session,
    *,
    grace_seconds: int = 30,
    now: datetime | None = None,
) -> list[ScrapingRun]:
    """Close stale ``running`` rows and return the runs that were reconciled."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(seconds=grace_seconds)
    running_runs = session.exec(select(ScrapingRun).where(ScrapingRun.status == RunStatus.running)).all()
    protected_ids = _protected_running_run_ids(session, running_runs)
    closed: list[ScrapingRun] = []

    for run in running_runs:
        if run.id in protected_ids:
            continue
        if run.started_at >= cutoff:
            continue

        run.finished_at = now
        if run.items_seen > 0 or run.pages_fetched > 0 or run.error_count > 0:
            run.status = RunStatus.partial
        else:
            run.status = RunStatus.failed
        run.error_message = ORPHAN_RUN_MESSAGE
        session.add(run)
        closed.append(run)

    if closed:
        session.commit()
        for run in closed:
            session.refresh(run)
        logger.warning(
            "Reconciled %d orphaned scrape run(s): %s",
            len(closed),
            [run.id for run in closed],
        )

    return closed
