"""Orchestrates one end-to-end Pokročilé analýzy recompute run: market
dynamics -> valuation -> anomaly -> spatial snapshot, in that order, tracked
as a single AnalyticsRun row (mirrors app.scraping.pipeline's ScrapingRun
pattern, and the single "Spustit scraping" trigger UX)."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session, select

from app.analytics.advanced import market_dynamics, spatial, valuation
from app.analytics.advanced.anomaly import compute_anomalies
from app.models import AnalyticsRun
from app.models.analytics_run import AdvancedAnalyticsRunStatus, AdvancedAnalyticsRunType
from app.scraping.locks import ANALYTICS_LOCK_ID
from app.scraping.orphan_runs import _is_advisory_lock_held

logger = logging.getLogger(__name__)


def _release_lock(session: Session, lock_id: int) -> None:
    session.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})

ORPHANED_ANALYTICS_RUN_MESSAGE = (
    "Přepočet byl přerušen (restart nebo pád backendu). Worker již neběží; "
    "spusťte přepočet znovu."
)


def reconcile_orphaned_analytics_runs(session: Session, *, grace_seconds: int = 30) -> list[AnalyticsRun]:
    """Close AnalyticsRun rows stuck in ``running`` after a worker died.

    Same criteria as reconcile_orphaned_scrape_runs: still 'running' in the DB,
    past a short grace window, and the analytics advisory lock is not held
    anywhere (the lock is session-scoped, so a dead worker's lock is gone)."""
    cutoff = datetime.utcnow() - timedelta(seconds=grace_seconds)
    running = session.exec(
        select(AnalyticsRun).where(AnalyticsRun.status == AdvancedAnalyticsRunStatus.running)
    ).all()
    closed: list[AnalyticsRun] = []
    for run in running:
        if run.started_at >= cutoff:
            continue
        if _is_advisory_lock_held(session, ANALYTICS_LOCK_ID):
            continue
        run.status = AdvancedAnalyticsRunStatus.failed
        run.error_message = ORPHANED_ANALYTICS_RUN_MESSAGE
        run.finished_at = datetime.utcnow()
        session.add(run)
        closed.append(run)
    if closed:
        session.commit()
        logger.warning("Reconciled %d orphaned analytics run(s): %s", len(closed), [r.id for r in closed])
    return closed


def run_full_recompute(session: Session) -> AnalyticsRun:
    run = AnalyticsRun(run_type=AdvancedAnalyticsRunType.all)
    session.add(run)
    session.commit()
    session.refresh(run)

    # Same advisory-lock guard as the scrape sweep/backfill: two concurrent
    # recomputes would interleave snapshot/valuation writes for the same day.
    got_lock = bool(
        session.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": ANALYTICS_LOCK_ID}).scalar()
    )
    if not got_lock:
        run.status = AdvancedAnalyticsRunStatus.failed
        run.error_message = "Jiný přepočet pokročilých analýz již běží (advisory lock); tento pokus byl přeskočen."
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    items_processed = 0
    try:
        snapshots = market_dynamics.compute_market_dynamics_snapshot(session)
        items_processed += len(snapshots)
        logger.info("Market dynamics: %d segment snapshots", len(snapshots))

        models = valuation.fit_and_apply_valuations(session)
        items_processed += len(models)
        logger.info("Valuation: %d models fitted", len(models))

        anomalies = compute_anomalies(session)
        items_processed += len(anomalies)
        logger.info("Anomaly: %d listings scored", len(anomalies))

        grid_metrics = spatial.snapshot_grid_metrics(session)
        items_processed += len(grid_metrics)
        logger.info("Spatial: %d grid cells snapshotted", len(grid_metrics))

        run.status = AdvancedAnalyticsRunStatus.success
    except Exception as exc:
        logger.exception("Advanced analytics recompute failed")
        run.status = AdvancedAnalyticsRunStatus.failed
        run.error_message = str(exc)
        run.error_count += 1
    finally:
        _release_lock(session, ANALYTICS_LOCK_ID)
        run.items_processed = items_processed
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)

    return run
