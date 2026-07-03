"""Resolve canonical Czech kraj for a listing using a fixed priority chain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from app.domain.czech_regions import (
    is_inside_czech_bbox,
    is_plausible_gps,
    normalize_region_name,
    region_from_gps,
    region_from_locality_id,
)
from app.domain.region_hints import RegionHints, hints_from_location, merge_hints
from app.models import Listing, Location


class RegionSource(str, Enum):
    detail = "detail"
    locality_region_id = "locality_region_id"
    gps_polygon = "gps_polygon"
    reverse_geocode = "reverse_geocode"
    unknown = "unknown"


class RegionUnknownReason(str, Enum):
    missing_gps = "missing_gps"
    invalid_gps = "invalid_gps"
    outside_czech_bounding_box = "outside_czech_bounding_box"
    polygon_miss = "polygon_miss"
    no_detail_no_region_no_gps = "no_detail_no_region_no_gps"
    unresolved = "unresolved"


@dataclass(frozen=True)
class ResolvedRegion:
    region_id: Optional[int]
    region_name: Optional[str]
    source: RegionSource
    unknown_reason: Optional[RegionUnknownReason] = None


ReverseGeocodeFn = Callable[[float, float], Optional[tuple[int, str]]]


def _pick_gps(
    listing_lat: float | None,
    listing_lon: float | None,
    hints: RegionHints,
    location: Location | None,
) -> tuple[float | None, float | None]:
    for lat, lon in (
        (listing_lat, listing_lon),
        (hints.gps_lat, hints.gps_lon),
        (location.gps_lat, location.gps_lon) if location else (None, None),
    ):
        if lat is not None and lon is not None:
            return lat, lon
    if listing_lat is not None or listing_lon is not None:
        return listing_lat, listing_lon
    return hints.gps_lat, hints.gps_lon


def _classify_unknown(
    *,
    detail_region_name: str | None,
    locality_region_id: int | None,
    gps_lat: float | None,
    gps_lon: float | None,
    had_unnormalized_detail_name: bool,
) -> RegionUnknownReason:
    has_detail_signal = bool(detail_region_name) or had_unnormalized_detail_name
    has_locality_signal = locality_region_id is not None

    if gps_lat is None or gps_lon is None:
        if not has_detail_signal and not has_locality_signal:
            return RegionUnknownReason.no_detail_no_region_no_gps
        return RegionUnknownReason.missing_gps

    if not is_plausible_gps(gps_lat, gps_lon):
        return RegionUnknownReason.invalid_gps

    if not is_inside_czech_bbox(gps_lat, gps_lon):
        return RegionUnknownReason.outside_czech_bounding_box

    if had_unnormalized_detail_name:
        return RegionUnknownReason.unresolved

    return RegionUnknownReason.polygon_miss


def resolve_region(
    *,
    location: Location | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    hints: RegionHints | None = None,
    reverse_geocode: ReverseGeocodeFn | None = None,
) -> ResolvedRegion:
    """Priority: detail name → locality_region_id → GPS polygon → rare reverse geocode → unknown."""
    merged = merge_hints(hints or RegionHints(), hints_from_location(location))
    lat, lon = _pick_gps(gps_lat, gps_lon, merged, location)

    detail_name = merged.detail_region_name
    had_unnormalized_detail_name = False
    if merged.has_detail and detail_name:
        mapped = normalize_region_name(detail_name)
        if mapped:
            region_id, region_name = mapped
            return ResolvedRegion(region_id, region_name, RegionSource.detail)
        had_unnormalized_detail_name = True

    locality_id = merged.locality_region_id
    if locality_id is None and location and location.locality_region_id is not None:
        locality_id = location.locality_region_id
    mapped = region_from_locality_id(locality_id)
    if mapped:
        region_id, region_name = mapped
        return ResolvedRegion(region_id, region_name, RegionSource.locality_region_id)

    mapped = region_from_gps(lat, lon)
    if mapped:
        region_id, region_name = mapped
        return ResolvedRegion(region_id, region_name, RegionSource.gps_polygon)

    if reverse_geocode and is_plausible_gps(lat, lon):
        mapped = reverse_geocode(lat, lon)
        if mapped:
            region_id, region_name = mapped
            return ResolvedRegion(region_id, region_name, RegionSource.reverse_geocode)

    unknown_reason = _classify_unknown(
        detail_region_name=detail_name,
        locality_region_id=locality_id,
        gps_lat=lat,
        gps_lon=lon,
        had_unnormalized_detail_name=had_unnormalized_detail_name,
    )
    return ResolvedRegion(None, None, RegionSource.unknown, unknown_reason)


def apply_resolved_region(
    listing: Listing,
    *,
    location: Location | None = None,
    hints: RegionHints | None = None,
    reverse_geocode: ReverseGeocodeFn | None = None,
) -> ResolvedRegion:
    resolved = resolve_region(
        location=location,
        gps_lat=listing.gps_lat,
        gps_lon=listing.gps_lon,
        hints=hints,
        reverse_geocode=reverse_geocode,
    )
    listing.resolved_region_id = resolved.region_id
    listing.resolved_region_name = resolved.region_name
    listing.region_source = resolved.source.value
    listing.region_unknown_reason = (
        resolved.unknown_reason.value if resolved.unknown_reason is not None else None
    )
    return resolved
