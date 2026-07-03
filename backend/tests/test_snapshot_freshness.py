"""Tests for snapshot freshness metadata and post-run transitions."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Listing, ScrapingRun
from app.models.scraping_run import RunStatus, RunType
from app.scraping.count_reconciliation import (
    EXPECTED_CATEGORY_SLICES,
    assess_dataset_completeness,
    assess_dataset_freshness,
    classify_slice_reconciliation,
)
from app.scraping.snapshot_metadata import (
    is_count_final,
    safe_to_compare_with_sreality_total,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_freshness_empty(session: Session):
    assert assess_dataset_freshness(session) == "empty"
    assert not is_count_final("empty")
    assert not safe_to_compare_with_sreality_total("empty")


def test_freshness_in_progress_overrides_complete(session: Session):
    for i in range(EXPECTED_CATEGORY_SLICES):
        session.add(
            Listing(
                hash_id=f"h{i}",
                category_main_cb=(i % 5) + 1,
                category_type_cb=(i % 4) + 1,
                is_active=True,
            )
        )
    session.add(
        ScrapingRun(
            run_type=RunType.incremental,
            status=RunStatus.running,
            category="all",
            items_seen=100_000,
        )
    )
    session.commit()
    assert assess_dataset_freshness(session) == "in_progress"
    assert not is_count_final("in_progress")
    assert not safe_to_compare_with_sreality_total("in_progress")


def test_freshness_final_complete_after_successful_sweep(session: Session):
    for i in range(EXPECTED_CATEGORY_SLICES):
        session.add(
            Listing(
                hash_id=f"h{i}",
                category_main_cb=(i % 5) + 1,
                category_type_cb=(i % 4) + 1,
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
    assert assess_dataset_freshness(session) == "final_complete"
    assert is_count_final("final_complete")
    assert safe_to_compare_with_sreality_total("final_complete")


def test_freshness_final_partial_without_full_sweep(session: Session):
    session.add(Listing(hash_id="a", category_main_cb=1, category_type_cb=1, is_active=True))
    session.commit()
    assert assess_dataset_freshness(session) == "final_partial"
    assert is_count_final("final_partial")
    assert not safe_to_compare_with_sreality_total("final_partial")


def test_post_run_transition_running_to_final(session: Session):
    session.add(Listing(hash_id="a", category_main_cb=1, category_type_cb=1, is_active=True))
    run = ScrapingRun(
        run_type=RunType.incremental,
        status=RunStatus.running,
        category="all",
        items_seen=1,
    )
    session.add(run)
    session.commit()
    assert assess_dataset_freshness(session) == "in_progress"

    run.status = RunStatus.success
    session.add(run)
    session.commit()
    assert assess_dataset_freshness(session) == "final_partial"


def test_classify_coverage_gap_only_after_processing():
    assert classify_slice_reconciliation(10_000, 9_000, scrape_in_progress=False) == "coverage_gap"
    assert classify_slice_reconciliation(10_000, 0, scrape_in_progress=False) == "missing"
    assert classify_slice_reconciliation(10_000, 0, scrape_in_progress=True) == "not_started"


def test_classify_not_started_not_missing_during_run():
    assert classify_slice_reconciliation(14_716, 0, scrape_in_progress=True) == "not_started"
    assert classify_slice_reconciliation(14_716, 0, scrape_in_progress=False) == "missing"
