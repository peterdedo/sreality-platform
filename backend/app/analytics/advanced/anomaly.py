"""Stage 2: rule-based + z-score anomaly detection. Explicitly NOT machine
learning -- every flag is a named, auditable rule, and anomaly_score is a
transparent capped weighted sum, not a learned score. See docs/METHODOLOGY.md §4.
"""

import statistics
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.analytics.advanced.geo import haversine_km
from app.models import Listing, ListingAnomaly, ListingDetail, PriceHistory

Z_SCORE_THRESHOLD = 2.5
UNUSUAL_PRICE_CHANGE_PCT = 30.0
STALE_FALLBACK_DAYS = 180
DUPLICATE_DISTANCE_KM = 0.05  # ~50m
DUPLICATE_AREA_TOLERANCE_PCT = 0.05
MIN_SEGMENT_SAMPLES_FOR_STATS = 10

# Heuristic minimum plausible usable_area (m2) per category_sub_cb (dispozice).
# These are reasonable common-sense bounds for Czech flats/houses, NOT sourced
# from an authoritative document (unlike app/domain/codebooks.py) -- flagged
# explicitly in docs/METHODOLOGY.md as a heuristic, not a verified fact.
MIN_PLAUSIBLE_AREA_BY_SUB_CB: dict[int, float] = {
    2: 15,   # 1+kk
    3: 20,   # 1+1
    4: 25,   # 2+kk
    5: 35,   # 2+1
    6: 45,   # 3+kk
    7: 55,   # 3+1
    8: 60,   # 4+kk
    9: 70,   # 4+1
    10: 75,  # 5+kk
    11: 85,  # 5+1
    12: 100,  # 6 a více
}

FLAG_WEIGHTS: dict[str, float] = {
    "extreme_price_per_m2": 30,
    "unusual_price_change": 25,
    "area_layout_mismatch": 20,
    "stale_listing": 15,
    "possible_duplicate": 35,
}


def _segment_key(listing: Listing) -> tuple[int, int, int | None]:
    return (listing.category_main_cb, listing.category_type_cb, listing.category_sub_cb)


def compute_anomalies(session: Session) -> list[ListingAnomaly]:
    listings = session.exec(select(Listing).where(Listing.is_active == True)).all()  # noqa: E712
    details_by_listing_id = {
        d.listing_id: d for d in session.exec(select(ListingDetail)).all()
    }

    # group price/m2 by segment for z-score computation
    price_per_m2_by_segment: dict[tuple, list[float]] = {}
    age_by_segment: dict[tuple, list[float]] = {}
    now = datetime.utcnow()
    for listing in listings:
        detail = details_by_listing_id.get(listing.id)
        segment = _segment_key(listing)
        if listing.price_czk and detail and detail.usable_area:
            price_per_m2_by_segment.setdefault(segment, []).append(listing.price_czk / detail.usable_area)
        age_by_segment.setdefault(segment, []).append((now - listing.first_seen_at).total_seconds() / 86400)

    results: list[ListingAnomaly] = []
    for listing in listings:
        detail = details_by_listing_id.get(listing.id)
        segment = _segment_key(listing)
        flags: list[str] = []
        segment_n = len(price_per_m2_by_segment.get(segment, []))

        # (a) extreme price/m2 vs segment
        if listing.price_czk and detail and detail.usable_area and segment_n >= MIN_SEGMENT_SAMPLES_FOR_STATS:
            values = price_per_m2_by_segment[segment]
            mean = statistics.mean(values)
            stdev = statistics.pstdev(values)
            if stdev > 0:
                z = (listing.price_czk / detail.usable_area - mean) / stdev
                if abs(z) > Z_SCORE_THRESHOLD:
                    flags.append("extreme_price_per_m2")

        # (b) unusual single-step price change
        history = session.exec(
            select(PriceHistory).where(PriceHistory.listing_id == listing.id).order_by(PriceHistory.recorded_at)
        ).all()
        for i in range(len(history) - 1):
            prev, curr = history[i].price_czk, history[i + 1].price_czk
            if prev and abs(curr - prev) / prev * 100 >= UNUSUAL_PRICE_CHANGE_PCT:
                flags.append("unusual_price_change")
                break

        # (c) area/layout mismatch
        if detail and detail.usable_area and listing.category_sub_cb in MIN_PLAUSIBLE_AREA_BY_SUB_CB:
            min_plausible = MIN_PLAUSIBLE_AREA_BY_SUB_CB[listing.category_sub_cb]
            if detail.usable_area < min_plausible * 0.5:
                flags.append("area_layout_mismatch")

        # (d) stale listing
        age_days = (now - listing.first_seen_at).total_seconds() / 86400
        age_samples = age_by_segment.get(segment, [])
        if len(age_samples) >= MIN_SEGMENT_SAMPLES_FOR_STATS:
            p90 = statistics.quantiles(age_samples, n=10)[8]  # 90th percentile
            if age_days > p90:
                flags.append("stale_listing")
        elif age_days > STALE_FALLBACK_DAYS:
            flags.append("stale_listing")

        # (e) possible duplicate / relisted
        if listing.gps_lat is not None and listing.gps_lon is not None and detail and detail.usable_area:
            for other in listings:
                if other.id == listing.id or other.gps_lat is None or other.gps_lon is None:
                    continue
                other_detail = details_by_listing_id.get(other.id)
                if not other_detail or not other_detail.usable_area:
                    continue
                if other.category_sub_cb != listing.category_sub_cb:
                    continue
                area_diff_pct = abs(other_detail.usable_area - detail.usable_area) / detail.usable_area
                if area_diff_pct > DUPLICATE_AREA_TOLERANCE_PCT:
                    continue
                distance = haversine_km(listing.gps_lat, listing.gps_lon, other.gps_lat, other.gps_lon)
                if distance <= DUPLICATE_DISTANCE_KM:
                    flags.append("possible_duplicate")
                    break

        flags = sorted(set(flags))
        score = min(100.0, sum(FLAG_WEIGHTS.get(f, 0) for f in flags))
        confidence = min(1.0, segment_n / MIN_SEGMENT_SAMPLES_FOR_STATS / 3) if segment_n else 0.0

        existing = session.exec(select(ListingAnomaly).where(ListingAnomaly.listing_id == listing.id)).first()
        if existing:
            existing.anomaly_score = score
            existing.anomaly_flags = flags
            existing.confidence_score = confidence
            existing.computed_at = now
            session.add(existing)
            results.append(existing)
        else:
            row = ListingAnomaly(
                listing_id=listing.id,
                anomaly_score=score,
                anomaly_flags=flags,
                confidence_score=confidence,
                computed_at=now,
            )
            session.add(row)
            results.append(row)

    session.commit()
    for row in results:
        session.refresh(row)
    return results
