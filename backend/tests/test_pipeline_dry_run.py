"""Controlled dry-run of the scraping pipeline against a real Postgres database.

This test does NOT hit the live sreality.cz API. Instead it monkeypatches
``SrealityClient.get_json`` to return fixture payloads shaped like the current
public API, while exercising every other line of real pipeline/ORM/DB code:
HTTP client retry wiring bypassed only at the transport boundary, parsing,
validation, deduplication, incremental diffing, price-history append,
delisting detection, and detail backfill all run for real against a real
database.
"""

import asyncio
import os
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.models import Listing, ListingDetail, PriceHistory, RunItemLog, ScrapingRun
from app.scraping import client as client_module
from app.scraping.constants import CATEGORY_COMBINATIONS
from app.scraping.pipeline import run_detail_backfill, run_incremental_scrape

DATABASE_URL = os.environ.get("VERIFY_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN to run this dry-run"
)


def make_list_estate(hash_id, name, price, category_main_cb=1, category_type_cb=1, category_sub_cb=4, lat=50.08, lon=14.43):
    return {
        "hash_id": hash_id,
        "advert_name": name,
        "category_main_cb": {"name": "Byty", "value": category_main_cb},
        "category_type_cb": {"name": "Prodej", "value": category_type_cb},
        "category_sub_cb": {"name": "2+kk", "value": category_sub_cb},
        "price_czk": price,
        "price_czk_m2": round(price / 50),
        "locality": {
            "city": "Praha",
            "citypart": "Vinohrady",
            "district": "Praha 2",
            "gps_lat": lat,
            "gps_lon": lon,
            "region": "Hlavní město Praha",
        },
        "advert_images": [],
    }


def make_detail_payload(hash_id):
    return {
        "result": {
            "hash_id": int(hash_id),
            "advert_description": f"Popis nabídky {hash_id}",
            "meta_description": "meta",
            "furnished": {"name": "Ne", "value": 2},
            "elevator": {"name": "Ano", "value": 1},
            "garden": True,
            "object_kind": {"name": "Byt", "value": 1},
            "building_type": {"name": "Cihlová", "value": 2},
            "building_condition": {"name": "Novostavba", "value": 6},
            "ownership": {"name": "Osobní", "value": 1},
            "parking_lots": 1,
            "terrace": False,
            "balcony": True,
            "loggia": False,
            "basin": False,
            "cellar": True,
            "garage": False,
            "low_energy": False,
            "easy_access": False,
            "energy_efficiency_rating_cb": {"name": "B - Velmi úsporná", "value": 2},
            "premise": {"name": "Test Reality s.r.o.", "ask_id": 123, "locality": {"gps_lat": 50.08, "gps_lon": 14.43}},
            "locality": {
                "district": "Praha 2",
                "district_id": 2,
                "ward_id": 3,
                "region": "Hlavní město Praha",
                "region_id": 4,
                "quarter_id": 5,
                "municipality_id": 6,
                "street_id": 1,
                "gps_lat": 50.08,
                "gps_lon": 14.43,
            },
            "usable_area": 65,
            "floor_area": 65,
            "land_area": 450,
            "floor_number": 3,
            "floors": 5,
            "edited": "2026-07-02",
            "advert_images": [],
            "items": [
                {"name": "Aktualizace", "value": "31.12.2025"},
            ],
        }
    }


def _query_param(url: str, key: str) -> str | None:
    return parse_qs(urlparse(url).query).get(key, [None])[0]


