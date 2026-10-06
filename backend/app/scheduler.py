"""APScheduler wiring for periodic scraping + analytics jobs.

Chosen over Celery: the workload here is a handful of periodic jobs (not
high-volume task fan-out), so in-process cron scheduling is simpler to operate.
See architecture.md section 8 for the documented Celery upgrade path.

Every cron cadence declared in Settings is registered here. JOB_SPECS is the
single source of truth mapping a job id -> (Settings cron attribute, callable);
a test asserts it covers exactly the Settings cron fields, so a future added
cron setting that isn't wired fails CI rather than silently never running.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.analytics.advanced.pipeline import run_full_recompute
from app.core.config import settings
from app.core.db import engine
from app.scraping.locks import BACKFILL_LOCK_ID
from app.scraping.orphan_runs import _is_advisory_lock_held
from app.scraping.pipeline import run_incremental_scrape
from app.scraping.prune import prune_list_raw_payloads

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _run_incremental_scrape_sync() -> None:
    async def _run() -> None:
        with Session(engine) as session:
            await run_incremental_scrape(session)

    asyncio.run(_run())


async def _scheduled_incremental_scrape() -> None:
    with Session(engine) as session:
        if _is_advisory_lock_held(session, BACKFILL_LOCK_ID):
            logger.info("Skipping scheduled incremental scrape — detail backfill in progress")
            return
    logger.info("Scheduled incremental scrape starting")
    await asyncio.to_thread(_run_incremental_scrape_sync)
    logger.info("Scheduled incremental scrape finished")


async def _scheduled_analytics_recompute() -> None:
    logger.info("Scheduled analytics recompute starting")
    # run_full_recompute is synchronous and DB-bound; run it off the event
    # loop so the scheduler's loop isn't blocked for its duration.
    def _work() -> None:
        with Session(engine) as session:
            run_full_recompute(session)

    await asyncio.to_thread(_work)
    logger.info("Scheduled analytics recompute finished")


async def _scheduled_prune_list_raw_payloads() -> None:
    logger.info("Scheduled list rawpayload prune starting")

    def _work() -> None:
        with Session(engine) as session:
            deleted = prune_list_raw_payloads(session)
            logger.info("Scheduled prune deleted %d list rawpayload row(s)", deleted)

    await asyncio.to_thread(_work)
    logger.info("Scheduled list rawpayload prune finished")


# job id -> (Settings attribute holding the cron "hour" expression, callable).
# test_scheduler.py asserts these attribute names are exactly the scheduling
# cron fields on Settings, so a newly-added cron setting that isn't wired here
# fails the test instead of silently never running.
JOB_SPECS: dict[str, tuple[str, object]] = {
    "incremental_scrape": ("incremental_scrape_cron_hour", _scheduled_incremental_scrape),
    "analytics_snapshot": ("analytics_snapshot_hour", _scheduled_analytics_recompute),
    "prune_list_raw_payloads": ("prune_raw_payloads_hour", _scheduled_prune_list_raw_payloads),
}


def build_cron_trigger(job_id: str, hour_attr: str) -> CronTrigger:
    hour = getattr(settings, hour_attr)
    if job_id == "incremental_scrape":
        return CronTrigger(
            day_of_week=settings.incremental_scrape_cron_day_of_week,
            hour=hour,
        )
    return CronTrigger(hour=hour)


def start_scheduler() -> None:
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled via ENABLE_SCHEDULER=false")
        return

    for job_id, (cron_attr, func) in JOB_SPECS.items():
        scheduler.add_job(
            func,
            trigger=build_cron_trigger(job_id, cron_attr),
            id=job_id,
            replace_existing=True,
            max_instances=1,
            # coalesce: if fires were missed during downtime, run once on
            # recovery, not N backlogged times. misfire_grace_time: still run a
            # job that fired while the process was briefly busy/down, within 1h.
            coalesce=True,
            misfire_grace_time=3600,
        )
    scheduler.start()
    logger.info(
        "Scheduler started with jobs: %s (incremental_scrape=%s %s:00 UTC)",
        ", ".join(JOB_SPECS),
        settings.incremental_scrape_cron_day_of_week,
        settings.incremental_scrape_cron_hour,
    )
