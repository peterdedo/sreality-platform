"""Real-database integration test for GET /listings' new joins, filters,
sorting, and serve-time-computed fields (price_per_m2, days_on_market,
price_change_count, has_price_drop, image_count, description_length).

Seeds Listing/ListingDetail/Location/PriceHistory/Image rows directly and
drives the endpoint through FastAPI's TestClient with a real Postgres session,
same VERIFY_DATABASE_URL convention as test_pipeline_dry_run.py.
"""

import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.models import Image, Listing, ListingDetail, Location, PriceHistory

LISTINGS_PATH = f"{settings.api_prefix}/listings"

DATABASE_URL = os.environ.get("VERIFY_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN to run this integration test"
)


@pytest.fixture()
def session():
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in ("rawpayload", "pricehistory", "image", "listingdetail", "location", "scrapingrun", "listing"):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(session):
    def _get_session_override():
        yield session

    app.dependency_overrides[get_session] = _get_session_override
    # Deliberately not using `with TestClient(app) as c:` here -- that triggers
    # app.main's lifespan (init_db + start_scheduler), and APScheduler's
    # background thread outlives the sync TestClient's event loop, crashing
    # later tests with "Event loop is closed". These tests only need the
    # router + our overridden session, not the scheduler.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed(session):
    now = datetime.utcnow()

    location_praha = Location(region="Hlavní město Praha", district="Praha 5", municipality="Praha")
    location_brno = Location(region="Jihomoravský kraj", district="Brno-město", municipality="Brno")
    session.add(location_praha)
    session.add(location_brno)
    session.commit()
    session.refresh(location_praha)
    session.refresh(location_brno)

    cheap = Listing(
        hash_id="cheap-1",
        title="Malý byt Praha",
        category_main_cb=1,
        category_type_cb=1,
        category_sub_cb=4,
        price_czk=3_000_000,
        is_active=True,
        first_seen_at=now - timedelta(days=5),
        last_seen_at=now,
        locality_text="Praha 5 - Smíchov",
        location_id=location_praha.id,
    )
    dropped = Listing(
        hash_id="dropped-1",
        title="Velký dům Brno se slevou",
        category_main_cb=2,
        category_type_cb=1,
        category_sub_cb=37,
        price_czk=8_000_000,
        is_active=True,
        first_seen_at=now - timedelta(days=40),
        last_seen_at=now,
        locality_text="Brno - střed",
        location_id=location_brno.id,
    )
    session.add_all([cheap, dropped])
    session.commit()
    session.refresh(cheap)
    session.refresh(dropped)

    session.add(ListingDetail(listing_id=cheap.id, usable_area=40, ownership="1", furnished="1", elevator="2"))
    session.add(ListingDetail(listing_id=dropped.id, usable_area=200, ownership="2", furnished="2", elevator="1"))

    session.add(PriceHistory(listing_id=cheap.id, price_czk=3_000_000, recorded_at=now - timedelta(days=5)))
    session.add(PriceHistory(listing_id=dropped.id, price_czk=9_500_000, recorded_at=now - timedelta(days=40)))
    session.add(PriceHistory(listing_id=dropped.id, price_czk=8_000_000, recorded_at=now - timedelta(days=1)))

    session.add(Image(listing_id=cheap.id, url="https://example.com/1.jpg", position=0))
    session.add(Image(listing_id=dropped.id, url="https://example.com/2.jpg", position=0))
    session.add(Image(listing_id=dropped.id, url="https://example.com/3.jpg", position=1))

    session.commit()
    return cheap, dropped