class FixtureClient:
    """Drop-in replacement for SrealityClient that serves canned responses
    instead of hitting the network, keyed by round number (mutated between
    scrape runs to simulate real-world changes over time)."""

    round = 1

    def __init__(self):
        self.consecutive_failures = 0

    async def aclose(self):
        pass

    async def get_json(self, url: str) -> dict:
        path = url.split("?")[0]
        if path.endswith("/search"):
            if "category_main_cb=1&category_type_cb=1" not in url:
                return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}

            offset = int(_query_param(url, "offset") or "0")
            per_page = int(_query_param(url, "per_page") or "100")
            if FixtureClient.round == 1:
                estates = [
                    make_list_estate("1001", "Prodej bytu 2+kk, Praha", 5_000_000),
                    make_list_estate("1002", "Prodej bytu 3+1, Praha", 7_500_000),
                    make_list_estate("1003", "Prodej bytu 1+kk, Praha", 3_200_000),
                ]
            else:
                # Round 2: 1001 price dropped (price history should append),
                # 1002 disappears (delisting), 1003 unchanged, 1004 is new.
                estates = [
                    make_list_estate("1001", "Prodej bytu 2+kk, Praha", 4_800_000),
                    make_list_estate("1003", "Prodej bytu 1+kk, Praha", 3_200_000),
                    make_list_estate("1004", "Prodej bytu 4+1, Praha", 9_000_000),
                ]

            start = offset
            result = estates[start : start + per_page]
            return {
                "pagination": {"limit": per_page, "offset": start, "total": len(estates)},
                "results": result,
                "search_title": "Byty k prodeji",
                "meta_title": "Prodej bytu • Sreality.cz",
                "meta_description": "meta",
                "status_code": 200,
                "status_message": "OK",
            }

        # Detail-fetch URLs (.../estates/{hash_id}) must be matched before the
        # other fallback below, since they don't carry category filters.
        if path.endswith("/estates/1004") or path.endswith("/estates/1003") or path.endswith("/estates/1002") or path.endswith("/estates/1001") or path.rsplit("/", 1)[-1].isdigit():
            hash_id = path.rsplit("/", 1)[-1]
            return make_detail_payload(hash_id)
        return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}


@pytest.fixture(autouse=True)
def patch_client(monkeypatch):
    monkeypatch.setattr(client_module, "SrealityClient", FixtureClient)
    import app.scraping.pipeline as pipeline_module
    monkeypatch.setattr(pipeline_module, "SrealityClient", FixtureClient)


@pytest.fixture()
def session():
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in ("runitemlog", "rawpayload", "pricehistory", "image", "listingdetail", "scrapingrun", "listing"):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    with Session(engine) as s:
        yield s


def test_full_scenario_insert_then_update_new_and_delist(session):
    _round_1_inserts_three_listings_with_details_and_no_duplicates(session)
    _round_2_detects_price_change_new_listing_and_delisting(session)


def _round_1_inserts_three_listings_with_details_and_no_duplicates(session):
    FixtureClient.round = 1
    run = asyncio.run(run_incremental_scrape(session, categories=CATEGORY_COMBINATIONS))

    assert run.status == "success"
    assert run.items_new == 3

    listings = session.exec(select(Listing)).all()
    assert len(listings) == 3
    hash_ids = {l.hash_id for l in listings}
    assert hash_ids == {"1001", "1002", "1003"}
    assert all(l.is_active for l in listings)

    # each new listing got exactly one price_history row and one detail row
    for listing in listings:
        history = session.exec(select(PriceHistory).where(PriceHistory.listing_id == listing.id)).all()
        assert len(history) == 1
        detail = session.exec(select(ListingDetail).where(ListingDetail.listing_id == listing.id)).first()
        assert detail is not None
        assert detail.usable_area == 65
        assert detail.land_area == 450
        assert detail.floor_number == 3
        assert detail.total_floors == 5
        assert detail.furnished == "2", "furnished_cb must persist as the raw code, not a bool cast of it"
        assert detail.elevator == "1"
        assert detail.garden is True
        assert detail.last_updated_at is not None and detail.last_updated_at.year == 2025

        assert listing.locality_text == "Praha 2 - Vinohrady"
        assert listing.seller_type == "realitni_kancelar", "broker_company was present in the fixture payload"


