"""Tests for orphaned scrape run detection and reconciliation."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.scraping_run import RunStatus, RunType, ScrapingRun
from app.scraping.orphan_runs import (
    ORPHAN_RUN_MESSAGE,
    is_active_in_process,
    reconcile_orphaned_scrape_runs,
    register_active_run,
    unregister_active_run,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _running_run(
    *,
    run_id: int = 1,
    started_at: datetime | None = None,
    items_seen: int = 0,
    pages_fetched: int = 0,
    error_count: int = 0,
) -> ScrapingRun:
    return ScrapingRun(
        id=run_id,
        run_type=RunType.incremental,
        status=RunStatus.running,
        started_at=started_at or datetime.utcnow() - timedelta(minutes=5),
        pages_fetched=pages_fetched,
        items_seen=items_seen,
        items_new=items_seen,
        error_count=error_count,
    )


def test_reconcile_closes_stale_running_run_with_progress(session: Session):
    run = _running_run(items_seen=100, pages_fetched=10)
    session.add(run)
    session.commit()
    session.refresh(run)

    closed = reconcile_orphaned_scrape_runs(session, now=datetime.utcnow())

    assert len(closed) == 1
    assert closed[0].id == run.id
    assert closed[0].status == RunStatus.partial
    assert closed[0].finished_at is not None
    assert closed[0].error_message == ORPHAN_RUN_MESSAGE


def test_reconcile_closes_stale_running_run_without_progress_as_failed(session: Session):
    run = _running_run()
    session.add(run)
    session.commit()

    closed = reconcile_orphaned_scrape_runs(session, now=datetime.utcnow())

    assert len(closed) == 1
    assert closed[0].status == RunStatus.failed


def test_reconcile_skips_recent_run_within_grace_period(session: Session):
    run = _running_run(started_at=datetime.utcnow() - timedelta(seconds=5))
    session.add(run)
    session.commit()

    closed = reconcile_orphaned_scrape_runs(session, grace_seconds=30, now=datetime.utcnow())

    assert closed == []
    refreshed = session.get(ScrapingRun, run.id)
    assert refreshed.status == RunStatus.running


def test_reconcile_skips_in_process_active_run(session: Session):
    run = _running_run(items_seen=50)
    session.add(run)
    session.commit()
    session.refresh(run)

    register_active_run(run.id)
    try:
        closed = reconcile_orphaned_scrape_runs(session, now=datetime.utcnow())
        assert closed == []
        refreshed = session.get(ScrapingRun, run.id)
        assert refreshed.status == RunStatus.running
    finally:
        unregister_active_run(run.id)


@patch("app.scraping.orphan_runs._is_advisory_lock_held", return_value=True)
def test_reconcile_closes_older_running_when_lock_held_by_newer(_mock_lock, session: Session):
    stale = _running_run(run_id=1, items_seen=100, pages_fetched=10)
    stale.started_at = datetime.utcnow() - timedelta(hours=2)
    current = _running_run(run_id=2, items_seen=5, pages_fetched=1)
    current.started_at = datetime.utcnow() - timedelta(minutes=10)
    session.add(stale)
    session.add(current)
    session.commit()

    closed = reconcile_orphaned_scrape_runs(session, now=datetime.utcnow())

    assert len(closed) == 1
    assert closed[0].id == 1
    assert session.get(ScrapingRun, 2).status == RunStatus.running


@patch("app.scraping.orphan_runs._is_advisory_lock_held", return_value=True)
def test_reconcile_skips_when_advisory_lock_held(_mock_lock, session: Session):
    run = _running_run(items_seen=50)
    session.add(run)
    session.commit()

    closed = reconcile_orphaned_scrape_runs(session, now=datetime.utcnow())

    assert closed == []
    refreshed = session.get(ScrapingRun, run.id)
    assert refreshed.status == RunStatus.running


def test_is_active_in_process_registry():
    register_active_run(99)
    try:
        assert is_active_in_process(99) is True
        assert is_active_in_process(100) is False
    finally:
        unregister_active_run(99)
        assert is_active_in_process(99) is False