def test_default_listing_returns_all_joined_and_computed_fields(client, session):
    cheap, dropped = _seed(session)

    resp = client.get(LISTINGS_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2

    by_id = {item["id"]: item for item in body["items"]}
    assert by_id[cheap.id]["usable_area"] == 40
    assert by_id[cheap.id]["price_per_m2"] == 75_000
    assert by_id[cheap.id]["ownership"] == "Osobní"
    assert by_id[cheap.id]["image_count"] == 1
    assert by_id[cheap.id]["price_change_count"] == 0
    assert by_id[cheap.id]["has_price_drop"] is False
    assert by_id[cheap.id]["locality_text"] == "Praha 5 - Smíchov"
    assert by_id[cheap.id]["region"] == "Hlavní město Praha"

    assert by_id[dropped.id]["image_count"] == 2
    assert by_id[dropped.id]["price_change_count"] == 1
    assert by_id[dropped.id]["has_price_drop"] is True
    assert by_id[dropped.id]["days_on_market"] >= 39


@pytest.mark.parametrize("page_size", [1, 25, 200, 1000])
def test_listings_returns_200_for_the_page_sizes_the_frontend_uses(client, session, page_size):
    """Regression guard for the reported /listings 500s. Surfaces that call
    bulk listing fetch paginate at up to max_listings_page_size (1000); Nabídky
    uses 25; Přehled uses 1 for total count only."""
    _seed(session)
    resp = client.get(LISTINGS_PATH, params={"page": 1, "page_size": page_size, "is_active": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["page_size"] == page_size
    assert body["total"] == 2
    assert len(body["items"]) == min(2, page_size)


def test_has_price_drop_filter(client, session):
    cheap, dropped = _seed(session)

    resp = client.get(LISTINGS_PATH, params={"has_price_drop": True})
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert ids == {dropped.id}


def test_usable_area_and_price_per_m2_filters(client, session):
    cheap, dropped = _seed(session)

    resp = client.get(LISTINGS_PATH, params={"usable_area_min": 100})
    assert {item["id"] for item in resp.json()["items"]} == {dropped.id}

    # cheap is 3M/40m2=75000/m2, dropped is 8M/200m2=40000/m2 -- a floor of
    # 50000 keeps only cheap.
    resp = client.get(LISTINGS_PATH, params={"price_per_m2_min": 50_000})
    assert {item["id"] for item in resp.json()["items"]} == {cheap.id}


def test_ownership_furnished_elevator_and_location_filters(client, session):
    cheap, dropped = _seed(session)

    resp = client.get(LISTINGS_PATH, params={"ownership": "2"})
    assert {item["id"] for item in resp.json()["items"]} == {dropped.id}

    resp = client.get(LISTINGS_PATH, params={"furnished": "1"})
    assert {item["id"] for item in resp.json()["items"]} == {cheap.id}

    resp = client.get(LISTINGS_PATH, params={"elevator": "1"})
    assert {item["id"] for item in resp.json()["items"]} == {dropped.id}

    resp = client.get(LISTINGS_PATH, params={"city": "Brno"})
    assert {item["id"] for item in resp.json()["items"]} == {dropped.id}

    resp = client.get(LISTINGS_PATH, params={"district": "Praha 5"})
    assert {item["id"] for item in resp.json()["items"]} == {cheap.id}


def test_search_filter_matches_title_and_locality(client, session):
    cheap, dropped = _seed(session)

    resp = client.get(LISTINGS_PATH, params={"search": "slevou"})
    assert {item["id"] for item in resp.json()["items"]} == {dropped.id}

    resp = client.get(LISTINGS_PATH, params={"search": "Smíchov"})
    assert {item["id"] for item in resp.json()["items"]} == {cheap.id}

    resp = client.get(LISTINGS_PATH, params={"search": "Praha 5"})
    assert {item["id"] for item in resp.json()["items"]} == {cheap.id}

    resp = client.get(LISTINGS_PATH, params={"search": "Hlavní město Praha"})
    assert {item["id"] for item in resp.json()["items"]} == {cheap.id}


def test_location_suggest_endpoint(client, session):
    _seed(session)
    resp = client.get(f"{LISTINGS_PATH}/location-suggest", params={"q": "Pra"})
    assert resp.status_code == 200
    labels = {item["label"] for item in resp.json()["items"]}
    assert any("Praha" in label for label in labels)


def test_sort_by_price_per_m2(client, session):
    cheap, dropped = _seed(session)

    resp = client.get(LISTINGS_PATH, params={"sort_by": "price_per_m2", "sort_dir": "desc"})
    ids = [item["id"] for item in resp.json()["items"]]
    assert ids == [cheap.id, dropped.id]  # cheap has higher price/m2 (75000 vs 40000)


def test_invalid_sort_by_returns_400(client, session):
    _seed(session)
    resp = client.get(LISTINGS_PATH, params={"sort_by": "not_a_real_column"})
    assert resp.status_code == 400


def test_listing_detail_endpoint_returns_enriched_listing(client, session):
    cheap, _dropped = _seed(session)

    resp = client.get(f"{LISTINGS_PATH}/{cheap.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["listing"]["usable_area"] == 40
    assert body["listing"]["ownership"] == "Osobní"
    assert body["ownership"] == "Osobní"
    assert body["images"] == ["https://example.com/1.jpg"]