def _round_2_detects_price_change_new_listing_and_delisting(session):
    FixtureClient.round = 2
    run = asyncio.run(run_incremental_scrape(session, categories=CATEGORY_COMBINATIONS))

    assert run.status == "success"
    assert run.items_new == 1  # 1004
    assert run.items_updated == 1  # 1001 price change
    assert run.items_removed == 1  # 1002 gone

    listings = {l.hash_id: l for l in session.exec(select(Listing)).all()}
    assert set(listings.keys()) == {"1001", "1002", "1003", "1004"}, "no duplicate rows should be created for re-seen hash_ids"

    assert listings["1002"].is_active is False
    assert listings["1002"].removed_at is not None

    assert listings["1001"].is_active is True
    assert listings["1001"].price_czk == 4_800_000

    history_1001 = session.exec(
        select(PriceHistory).where(PriceHistory.listing_id == listings["1001"].id).order_by(PriceHistory.recorded_at)
    ).all()
    assert [h.price_czk for h in history_1001] == [5_000_000, 4_800_000]

    history_1003 = session.exec(select(PriceHistory).where(PriceHistory.listing_id == listings["1003"].id)).all()
    assert len(history_1003) == 1, "unchanged price must not create a spurious history row"

    # total listing count must equal 4, never re-inserted, confirming dedup by hash_id
    total_listings = session.exec(select(Listing)).all()
    assert len(total_listings) == 4


class _InvalidItemFixtureClient:
    """Standalone client (independent of FixtureClient's round-based global
    state) that returns one estate missing a required field, to exercise the
    RunItemLog validate-stage logging path."""

    async def aclose(self):
        pass

    async def get_json(self, url: str) -> dict:
        if path := url.split("?")[0]:
            if path.endswith("/search"):
                if "category_main_cb=1&category_type_cb=1" not in url:
                    return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}
                estates = [
                    make_list_estate("2001", "Prodej bytu, Praha", 4_000_000),
                    {"hash_id": "2002", "category_main_cb": {"value": 1}, "category_type_cb": {"value": 1}},  # missing title
                ]
                return {
                    "pagination": {"limit": 100, "offset": 0, "total": len(estates)},
                    "results": estates,
                    "search_title": "Byty k prodeji",
                    "meta_title": "Prodej bytu • Sreality.cz",
                    "status_code": 200,
                    "status_message": "OK",
                }
            if path.rsplit("/", 1)[-1].isdigit():
                return make_detail_payload(path.rsplit("/", 1)[-1])
        return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}


def test_invalid_list_item_is_logged_to_run_item_log(session, monkeypatch):
    monkeypatch.setattr(client_module, "SrealityClient", _InvalidItemFixtureClient)
    import app.scraping.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SrealityClient", _InvalidItemFixtureClient)

    run = asyncio.run(run_incremental_scrape(session, categories=CATEGORY_COMBINATIONS))

    assert run.error_count == 1
    logs = session.exec(select(RunItemLog).where(RunItemLog.run_id == run.id)).all()
    assert len(logs) == 1
    assert logs[0].stage == "validate"
    assert logs[0].hash_id == "2002"
    assert "hash_id=" in logs[0].message


class _DetailFailureFixtureClient:
    """Standalone client for run_detail_backfill: hash_id 3002's detail fetch
    raises, hash_id 3003's payload fails to parse (missing recommendations_data
    forces a KeyError-shaped failure via a deliberately broken shape). Verifies
    both (a) the failure is logged with the specific hash_id/reason and (b) a
    single bad item does not abort processing of the other listing_ids."""

    async def aclose(self):
        pass

    async def get_json(self, url: str) -> dict:
        hash_id = url.rsplit("/", 1)[-1]
        if hash_id == "3002":
            raise RuntimeError("simulated network failure")
        return make_detail_payload(hash_id)


