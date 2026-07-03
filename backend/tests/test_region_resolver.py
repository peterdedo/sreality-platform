"""Tests for Czech region resolution (detail, locality id, GPS polygon, unknown)."""

from datetime import datetime

from sqlmodel import Session, SQLModel, create_engine

from app.domain.czech_regions import is_plausible_gps, normalize_region_name, region_from_gps, region_from_locality_id
from app.domain.region_hints import RegionHints, hints_from_list_payload, merge_hints
from app.domain.region_resolver import (
    RegionSource,
    RegionUnknownReason,
    apply_resolved_region,
    resolve_region,
)
from app.models import Listing, Location, RawPayload
from app.scraping.region_backfill import backfill_resolved_regions


def _listing(**kwargs) -> Listing:
    return Listing(
        hash_id=kwargs.pop("hash_id", "test"),
        category_main_cb=1,
        category_type_cb=1,
        **kwargs,
    )


def test_resolve_from_detail_region_name():
    hints = RegionHints(detail_region_name="Jihomoravský kraj", has_detail=True)
    resolved = resolve_region(location=None, gps_lat=49.2, gps_lon=16.6, hints=hints)
    assert resolved.source == RegionSource.detail
    assert resolved.region_id == 14
    assert resolved.unknown_reason is None


def test_resolve_from_locality_region_id():
    hints = RegionHints(locality_region_id=8)
    resolved = resolve_region(location=None, gps_lat=None, gps_lon=None, hints=hints)
    assert resolved.source == RegionSource.locality_region_id
    assert resolved.region_id == 8


def test_detail_takes_priority_over_locality_id():
    hints = RegionHints(detail_region_name="Plzeňský kraj", locality_region_id=11, has_detail=True)
    resolved = resolve_region(location=None, gps_lat=49.7, gps_lon=13.4, hints=hints)
    assert resolved.source == RegionSource.detail
    assert resolved.region_id == 2


def test_resolve_from_gps_polygon_prague():
    resolved = resolve_region(location=None, gps_lat=50.0755, gps_lon=14.4378)
    assert resolved.source == RegionSource.gps_polygon
    assert resolved.region_id == 10


def test_resolve_from_gps_polygon_brno():
    resolved = resolve_region(location=None, gps_lat=49.1951, gps_lon=16.6068)
    assert resolved.source == RegionSource.gps_polygon
    assert resolved.region_id == 14


def test_unknown_missing_gps_with_locality_only():
    hints = RegionHints(locality_region_id=99)
    resolved = resolve_region(location=None, gps_lat=None, gps_lon=None, hints=hints)
    assert resolved.source == RegionSource.unknown
    assert resolved.unknown_reason == RegionUnknownReason.missing_gps


def test_unknown_no_signals():
    resolved = resolve_region(location=None, gps_lat=None, gps_lon=None)
    assert resolved.source == RegionSource.unknown
    assert resolved.unknown_reason == RegionUnknownReason.no_detail_no_region_no_gps


def test_unknown_invalid_gps():
    resolved = resolve_region(location=None, gps_lat=0.0, gps_lon=0.0)
    assert resolved.source == RegionSource.unknown
    assert resolved.unknown_reason == RegionUnknownReason.invalid_gps
    assert not is_plausible_gps(0.0, 0.0)


def test_unknown_outside_czech_bbox():
    resolved = resolve_region(location=None, gps_lat=40.0, gps_lon=10.0)
    assert resolved.source == RegionSource.unknown
    assert resolved.unknown_reason == RegionUnknownReason.outside_czech_bounding_box


def test_unknown_polygon_miss_inside_bbox():
    resolved = resolve_region(location=None, gps_lat=50.0, gps_lon=12.05)
    assert resolved.source == RegionSource.unknown
    assert resolved.unknown_reason == RegionUnknownReason.polygon_miss


def test_unknown_unnormalized_detail_name():
    hints = RegionHints(detail_region_name="Not A Real Kraj", has_detail=True)
    resolved = resolve_region(location=None, gps_lat=50.0, gps_lon=12.05, hints=hints)
    assert resolved.source == RegionSource.unknown
    assert resolved.unknown_reason == RegionUnknownReason.unresolved


def test_reverse_geocode_only_when_polygon_misses():
    calls = []

    def fake_reverse(lat: float, lon: float):
        calls.append((lat, lon))
        return 7, "Liberecký kraj"

    resolved = resolve_region(
        location=None,
        gps_lat=50.0,
        gps_lon=12.05,
        reverse_geocode=fake_reverse,
    )
    assert resolved.source == RegionSource.reverse_geocode
    assert resolved.region_id == 7
    assert calls == [(50.0, 12.05)]


def test_apply_resolved_region_persists_fields():
    listing = _listing(gps_lat=50.0755, gps_lon=14.4378)
    resolved = apply_resolved_region(listing, location=None)
    assert resolved.source == RegionSource.gps_polygon
    assert listing.resolved_region_name == "Hlavní město Praha"
    assert listing.region_unknown_reason is None


def test_hints_from_list_payload_locality_region_id():
    hints = hints_from_list_payload(
        {
            "locality": {"region_id": 11, "gps_lat": 49.2, "gps_lon": 16.6},
            "gps": {"lat": 49.2, "lon": 16.6},
        }
    )
    resolved = resolve_region(location=None, gps_lat=None, gps_lon=None, hints=hints)
    assert resolved.source == RegionSource.locality_region_id
    assert resolved.region_id == 11


def test_merge_hints_prefers_first_non_empty_detail():
    merged = merge_hints(
        RegionHints(detail_region_name="Karlovarský kraj", has_detail=True),
        RegionHints(detail_region_name="Plzeňský kraj", has_detail=True),
    )
    resolved = resolve_region(hints=merged)
    assert resolved.region_id == 3


def test_backfill_populates_resolved_regions():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    now = datetime.utcnow()
    with Session(engine) as session:
        listing = Listing(
            hash_id="gps-only",
            title="GPS",
            category_main_cb=1,
            category_type_cb=1,
            is_active=True,
            gps_lat=50.0755,
            gps_lon=14.4378,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(listing)
        session.commit()
        session.refresh(listing)

        result = backfill_resolved_regions(session, batch_size=10)
        session.refresh(listing)

    assert result["updated"] == 1
    assert listing.resolved_region_name == "Hlavní město Praha"
    assert listing.region_source == "gps_polygon"
    assert result["after"]["with_region"] == 1
    assert result["after"]["unknown_region"] == 0


def test_backfill_uses_raw_payload_locality_region_id():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    now = datetime.utcnow()
    with Session(engine) as session:
        listing = Listing(
            hash_id="payload-region",
            title="Payload",
            category_main_cb=1,
            category_type_cb=1,
            is_active=True,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(listing)
        session.commit()
        session.refresh(listing)
        session.add(
            RawPayload(
                hash_id=listing.hash_id,
                payload_type="list",
                payload={"locality": {"region_id": 4}},
            )
        )
        session.commit()

        backfill_resolved_regions(session, batch_size=10)
        session.refresh(listing)

    assert listing.resolved_region_id == 4
    assert listing.region_source == "locality_region_id"


def test_normalize_region_name_variants():
    assert normalize_region_name("Praha") == (10, "Hlavní město Praha")
    assert region_from_locality_id(14) == (14, "Jihomoravský kraj")
    assert region_from_gps(40.0, 10.0) is None
