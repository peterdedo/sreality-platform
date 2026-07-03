"""Stage 1 (descriptive): point-in-time segment breakdowns.

Plain GROUP BY queries over every active listing in the local database.
NULL dimension values are bucketed as "Neznámý" so aggregates are not
silently truncated.
"""

from typing import Callable

from sqlalchemy import func, literal
from sqlmodel import Session, select

from app.analytics.queries import UNKNOWN_REGION
from app.domain import codebooks
from app.models import Listing, ListingDetail
from app.scraping.constants import DEAL_TYPES, PROPERTY_TYPES, ROOM_LAYOUTS

UNKNOWN_SEGMENT = "unknown"
UNKNOWN_SUB_CB = -1

# dimension name -> (raw column, label function for non-null wire values)
_DIMENSIONS: dict[str, tuple] = {
    "category_main_cb": (Listing.category_main_cb, lambda v: PROPERTY_TYPES.get(v, str(v))),
    "category_type_cb": (Listing.category_type_cb, lambda v: DEAL_TYPES.get(v, str(v))),
    "category_sub_cb": (Listing.category_sub_cb, lambda v: ROOM_LAYOUTS.get(v, "Neznámý")),
    "building_condition": (ListingDetail.building_condition, codebooks.building_condition_label),
    "ownership": (ListingDetail.ownership, codebooks.ownership_label),
    "energy_efficiency_rating": (ListingDetail.energy_efficiency_rating, codebooks.energy_efficiency_rating_label),
    "region": (Listing.resolved_region_name, lambda v: v),
}

ALLOWED_DIMENSIONS = list(_DIMENSIONS.keys())


def _grouping_column(dimension: str) -> tuple:
    column, label_fn = _DIMENSIONS[dimension]
    if dimension == "region":
        grouped = func.coalesce(column, literal(UNKNOWN_REGION))
        return grouped, lambda v: v or UNKNOWN_REGION
    if dimension in ("building_condition", "ownership", "energy_efficiency_rating"):
        grouped = func.coalesce(column, literal(UNKNOWN_SEGMENT))
        return grouped, lambda v: label_fn(v) if v and v != UNKNOWN_SEGMENT else "Neznámý"
    if dimension == "category_sub_cb":
        grouped = func.coalesce(column, literal(UNKNOWN_SUB_CB))
        return grouped, lambda v: ROOM_LAYOUTS.get(v, "Neznámý") if v != UNKNOWN_SUB_CB else "Neznámý"
    return column, label_fn


def segment_breakdown(session: Session, dimension: str, category_main_cb: int | None = None) -> list[dict]:
    if dimension not in _DIMENSIONS:
        raise ValueError(f"Unknown dimension '{dimension}'. Allowed: {ALLOWED_DIMENSIONS}")

    column, label_fn = _grouping_column(dimension)

    stmt = (
        select(
            column,
            func.count(Listing.id),
            func.avg(Listing.price_czk),
            func.avg(Listing.price_czk / func.nullif(ListingDetail.usable_area, 0)),
        )
        .select_from(Listing)
        .join(ListingDetail, ListingDetail.listing_id == Listing.id, isouter=True)
        .where(Listing.is_active == True)  # noqa: E712
    )
    if category_main_cb is not None:
        stmt = stmt.where(Listing.category_main_cb == category_main_cb)
    stmt = stmt.group_by(column)

    rows = session.exec(stmt).all()
    label_fn_callable: Callable = label_fn
    results = []
    for value, count, avg_price, avg_price_per_m2 in rows:
        results.append(
            {
                "value": value,
                "label": label_fn_callable(value),
                "listing_count": count,
                "avg_price_czk": float(avg_price) if avg_price else None,
                "avg_price_per_m2": float(avg_price_per_m2) if avg_price_per_m2 else None,
            }
        )
    results.sort(key=lambda r: r["listing_count"], reverse=True)
    return results
