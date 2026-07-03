"""Unit tests for app/domain/export.py's serialization (no DB needed) plus a
real-database integration test for the export endpoints, same
VERIFY_DATABASE_URL convention as test_listings_api.py.
"""

import io
import json
import os
from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.domain.export import SUPPORTED_FORMATS, serialize_rows

DATABASE_URL = os.environ.get("VERIFY_DATABASE_URL")


def test_csv_has_utf8_bom_and_preserves_diacritics():
    content, media_type, filename = serialize_rows([{"lokalita": "Praha 5 - Smíchov"}], "csv", "test")
    assert content.startswith(b"\xef\xbb\xbf")
    assert media_type == "text/csv; charset=utf-8"
    assert filename == "test.csv"
    decoded = content.decode("utf-8-sig")
    assert "Smíchov" in decoded


def test_json_does_not_escape_unicode():
    content, _, _ = serialize_rows([{"lokalita": "Brno-střed"}], "json", "test")
    decoded = content.decode("utf-8")
    assert "Brno-střed" in decoded  # not ř escape
    assert json.loads(decoded)[0]["lokalita"] == "Brno-střed"


def test_json_serializes_datetimes_as_iso():
    content, _, _ = serialize_rows([{"first_seen_at": datetime(2026, 1, 1, 12, 0)}], "json", "test")
    parsed = json.loads(content)
    assert parsed[0]["first_seen_at"] == "2026-01-01T12:00:00"


def test_xlsx_roundtrips_via_pandas():
    content, media_type, filename = serialize_rows([{"cena": 5_000_000, "lokalita": "Praha"}], "xlsx", "test")
    assert filename == "test.xlsx"
    df = pd.read_excel(io.BytesIO(content))
    assert df.iloc[0]["cena"] == 5_000_000
    assert df.iloc[0]["lokalita"] == "Praha"


def test_parquet_roundtrips_via_pandas():
    content, _, filename = serialize_rows([{"cena": 5_000_000}], "parquet", "test")
    assert filename == "test.parquet"
    df = pd.read_parquet(io.BytesIO(content))
    assert df.iloc[0]["cena"] == 5_000_000


def test_nan_values_become_null_not_literal_nan_token():
    """Regression: pandas produces float('nan') for missing values (e.g. the
    first row of a pct_change() series), and float('nan') is not valid JSON --
    json.dumps emits a bare NaN token that strict parsers reject. Caught via
    a live /api/export/analytics/timeseries check during manual verification."""
    rows = [{"mom_change_pct": float("nan"), "lokalita": "Praha"}]
    content, _, _ = serialize_rows(rows, "json", "test")
    parsed = json.loads(content)  # must not raise, and must not contain "NaN"
    assert parsed[0]["mom_change_pct"] is None
    assert b"NaN" not in content


def test_unsupported_format_raises():
    with pytest.raises(ValueError):
        serialize_rows([{"a": 1}], "xml", "test")


def test_empty_rows_produce_valid_empty_outputs():
    for fmt in SUPPORTED_FORMATS:
        content, _, _ = serialize_rows([], fmt, "empty")
        assert isinstance(content, bytes)


# --- Real-database integration tests for the export endpoints ---

pytestmark_db = pytest.mark.skipif(
    not DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN to run this integration test"
)


@pytest.fixture()
def db_session():
    if not DATABASE_URL:
        pytest.skip("VERIFY_DATABASE_URL not set")
    from app.models import Image, Listing, ListingDetail, Location, PriceHistory

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in ("rawpayload", "pricehistory", "image", "listingdetail", "location", "scrapingrun", "listing"):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    with Session(engine) as s:
        yield s


@pytest.fixture()
def api_client(db_session):
    from app.core.db import get_session
    from app.main import app

    def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    # See test_listings_api.py: avoid triggering app.main's lifespan (scheduler)
    # under TestClient, which crashes across tests with "Event loop is closed".
    # Export endpoints are now API-key guarded (T1), so send the key by default.
    from app.core.config import settings

    yield TestClient(app, headers={"X-API-Key": settings.api_key})
    app.dependency_overrides.clear()


