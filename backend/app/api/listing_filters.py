"""Shared listing filter helpers for GET /listings and export."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models import Listing, Location


def _pattern(value: str) -> str:
    return f"%{value.strip()}%"


def listing_text_search_condition(query: str):
    """Match free-text query across title and all known locality fields."""
    pattern = _pattern(query)
    return or_(
        Listing.title.ilike(pattern),
        Listing.locality_text.ilike(pattern),
        Listing.resolved_region_name.ilike(pattern),
        Location.region.ilike(pattern),
        Location.district.ilike(pattern),
        Location.municipality.ilike(pattern),
        Location.quarter.ilike(pattern),
    )


def listing_region_condition(region: str):
    pattern = _pattern(region)
    region_col = func.coalesce(Listing.resolved_region_name, Location.region)
    return or_(
        region_col.ilike(pattern),
        Location.district.ilike(pattern),
        Listing.locality_text.ilike(pattern),
    )


def listing_district_condition(district: str):
    pattern = _pattern(district)
    return or_(
        Location.district.ilike(pattern),
        Location.quarter.ilike(pattern),
        Location.municipality.ilike(pattern),
        Listing.locality_text.ilike(pattern),
    )


def listing_city_condition(city: str):
    pattern = _pattern(city)
    return or_(
        Location.municipality.ilike(pattern),
        Location.quarter.ilike(pattern),
        Location.district.ilike(pattern),
        Listing.locality_text.ilike(pattern),
    )


def _with_active_filter(*conditions, active_only: bool):
    clauses = list(conditions)
    if active_only:
        clauses.append(Listing.is_active == True)  # noqa: E712
    return clauses


def _distinct_labels(session: Session, column, pattern: str, *, limit: int, active_only: bool) -> list[str]:
    stmt = (
        select(func.distinct(column))
        .select_from(Listing)
        .join(Location, Location.id == Listing.location_id, isouter=True)
        .where(*_with_active_filter(column.is_not(None), column.ilike(pattern), active_only=active_only))
        .order_by(column)
        .limit(limit)
    )
    return [row for row in session.exec(stmt).all() if row]


def location_suggest(session: Session, query: str, *, limit: int = 15, active_only: bool = True) -> list[dict]:
    """Return locality suggestions with filter hints for the listings UI."""
    q = query.strip()
    if len(q) < 2:
        return []

    pattern = _pattern(q)
    limit = max(1, min(limit, 30))
    items: list[dict] = []
    seen: set[str] = set()
    per_kind = max(3, limit // 3)

    def add(label: Optional[str], kind: str, **filters: str) -> None:
        if not label:
            return
        key = label.casefold()
        if key in seen:
            return
        seen.add(key)
        items.append({"label": label, "kind": kind, **filters})

    region_col = func.coalesce(Listing.resolved_region_name, Location.region)
    for label in _distinct_labels(session, region_col, pattern, limit=per_kind, active_only=active_only):
        add(label, "kraj", region=label)

    for label in _distinct_labels(session, Location.district, pattern, limit=per_kind, active_only=active_only):
        add(label, "okres", district=label)

    for label in _distinct_labels(session, Location.municipality, pattern, limit=per_kind, active_only=active_only):
        add(label, "obec", city=label)

    for label in _distinct_labels(session, Location.quarter, pattern, limit=per_kind, active_only=active_only):
        add(label, "ctvrt", search=label)

    locality_stmt = (
        select(func.distinct(Listing.locality_text))
        .where(*_with_active_filter(Listing.locality_text.is_not(None), Listing.locality_text.ilike(pattern), active_only=active_only))
        .order_by(Listing.locality_text)
        .limit(per_kind)
    )
    for label in session.exec(locality_stmt).all():
        add(label, "lokalita", search=label)

    kind_order = {"ctvrt": 0, "okres": 1, "obec": 2, "lokalita": 3, "kraj": 4}
    items.sort(key=lambda row: (kind_order.get(row["kind"], 9), len(row["label"]), row["label"]))
    return items[:limit]
