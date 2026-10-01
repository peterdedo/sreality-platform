"""Unit tests for cooperative scrape shutdown flag and pipeline behaviour."""

from __future__ import annotations

import asyncio
import os
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.models import Listing, ScrapingRun
from app.models.scraping_run import RunStatus
from app.scraping import client as client_module
from app.scraping.orphan_runs import (
    SHUTDOWN_PARTIAL_MESSAGE,
    clear_scrape_shutdown_request,
    is_scrape_shutdown_requested,
    request_scrape_shutdown,
)
from app.scraping.pipeline import run_detail_backfill, run_incremental_scrape
from tests.test_pipeline_dry_run import make_detail_payload, make_list_estate

DATABASE_URL = os.environ.get("VERIFY_DATABASE_URL")


@pytest.fixture(autouse=True)
def _reset_shutdown_flag():
    clear_scrape_shutdown_request()
    yield
    clear_scrape_shutdown_request()


def test_shutdown_flag_defaults_false_and_clears():
    assert is_scrape_shutdown_requested() is False
    request_scrape_shutdown()
    assert is_scrape_shutdown_requested() is True
    clear_scrape_shutdown_request()
    assert is_scrape_shutdown_requested() is False


def test_request_scrape_shutdown_is_idempotent():
    request_scrape_shutdown()
    request_scrape_shutdown()
    assert is_scrape_shutdown_requested() is True


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN")
def test_incremental_scrape_exits_partial_on_shutdown(monkeypatch):
    """After shutdown is requested mid-fetch, run ends as partial with clear message
    and does not chain detail backfill."""

    class _MultiCategoryClient:
        """Serves two non-empty category slices; requests shutdown after first page."""

        def __init__(self):
            self.search_calls = 0

        async def aclose(self):
            pass

        async def get_json(self, url: str) -> dict:
            path = url.split("?")[0]
            if path.endswith("/search"):
                self.search_calls += 1
                main = parse_qs(urlparse(url).query).get("category_main_cb", [None])[0]
                type_cb = parse_qs(urlparse(url).query).get("category_type_cb", [None])[0]
                # First category slice only (byty/prodej); others empty so fan-out is cheap.
                if main == "1" and type_cb == "1":
                    if self.search_calls >= 1:
                        request_scrape_shutdown()
                    estates = [
                        make_list_estate("9101", "Byt A", 1_000_000),
                        make_list_estate("9102", "Byt B", 2_000_000),
                    ]
                    return {
                        "pagination": {"limit": 100, "offset": 0, "total": len(estates)},
                        "results": estates,
                    }
                return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}
            if path.rsplit("/", 1)[-1].isdigit():
                return make_detail_payload(path.rsplit("/", 1)[-1])
            return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}

    monkeypatch.setattr(client_module, "SrealityClient", _MultiCategoryClient)
    import app.scraping.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SrealityClient", _MultiCategoryClient)

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in (
            "runitemlog",
            "rawpayload",
            "pricehistory",
            "image",
            "listingdetail",
            "scrapingrun",
            "listing",
        ):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))

    with Session(engine) as session:
        categories = [
            {"name": "Byty / Prodej", "category_main_cb": 1, "category_type_cb": 1},
            {"name": "Byty / Pronájem", "category_main_cb": 1, "category_type_cb": 2},
        ]
        run = asyncio.run(run_incremental_scrape(session, categories=categories))

        assert run.status == RunStatus.partial
        assert run.error_message == SHUTDOWN_PARTIAL_MESSAGE
        assert run.items_new >= 1

        # Chained backfill must not have run (would create a second ScrapingRun).
        runs = session.exec(select(ScrapingRun)).all()
        assert len(runs) == 1
        assert runs[0].id == run.id


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN")
def test_detail_backfill_exits_partial_on_shutdown(monkeypatch):
    class _DetailClient:
        def __init__(self):
            self.calls = 0

        async def aclose(self):
            pass

        async def get_json(self, url: str) -> dict:
            self.calls += 1
            if self.calls >= 1:
                request_scrape_shutdown()
            return make_detail_payload(url.rsplit("/", 1)[-1])

    monkeypatch.setattr(client_module, "SrealityClient", _DetailClient)
    import app.scraping.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SrealityClient", _DetailClient)

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in (
            "runitemlog",
            "rawpayload",
            "pricehistory",
            "image",
            "listingdetail",
            "scrapingrun",
            "listing",
        ):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))

    with Session(engine) as session:
        from datetime import datetime

        listings = [
            Listing(
                hash_id=str(9200 + i),
                title=f"t{i}",
                category_main_cb=1,
                category_type_cb=1,
                price_czk=1,
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                is_active=True,
            )
            for i in range(3)
        ]
        session.add_all(listings)
        session.commit()
        ids = [session.refresh(x) or x.id for x in listings]

        run = asyncio.run(run_detail_backfill(session, ids))
        assert run.status == RunStatus.partial
        assert run.error_message == SHUTDOWN_PARTIAL_MESSAGE
        # Finished current item, then stopped — at most one full detail.
        assert run.items_seen <= 1
