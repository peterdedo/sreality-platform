"""Stage 1/2: comparable-listings engine.

Computed per-request from a bounded candidate query -- not materialized.
Candidate pool: active listings in the same category_main_cb + category_type_cb,
category_sub_cb within +/-1, usable_area within +/-25%, ranked by haversine
distance, expanding the search radius if too few candidates are found nearby.
See docs/METHODOLOGY.md §5.
"""

import statistics
from dataclasses import dataclass

from sqlmodel import Session, select

from app.analytics.advanced.geo import haversine_km
from app.models import Listing, ListingDetail

AREA_BAND_PCT = 0.25
SUB_CB_BAND = 1
SEARCH_RADII_KM = [5, 10, 20]
MIN_COMPARABLES = 3
MAX_COMPARABLES = 8


@dataclass
class ComparableResult:
    listing_id: int
    title: str | None
    price_czk: int | None
    price_per_m2: float | None
    distance_km: float


def find_comparables(session: Session, listing_id: int, limit: int = MAX_COMPARABLES) -> dict | None:
    subject = session.get(Listing, listing_id)
    if subject is None:
        return None
    subject_detail = session.exec(select(ListingDetail).where(ListingDetail.listing_id == listing_id)).first()

    if subject.gps_lat is None or subject.gps_lon is None:
        return {
            "listing_id": listing_id,
            "comparables": [],
            "median_comparable_price_czk": None,
            "median_comparable_price_per_m2": None,
            "deviation_from_comparables_pct": None,
            "note": "Nabídka nemá GPS souřadnice, srovnatelné nabídky nelze dohledat.",
        }

    area = subject_detail.usable_area if subject_detail else None
    area_min = area * (1 - AREA_BAND_PCT) if area else None
    area_max = area * (1 + AREA_BAND_PCT) if area else None

    candidates_stmt = (
        select(Listing, ListingDetail)
        .join(ListingDetail, ListingDetail.listing_id == Listing.id)
        .where(
            Listing.id != listing_id,
            Listing.is_active == True,  # noqa: E712
            Listing.category_main_cb == subject.category_main_cb,
            Listing.category_type_cb == subject.category_type_cb,
            Listing.gps_lat.is_not(None),
            Listing.gps_lon.is_not(None),
        )
    )
    if subject.category_sub_cb is not None:
        candidates_stmt = candidates_stmt.where(
            Listing.category_sub_cb.between(subject.category_sub_cb - SUB_CB_BAND, subject.category_sub_cb + SUB_CB_BAND)
        )
    if area_min is not None:
        candidates_stmt = candidates_stmt.where(ListingDetail.usable_area.between(area_min, area_max))

    rows = session.exec(candidates_stmt).all()

    scored: list[ComparableResult] = []
    for listing, detail in rows:
        distance = haversine_km(subject.gps_lat, subject.gps_lon, listing.gps_lat, listing.gps_lon)
        price_per_m2 = (listing.price_czk / detail.usable_area) if listing.price_czk and detail.usable_area else None
        scored.append(
            ComparableResult(
                listing_id=listing.id,
                title=listing.title,
                price_czk=listing.price_czk,
                price_per_m2=price_per_m2,
                distance_km=round(distance, 2),
            )
        )
    scored.sort(key=lambda c: c.distance_km)

    selected: list[ComparableResult] = []
    for radius in SEARCH_RADII_KM:
        selected = [c for c in scored if c.distance_km <= radius][:limit]
        if len(selected) >= MIN_COMPARABLES or radius == SEARCH_RADII_KM[-1]:
            break

    prices = [c.price_czk for c in selected if c.price_czk]
    prices_per_m2 = [c.price_per_m2 for c in selected if c.price_per_m2]
    median_price = statistics.median(prices) if prices else None
    median_price_per_m2 = statistics.median(prices_per_m2) if prices_per_m2 else None

    deviation_pct = None
    if median_price and subject.price_czk:
        deviation_pct = round((subject.price_czk - median_price) / median_price * 100, 1)

    return {
        "listing_id": listing_id,
        "comparables": [
            {
                "listing_id": c.listing_id,
                "title": c.title,
                "price_czk": c.price_czk,
                "price_per_m2": round(c.price_per_m2, 0) if c.price_per_m2 else None,
                "distance_km": c.distance_km,
            }
            for c in selected
        ],
        "median_comparable_price_czk": median_price,
        "median_comparable_price_per_m2": round(median_price_per_m2, 0) if median_price_per_m2 else None,
        "deviation_from_comparables_pct": deviation_pct,
        "note": None if len(selected) >= MIN_COMPARABLES else "Nedostatek srovnatelných nabídek v okolí -- výsledek má nízkou vypovídací hodnotu.",
    }
