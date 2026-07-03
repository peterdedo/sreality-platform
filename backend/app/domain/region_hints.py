"""Collect region-resolution hints from Location rows and stored raw payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import Location, RawPayload
from app.scraping.parser import _extract_admin_names, _safe_float, _safe_int, parse_detail


@dataclass(frozen=True)
class RegionHints:
    detail_region_name: str | None = None
    locality_region_id: int | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None
    has_detail: bool = False


def _gps_from_payload(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    locality = payload.get("locality")
    loc = locality if isinstance(locality, dict) else {}
    gps = payload.get("gps") or {}
    lat = gps.get("lat") or loc.get("gps_lat") or payload.get("locality_gps_lat")
    lon = gps.get("lon") or loc.get("gps_lon") or payload.get("locality_gps_lon")
    return _safe_float(lat), _safe_float(lon)


def _locality_region_id_from_payload(payload: dict[str, Any]) -> int | None:
    locality = payload.get("locality")
    loc = locality if isinstance(locality, dict) else {}
    return _safe_int(loc.get("region_id") or payload.get("locality_region_id"))


def hints_from_list_payload(payload: dict[str, Any]) -> RegionHints:
    names = _extract_admin_names(payload.get("locality"), payload)
    lat, lon = _gps_from_payload(payload)
    return RegionHints(
        locality_region_id=_locality_region_id_from_payload(payload),
        gps_lat=lat,
        gps_lon=lon,
    )


def hints_from_detail_payload(payload: dict[str, Any]) -> RegionHints:
    parsed = parse_detail(payload)
    location = parsed.get("location") or {}
    lat = _safe_float(location.get("gps_lat"))
    lon = _safe_float(location.get("gps_lon"))
    return RegionHints(
        detail_region_name=location.get("region"),
        locality_region_id=_safe_int(location.get("locality_region_id")),
        gps_lat=lat,
        gps_lon=lon,
        has_detail=True,
    )


def merge_hints(*items: RegionHints) -> RegionHints:
    detail_region_name = None
    locality_region_id = None
    gps_lat = None
    gps_lon = None
    has_detail = False
    for item in items:
        if item.detail_region_name and not detail_region_name:
            detail_region_name = item.detail_region_name
        if item.locality_region_id is not None and locality_region_id is None:
            locality_region_id = item.locality_region_id
        if item.gps_lat is not None and gps_lat is None:
            gps_lat = item.gps_lat
        if item.gps_lon is not None and gps_lon is None:
            gps_lon = item.gps_lon
        has_detail = has_detail or item.has_detail
    return RegionHints(
        detail_region_name=detail_region_name,
        locality_region_id=locality_region_id,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        has_detail=has_detail,
    )


def hints_from_location(location: Location | None) -> RegionHints:
    if location is None:
        return RegionHints()
    return RegionHints(
        detail_region_name=location.region,
        locality_region_id=location.locality_region_id,
        gps_lat=location.gps_lat,
        gps_lon=location.gps_lon,
    )


def hints_from_raw_payloads(
    list_payload: dict[str, Any] | None,
    detail_payload: dict[str, Any] | None,
    *,
    location: Location | None = None,
    has_detail_row: bool = False,
) -> RegionHints:
    parts: list[RegionHints] = [hints_from_location(location)]
    if list_payload:
        parts.append(hints_from_list_payload(list_payload))
    if detail_payload:
        parts.append(hints_from_detail_payload(detail_payload))
    elif has_detail_row and location:
        parts.append(RegionHints(detail_region_name=location.region, has_detail=True))
    return merge_hints(*parts)


def latest_payloads_by_listing(
    list_rows: list[RawPayload],
    detail_rows: list[RawPayload],
) -> tuple[dict[str, dict[str, Any]], dict[int, dict[str, Any]]]:
    """Return newest list payload per hash_id and newest detail payload per listing_id."""
    list_by_hash: dict[str, dict[str, Any]] = {}
    for row in sorted(list_rows, key=lambda r: r.fetched_at):
        if row.hash_id:
            list_by_hash[row.hash_id] = row.payload

    detail_by_listing: dict[int, dict[str, Any]] = {}
    for row in sorted(detail_rows, key=lambda r: r.fetched_at):
        if row.listing_id is not None:
            detail_by_listing[row.listing_id] = row.payload
    return list_by_hash, detail_by_listing