def _seed_listing(session, **overrides):
    from app.models import Listing, ListingDetail

    now = datetime.utcnow()
    defaults = dict(
        hash_id="export-1",
        title="Byt Praha 5 - Smíchov",
        category_main_cb=1,
        category_type_cb=1,
        category_sub_cb=4,
        price_czk=5_000_000,
        is_active=True,
        first_seen_at=now - timedelta(days=10),
        last_seen_at=now,
        locality_text="Praha 5 - Smíchov",
    )
    defaults.update(overrides)
    listing = Listing(**defaults)
    session.add(listing)
    session.commit()
    session.refresh(listing)
    session.add(ListingDetail(listing_id=listing.id, usable_area=50, ownership="1"))
    session.commit()
    return listing


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to run")
def test_export_listings_raw_csv(api_client, db_session):
    _seed_listing(db_session)
    resp = api_client.get("/api/export/listings", params={"scope": "raw", "format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.content.decode("utf-8-sig")
    assert "Smíchov" in body
    assert "ownership_cb" in body  # raw scope uses raw codes, not translated labels


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to run")
def test_export_listings_cleaned_json_has_translated_labels(api_client, db_session):
    _seed_listing(db_session)
    resp = api_client.get("/api/export/listings", params={"scope": "cleaned", "format": "json"})
    assert resp.status_code == 200
    rows = json.loads(resp.content)
    assert rows[0]["ownership"] == "Osobní"  # translated via codebooks, not raw "1"
    assert rows[0]["price_per_m2"] == 100_000  # 5_000_000 / 50


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to run")
def test_export_listings_honors_filters(api_client, db_session):
    _seed_listing(db_session, hash_id="a", price_czk=3_000_000, first_seen_at=datetime.utcnow())
    resp = api_client.get("/api/export/listings", params={"scope": "cleaned", "format": "json", "price_min": 4_000_000})
    rows = json.loads(resp.content)
    assert rows == []


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to run")
def test_export_invalid_format_returns_400(api_client, db_session):
    resp = api_client.get("/api/export/listings", params={"format": "xml"})
    assert resp.status_code == 400


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to run")
def test_export_timeseries_empty_db_returns_empty(api_client, db_session):
    resp = api_client.get("/api/export/analytics/timeseries", params={"format": "json"})
    assert resp.status_code == 200
    assert json.loads(resp.content) == []


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to run")
def test_export_timeseries_computes_derived_fields(api_client, db_session):
    from app.models.analytic_snapshot import AnalyticSnapshot

    base_date = datetime.utcnow().date() - timedelta(days=60)
    for i, price_per_m2 in enumerate([80_000, 88_000, 96_000]):
        db_session.add(
            AnalyticSnapshot(
                snapshot_date=base_date + timedelta(days=i * 20),
                location_id=None,
                category_main_cb=1,
                category_type_cb=1,
                listing_count=10,
                avg_price_czk=price_per_m2 * 50,
                avg_price_per_m2=price_per_m2,
                new_count=2,
                avg_days_on_market=30,
            )
        )
    db_session.commit()

    resp = api_client.get("/api/export/analytics/timeseries", params={"format": "json", "days": 90})
    assert resp.status_code == 200
    rows = json.loads(resp.content)
    assert len(rows) >= 1
    assert all("mom_change_pct" in r for r in rows)
    assert all("price_index_base_100" in r for r in rows)
    assert rows[0]["typ"] == "byt"


@pytest.mark.skipif(not DATABASE_URL, reason="set VERIFY_DATABASE_URL to run")
def test_export_analytics_valuation_endpoint(api_client, db_session):
    resp = api_client.get("/api/export/analytics/valuation", params={"format": "json"})
    assert resp.status_code == 200
    assert json.loads(resp.content) == []