def test_detail_backfill_isolates_failures_and_logs_them(session, monkeypatch):
    monkeypatch.setattr(client_module, "SrealityClient", _DetailFailureFixtureClient)
    import app.scraping.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SrealityClient", _DetailFailureFixtureClient)

    from datetime import datetime

    listings = [
        Listing(hash_id=h, title=f"Byt {h}", category_main_cb=1, category_type_cb=1, price_czk=1_000_000, first_seen_at=datetime.utcnow(), last_seen_at=datetime.utcnow())
        for h in ("3001", "3002", "3003")
    ]
    session.add_all(listings)
    session.commit()
    for listing in listings:
        session.refresh(listing)

    run = asyncio.run(run_detail_backfill(session, [l.id for l in listings]))

    # the one failing listing must not stop the other two from being processed.
    # Status is "partial", not "success" -- one item genuinely failed and that
    # must be visible to the operator, not silently reported as a clean run.
    assert run.status == "partial"
    assert run.error_count == 1
    assert run.items_seen == 2

    details = {d.listing_id: d for d in session.exec(select(ListingDetail)).all()}
    listings_by_hash = {l.hash_id: l for l in listings}
    assert listings_by_hash["3001"].id in details
    assert listings_by_hash["3003"].id in details
    assert listings_by_hash["3002"].id not in details

    logs = session.exec(select(RunItemLog).where(RunItemLog.run_id == run.id)).all()
    assert len(logs) == 1
    assert logs[0].hash_id == "3002"
    assert logs[0].stage == "detail_fetch"
    assert "simulated network failure" in logs[0].message


class _PageFailureFixtureClient:
    """3 total estates over 2 offset windows (via a monkeypatched scrape_per_page=2),
    with offset=2 always failing. Exercises the page_fetch logging path."""

    async def aclose(self):
        pass

    async def get_json(self, url: str) -> dict:
        if url.split("?")[0].endswith("/search"):
            if "category_main_cb=1&category_type_cb=1" not in url:
                return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}
            offset = int(_query_param(url, "offset") or "0")
            per_page = int(_query_param(url, "per_page") or "100")
            if offset == 2:
                raise RuntimeError("simulated page fetch failure")
            estates = [make_list_estate("4001", "Byt 1", 1_000_000), make_list_estate("4002", "Byt 2", 1_100_000)]
            return {
                "pagination": {"limit": per_page, "offset": offset, "total": 3},
                "results": estates[:per_page] if offset == 0 else estates[offset : offset + per_page],
                "search_title": "Byty k prodeji",
                "meta_title": "Prodej bytu • Sreality.cz",
                "status_code": 200,
                "status_message": "OK",
            }
        if url.split("?")[0].rsplit("/", 1)[-1].isdigit():
            return make_detail_payload(url.rsplit("/", 1)[-1])
        return {"pagination": {"limit": 100, "offset": 0, "total": 0}, "results": []}


def test_page_fetch_failure_is_logged_and_other_pages_still_processed(session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "scrape_per_page", 2)
    monkeypatch.setattr(client_module, "SrealityClient", _PageFailureFixtureClient)
    import app.scraping.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SrealityClient", _PageFailureFixtureClient)

    run = asyncio.run(run_incremental_scrape(session, categories=CATEGORY_COMBINATIONS))

    # page 2 failed, but page 1's 2 listings must still have been processed.
    # error_count is 2: one for the page_fetch failure itself, one for the
    # resulting coverage_gap (2 of 3 probed listings recovered) -- both are
    # independently useful signals, not a double-count of the same failure.
    assert run.error_count == 2
    listings = session.exec(select(Listing)).all()
    assert {l.hash_id for l in listings} == {"4001", "4002"}

    logs = session.exec(select(RunItemLog).where(RunItemLog.run_id == run.id)).all()
    assert len(logs) == 2
    logs_by_stage = {log.stage: log for log in logs}
    assert set(logs_by_stage) == {"page_fetch", "coverage_gap"}
    assert "offset2" in logs_by_stage["page_fetch"].hash_id
    assert "simulated page fetch failure" in logs_by_stage["page_fetch"].message
    assert "probed_total=3" in logs_by_stage["coverage_gap"].message
    assert "recovered=2" in logs_by_stage["coverage_gap"].message
