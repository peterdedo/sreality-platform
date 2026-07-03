"""Analytics aggregation coverage tests (real Postgres when VERIFY_DATABASE_URL is set)."""

import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.analytics.queries import UNKNOWN_REGION, dataset_summary, inventory_by_region, price_drops
from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.models import Listing, Location

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
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_inventory_by_region_counts_listings_without_location(session):
    now = datetime.utcnow()
    located = Listing(
        hash_id="with-region",
        title="S krajem",
        category_main_cb=1,
        category_type_cb=1,
        is_active=True,
        resolved_region_name="Karlovarský kraj",
        resolved_region_id=5,
        region_source="gps_polygon",
        first_seen_at=now,
        last_seen_at=now,
    )
    orphan = Listing(
        hash_id="without-region",
        title="Bez kraje",
        category_main_cb=1,
        category_type_cb=1,
        is_active=True,
        region_source="unknown",
        region_unknown_reason="no_detail_no_region_no_gps",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add_all([located, orphan])
    session.commit()

    rows = {row["region"]: row["listing_count"] for row in inventory_by_region(session)}
    assert rows["Karlovarský kraj"] == 1
    assert rows[UNKNOWN_REGION] == 1


def test_dataset_summary_reports_coverage(session):
    now = datetime.utcnow()
    session.add(
        Listing(
            hash_id="gps-1",
            title="A",
            category_main_cb=1,
            category_type_cb=1,
            is_active=True,
            gps_lat=50.0755,
            gps_lon=14.4378,
            resolved_region_name="Hlavní město Praha",
            resolved_region_id=1,
            region_source="gps_polygon",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    session.commit()

    summary = dataset_summary(session)
    assert summary["active_listing_count"] == 1
    assert summary["active_with_gps_count"] == 1
    assert summary["active_without_region_count"] == 0
    assert summary["active_with_region_count"] == 1


def test_price_drops_returns_total_matched(session):
    result = price_drops(session, min_drop_pct=5.0, limit=None)
    assert "items" in result
    assert "total_matched" in result
    assert result["total_matched"] == len(result["items"])


def test_inventory_by_region_uses_resolved_region_not_location(session):
    """Analytics must bucket by resolved_region_name, not Location.region."""
    now = datetime.utcnow()
    location = Location(region="Wrong Raw Region")
    session.add(location)
    session.commit()
    session.refresh(location)

    listing = Listing(
        hash_id="resolved-wins",
        title="Resolved",
        category_main_cb=1,
        category_type_cb=1,
        is_active=True,
        location_id=location.id,
        resolved_region_name="Jihomoravský kraj",
        resolved_region_id=11,
        region_source="gps_polygon",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(listing)
    session.commit()

    rows = {row["region"]: row["listing_count"] for row in inventory_by_region(session)}
    assert "Wrong Raw Region" not in rows
    assert rows["Jihomoravský kraj"] == 1


def test_dataset_summary_endpoint(client, session):
    resp = client.get(f"{settings.api_prefix}/analytics/dataset-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "active_listing_count" in body
