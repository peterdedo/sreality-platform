"""Real-database integration test for the Pokročilé analýzy recompute
pipeline (market dynamics -> valuation -> anomaly -> spatial). Unlike
test_pipeline_dry_run.py this test doesn't touch the scraping/HTTP layer at
all -- it seeds Listing/ListingDetail/PriceHistory rows directly (this
pipeline only ever reads/writes the database) and exercises every real
service module in app/analytics/advanced/ against a real Postgres database.

Skipped unless VERIFY_DATABASE_URL is set, same convention as
test_pipeline_dry_run.py.
"""

import os
import random
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.analytics.advanced.pipeline import run_full_recompute
from app.models import (
    AnalyticSnapshot,
    Listing,
    ListingAnomaly,
    ListingDetail,
    ListingValuation,
    PriceHistory,
    SpatialGridMetric,
    ValuationModel,
)

DATABASE_URL = os.environ.get("VERIFY_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN to run this dry-run"
)

# Prague-ish bounding box for synthetic GPS coordinates
BASE_LAT, BASE_LON = 50.075, 14.42
PRICE_PER_M2_BASE = 90_000  # plausible-ish CZK/m2 for a Prague flat


@pytest.fixture()
def session():
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in (
            "spatialgridmetric",
            "listinganomaly",
            "listingvaluation",
            "valuationmodel",
            "analyticsnapshot",
            "rawpayload",
            "pricehistory",
            "image",
            "listingdetail",
            "scrapingrun",
            "analyticsrun",
            "listing",
        ):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    with Session(engine) as s:
        yield s


def _make_listing(session, i, *, area, price, lat, lon, sub_cb=4, first_seen_days_ago=10, condition="1", ownership="1"):
    now = datetime.utcnow()
    listing = Listing(
        hash_id=f"synthetic-{i}",
        category_main_cb=1,
        category_type_cb=1,
        category_sub_cb=sub_cb,
        title=f"Byt {i}",
        price_czk=price,
        gps_lat=lat,
        gps_lon=lon,
        is_active=True,
        first_seen_at=now - timedelta(days=first_seen_days_ago),
        last_seen_at=now,
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)

    session.add(
        ListingDetail(
            listing_id=listing.id,
            usable_area=area,
            building_condition=condition,
            ownership=ownership,
            energy_efficiency_rating="3",
            floor="2/5",
            balcony=True,
        )
    )
    session.add(PriceHistory(listing_id=listing.id, price_czk=price, recorded_at=now - timedelta(days=first_seen_days_ago)))
    session.commit()
    return listing


def test_full_recompute_pipeline_on_synthetic_segment(session):
    random.seed(42)

    # 35 "normal" listings with a real area->price relationship plus noise,
    # scattered across a handful of grid cells, so the valuation model has
    # enough training data (MIN_TRAINING_SAMPLES = 30) to actually fit.
    normal_listings = []
    for i in range(35):
        area = random.uniform(40, 90)
        noise = random.uniform(0.9, 1.1)
        price = round(area * PRICE_PER_M2_BASE * noise)
        lat = BASE_LAT + random.uniform(-0.02, 0.02)
        lon = BASE_LON + random.uniform(-0.02, 0.02)
        normal_listings.append(_make_listing(session, i, area=area, price=price, lat=lat, lon=lon))

    # A deliberately underpriced listing (should classify under_market)
    underpriced = _make_listing(session, "under", area=60, price=int(60 * PRICE_PER_M2_BASE * 0.5), lat=BASE_LAT, lon=BASE_LON)

    # A deliberately overpriced listing (should classify over_market)
    overpriced = _make_listing(session, "over", area=60, price=int(60 * PRICE_PER_M2_BASE * 2.0), lat=BASE_LAT, lon=BASE_LON)

    # A near-duplicate pair: same location, same area, same layout, different hash_id
    dup1 = _make_listing(session, "dup1", area=55, price=int(55 * PRICE_PER_M2_BASE), lat=50.09, lon=14.44)
    dup2 = _make_listing(session, "dup2", area=55.5, price=int(55 * PRICE_PER_M2_BASE * 1.02), lat=50.0901, lon=14.4401)

    # A listing with an implausibly tiny area for its layout (2+kk, min ~25m2 per the heuristic table)
    tiny = _make_listing(session, "tiny", area=8, price=int(8 * PRICE_PER_M2_BASE), lat=BASE_LAT, lon=BASE_LON, sub_cb=4)

    # A listing with a huge single-step price drop
    dropper = _make_listing(session, "dropper", area=50, price=int(50 * PRICE_PER_M2_BASE * 0.6), lat=BASE_LAT, lon=BASE_LON)
    session.add(
        PriceHistory(
            listing_id=dropper.id,
            price_czk=int(50 * PRICE_PER_M2_BASE),
            recorded_at=datetime.utcnow() - timedelta(days=20),
        )
    )
    session.commit()

    run = run_full_recompute(session)

    assert run.status == "success", run.error_message
    assert run.error_count == 0

    # --- market dynamics ---
    snapshots = session.exec(select(AnalyticSnapshot)).all()
    segment_snapshot = next(s for s in snapshots if s.category_main_cb == 1 and s.category_type_cb == 1)
    assert segment_snapshot.listing_count == len(normal_listings) + 6  # +underpriced/overpriced/dup1/dup2/tiny/dropper
    assert segment_snapshot.avg_price_per_m2 is not None

    # --- valuation ---
    models = session.exec(select(ValuationModel)).all()
    assert len(models) == 1
    assert models[0].n_samples >= 30
    assert models[0].r2 is not None

    valuations = {v.listing_id: v for v in session.exec(select(ListingValuation)).all()}
    assert valuations[underpriced.id].confidence != "unavailable"
    assert valuations[underpriced.id].classification == "under_market"
    assert valuations[overpriced.id].classification == "over_market"

    # --- anomaly ---
    anomalies = {a.listing_id: a for a in session.exec(select(ListingAnomaly)).all()}
    assert "possible_duplicate" in anomalies[dup1.id].anomaly_flags
    assert "possible_duplicate" in anomalies[dup2.id].anomaly_flags
    assert "area_layout_mismatch" in anomalies[tiny.id].anomaly_flags
    assert "unusual_price_change" in anomalies[dropper.id].anomaly_flags
    # a "normal" listing shouldn't be flagged for everything
    assert anomalies[normal_listings[0].id].anomaly_score < anomalies[dup1.id].anomaly_score

    # --- spatial ---
    grid_rows = session.exec(select(SpatialGridMetric)).all()
    assert len(grid_rows) > 0
    assert sum(r.listing_count for r in grid_rows) == segment_snapshot.listing_count
