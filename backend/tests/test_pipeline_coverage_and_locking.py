"""Real-database tests for the coverage-completeness and concurrency-safety
fixes: two-dimensional (region + subcategory) fan-out with explicit gap
logging, advisory-lock guards against concurrent sweeps/backfills, and the
resumable/idempotent missing-detail backfill.

Root cause this guards against: a stale/second backend process ran a sweep
concurrently with another and marked 14 389 freshly-scraped listings as
removed. See app/scraping/pipeline.py's _SWEEP_LOCK_ID docstring.
"""

import asyncio
import os
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.models import Listing, ListingDetail, RunItemLog, ScrapingRun
from app.scraping import client as client_module
from app.scraping.locks import BACKFILL_LOCK_ID, SWEEP_LOCK_ID
from app.scraping.pipeline import (
    _release_lock,
    _try_acquire_lock,
    run_incremental_scrape,
    run_missing_detail_backfill,
)

DATABASE_URL = os.environ.get("VERIFY_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN to run this dry-run"
)


def _query_param(url: str, key: str) -> str | None:
    return parse_qs(urlparse(url).query).get(key, [None])[0]


def _make_estate(hash_id: str) -> dict:
    return {
        "hash_id": hash_id,
        "advert_name": f"Byt {hash_id}",
        "category_main_cb": {"name": "Byty", "value": 1},
        "category_type_cb": {"name": "Prodej", "value": 1},
        "category_sub_cb": {"name": "2+kk", "value": 4},
        "price_czk": 1_000_000,
        "price_czk_m2": 20_000,
        "locality": {"city": "Praha", "region": "Hlavní město Praha"},
        "advert_images": [],
    }


class _SplitCoverageFixtureClient:
    """Simulates an over-cap category where NEITHER a region filter NOR a
    subcategory filter alone recovers every listing, but their union does --
    exactly the real-world byty/pozemky/domy shape found on the live API.
    Total probed = 5; region=1 returns {a,b}; sub=4 returns {b,c,d}; hash e is
    unreachable by either filter (models a residual real-world gap)."""

    async def aclose(self):
        pass

    async def get_json(self, url: str) -> dict:
        if not url.split("?")[0].endswith("/search"):
            return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}
        if "category_main_cb=1&category_type_cb=1" not in url:
            return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}

        region = _query_param(url, "locality_region_id")
        sub = _query_param(url, "category_sub_cb")
        offset = int(_query_param(url, "offset") or "0")

        if region is None and sub is None:
            # unfiltered probe call
            return {"pagination": {"limit": 100, "offset": 0, "total": 5}, "results": []}
        if region == "1":
            ids = ["a", "b"]
        elif sub == "4":
            ids = ["b", "c", "d"]
        else:
            ids = []

        if offset > 0:
            return {"pagination": {"limit": 100, "offset": offset, "total": len(ids)}, "results": []}
        return {
            "pagination": {"limit": 100, "offset": 0, "total": len(ids)},
            "results": [_make_estate(h) for h in ids],
        }


@pytest.fixture()
def session():
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in ("runitemlog", "rawpayload", "pricehistory", "image", "listingdetail", "scrapingrun", "listing"):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    with Session(engine) as s:
        # Make sure no advisory lock leaks in from a prior failed test run in
        # the same backend connection pool.
        s.execute(text("SELECT pg_advisory_unlock_all()"))
        s.commit()
        yield s


def test_two_dimensional_fanout_unions_region_and_subcategory(session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "scrape_offset_cap", 3)  # force fan-out with only 5 probed
    monkeypatch.setattr(client_module, "SrealityClient", _SplitCoverageFixtureClient)
    import app.scraping.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SrealityClient", _SplitCoverageFixtureClient)
    monkeypatch.setattr(pipeline_module, "CZECH_REGION_IDS", [1])
    monkeypatch.setattr(pipeline_module, "SUBCATEGORIES_BY_MAIN", {1: [4]})

    category = {"name": "byt - prodej", "category_main_cb": 1, "category_type_cb": 1}
    run = ScrapingRun(run_type="incremental")
    session.add(run)
    session.commit()
    session.refresh(run)

    estates, _pages = asyncio.run(pipeline_module._fetch_category_estates(pipeline_module.SrealityClient(), category, session, run))
    session.commit()

    # region={a,b} UNION sub={b,c,d} = {a,b,c,d} -- "e" is unreachable by
    # either filter, matching the real API's residual gap shape.
    assert {e["hash_id"] for e in estates} == {"a", "b", "c", "d"}

    logs = session.exec(select(RunItemLog).where(RunItemLog.run_id == run.id)).all()
    gap_logs = [log for log in logs if log.stage == "coverage_gap"]
    assert len(gap_logs) == 1
    assert "probed_total=5" in gap_logs[0].message
    assert "recovered=4" in gap_logs[0].message
    assert "gap=1" in gap_logs[0].message
    assert run.error_count == 1


