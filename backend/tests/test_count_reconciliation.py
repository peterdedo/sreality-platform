"""Tests for dataset completeness assessment and count reconciliation helpers."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Listing, ScrapingRun
from app.models.scraping_run import RunStatus, RunType
from app.scraping.count_reconciliation import (
    EXPECTED_CATEGORY_SLICES,
    assess_dataset_completeness,
    assess_dataset_freshness,
    build_count_reconciliation_report,
    classify_slice_reconciliation,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_assess_empty_dataset(session: Session):
    assert assess_dataset_completeness(session) == "empty"


def test_assess_partial_single_slice(session: Session):
    session.add(
        Listing(
            hash_id="a1",
            category_main_cb=1,
            category_type_cb=1,
            is_active=True,
        )
    )
    session.commit()
    assert assess_dataset_completeness(session) == "partial"


def test_assess_complete_after_full_sweep(session: Session):
    for i in range(EXPECTED_CATEGORY_SLICES):
        main = (i % 5) + 1
        deal = (i % 4) + 1
        session.add(
            Listing(
                hash_id=f"h{i}",
                category_main_cb=main,
                category_type_cb=deal,
                is_active=True,
            )
        )
    session.add(
        ScrapingRun(
            run_type=RunType.incremental,
            status=RunStatus.success,
            category="all",
            items_seen=105_000,
        )
    )
    session.commit()
    assert assess_dataset_completeness(session) == "complete"


def test_reconciliation_report_db_only(session: Session):
    session.add(
        Listing(hash_id="x1", category_main_cb=1, category_type_cb=1, is_active=True)
    )
    session.commit()
    report = build_count_reconciliation_report(session, sreality_totals=None)
    assert report.db_active_total == 1
    assert report.dataset_completeness == "partial"
    assert report.sreality_api_slice_sum is None
    assert report.active_category_slice_count == 1


def test_classify_slice_aligned():
    assert classify_slice_reconciliation(20109, 20185, scrape_in_progress=True) == "aligned"


def test_classify_slice_not_started_during_run():
    assert classify_slice_reconciliation(14716, 0, scrape_in_progress=True) == "not_started"


def test_classify_slice_missing_after_run():
    assert classify_slice_reconciliation(14716, 0, scrape_in_progress=False) == "missing"


def test_classify_slice_coverage_gap():
    assert classify_slice_reconciliation(10000, 9000, scrape_in_progress=False) == "coverage_gap"


def test_classify_slice_in_progress_partial_fetch():
    assert classify_slice_reconciliation(10000, 5000, scrape_in_progress=True) == "in_progress"


def test_assess_freshness_in_progress(session: Session):
    session.add(
        ScrapingRun(
            run_type=RunType.incremental,
            status=RunStatus.running,
            category="all",
            items_seen=1000,
        )
    )
    session.commit()
    assert assess_dataset_freshness(session) == "in_progress"