class _ThirdLevelFanoutFixtureClient:
    """Simulates the exact rodinné-domy shape found live: the category is
    over cap (probed=6, cap=3), AND its one subcategory is *itself* over cap
    when queried alone (sub=4 probed=6, still > cap=3), so a flat sub-only
    query would truncate. Region-only recovers {a,b,c}; sub=4 split by region
    recovers {c,d,e}; "f" is reachable by neither (models the residual
    no-resolvable-region gap found live). No real network calls -- this is a
    pure fixture, not a lock/session test, so no separate-session concern
    applies here."""

    async def aclose(self):
        pass

    async def get_json(self, url: str) -> dict:
        if not url.split("?")[0].endswith("/search"):
            return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}
        if "category_main_cb=1&category_type_cb=1" not in url:
            return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}

        region = _query_param(url, "locality_region_id")
        sub = _query_param(url, "category_sub_cb")
        offset = int(_query_param(url, "offset") or "0")

        if region is None and sub is None:
            return {"pagination": {"limit": 100, "offset": 0, "total": 6}, "results": []}
        if sub is None and region == "1":
            ids = ["a", "b"]
        elif sub is None and region == "2":
            ids = ["c"]
        elif sub == "4" and region is None:
            # sub-only probe call: must report over-cap so the third level
            # triggers, even though this exact query is never fetched for rows.
            return {"pagination": {"limit": 100, "offset": 0, "total": 6}, "results": []}
        elif sub == "4" and region == "1":
            ids = ["c", "d"]
        elif sub == "4" and region == "2":
            ids = ["e"]
        else:
            ids = []

        if offset > 0:
            return {"pagination": {"limit": 100, "offset": offset, "total": len(ids)}, "results": []}
        return {
            "pagination": {"limit": 100, "offset": 0, "total": len(ids)},
            "results": [_make_estate(h) for h in ids],
        }


def test_third_level_fanout_splits_over_cap_subcategory_by_region(session, monkeypatch):
    """The rodinné-domy scenario: a subcategory that is itself over cap must
    be split by region instead of fetched as one truncated query. Reproduces
    the live-confirmed shape (region-only and sub-only each miss listings the
    other catches) one level deeper, plus a residual gap neither reaches."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "scrape_offset_cap", 3)
    monkeypatch.setattr(client_module, "SrealityClient", _ThirdLevelFanoutFixtureClient)
    import app.scraping.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SrealityClient", _ThirdLevelFanoutFixtureClient)
    monkeypatch.setattr(pipeline_module, "CZECH_REGION_IDS", [1, 2])
    monkeypatch.setattr(pipeline_module, "SUBCATEGORIES_BY_MAIN", {1: [4]})

    category = {"name": "dům - prodej", "category_main_cb": 1, "category_type_cb": 1}
    run = ScrapingRun(run_type="incremental")
    session.add(run)
    session.commit()
    session.refresh(run)

    estates, _pages = asyncio.run(
        pipeline_module._fetch_category_estates(pipeline_module.SrealityClient(), category, session, run)
    )
    session.commit()

    # region{a,b,c} UNION sub4xregion{c,d,e} = {a,b,c,d,e}; "f" is reachable
    # by neither a region-only nor a sub-x-region query (residual gap).
    assert {e["hash_id"] for e in estates} == {"a", "b", "c", "d", "e"}

    logs = session.exec(select(RunItemLog).where(RunItemLog.run_id == run.id)).all()
    gap_logs = [log for log in logs if log.stage == "coverage_gap"]
    assert len(gap_logs) == 1
    assert "probed_total=6" in gap_logs[0].message
    assert "recovered=5" in gap_logs[0].message
    assert "gap=1" in gap_logs[0].message
    assert run.error_count == 1


def test_sweep_lock_prevents_concurrent_delisting(session):
    """Simulates the exact incident this fix targets: a second sweep must not
    be able to run its delisting pass while another sweep holds the lock."""
    # Seed one active listing that a colliding sweep might otherwise delist.
    from datetime import datetime

    listing = Listing(
        hash_id="preexisting",
        title="t",
        category_main_cb=1,
        category_type_cb=1,
        price_czk=1,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
        is_active=True,
    )
    session.add(listing)
    session.commit()

    # pg_advisory_lock is scoped to the DB session/connection that acquired
    # it, and is reentrant *within* that same session -- acquiring it on
    # `session` and then calling run_incremental_scrape(session) would not
    # actually simulate contention (the same connection is allowed to
    # "re-acquire" its own lock), and the call would fall through to real
    # network requests instead of being blocked. A second, independent
    # connection is required to model what a second backend process does.
    other_engine = create_engine(DATABASE_URL)
    with Session(other_engine) as other_session:
        assert _try_acquire_lock(other_session, SWEEP_LOCK_ID) is True
        try:
            run = asyncio.run(run_incremental_scrape(session))
            assert run.status == "failed"
            assert "přeskočen" in run.error_message
            assert run.items_removed == 0  # delisting pass never ran

            session.refresh(listing)
            assert listing.is_active is True  # not corrupted by the blocked run
        finally:
            _release_lock(other_session, SWEEP_LOCK_ID)


def test_backfill_lock_prevents_concurrent_backfill(session):
    # See test_sweep_lock_prevents_concurrent_delisting: must be a genuinely
    # separate connection, not the same session, to simulate a second process.
    other_engine = create_engine(DATABASE_URL)
    with Session(other_engine) as other_session:
        assert _try_acquire_lock(other_session, BACKFILL_LOCK_ID) is True
        try:
            run = asyncio.run(run_missing_detail_backfill(session))
            assert run.status == "failed"
            assert "přeskočen" in run.error_message
        finally:
            _release_lock(other_session, BACKFILL_LOCK_ID)


def test_missing_detail_backfill_is_idempotent(session, monkeypatch):
    from datetime import datetime

    from tests.test_pipeline_dry_run import make_detail_payload

    class _DetailFixtureClient:
        async def aclose(self):
            pass

        async def get_json(self, url: str) -> dict:
            hash_id = url.rsplit("/", 1)[-1]
            return make_detail_payload(hash_id)

    monkeypatch.setattr(client_module, "SrealityClient", _DetailFixtureClient)
    import app.scraping.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SrealityClient", _DetailFixtureClient)

    has_detail = Listing(
        hash_id="5001", title="t", category_main_cb=1, category_type_cb=1, price_czk=1,
        first_seen_at=datetime.utcnow(), last_seen_at=datetime.utcnow(), is_active=True,
    )
    missing_detail = Listing(
        hash_id="5002", title="t", category_main_cb=1, category_type_cb=1, price_czk=1,
        first_seen_at=datetime.utcnow(), last_seen_at=datetime.utcnow(), is_active=True,
    )
    session.add_all([has_detail, missing_detail])
    session.commit()
    session.refresh(has_detail)
    session.refresh(missing_detail)
    session.add(ListingDetail(listing_id=has_detail.id, usable_area=50))
    session.commit()

    run1 = asyncio.run(run_missing_detail_backfill(session))
    assert run1.status == "success"
    assert run1.items_seen == 1  # only the listing that was missing a detail

    details = session.exec(select(ListingDetail)).all()
    assert len(details) == 2  # one pre-existing + one newly backfilled
    assert {d.listing_id for d in details} == {has_detail.id, missing_detail.id}

    # Re-running with nothing left to backfill must be a safe no-op, not an
    # error and not a duplicate ListingDetail row.
    run2 = asyncio.run(run_missing_detail_backfill(session))
    assert run2.status == "success"
    assert run2.items_seen == 0
    assert len(session.exec(select(ListingDetail)).all()) == 2
