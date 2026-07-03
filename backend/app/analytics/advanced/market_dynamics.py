"""Stage 1 (descriptive): market-dynamics metrics over time.

Populates AnalyticSnapshot -- one row per (snapshot_date, category_main_cb,
category_type_cb) segment, aggregated across all locations. Region/district
splits are intentionally left to the point-in-time `segments` module rather
than duplicated here as a second time-series dimension, to avoid a sparse
M x N explosion of near-empty rows given current data volume (see
docs/METHODOLOGY.md §1 and §7 "Limitations").

new_count/removed_count are computed "since the previous snapshot for this
segment" (falling back to a 1-day window if there is no prior snapshot), so
the resulting time series is additive regardless of how often the recompute
job is actually run.
"""

import statistics
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from app.models import AnalyticSnapshot, Listing, ListingDetail, PriceHistory

DAYS_ON_MARKET_LOOKBACK_DAYS = 90  # include listings removed within this window when computing DOM stats


def _distinct_segments(session: Session) -> list[tuple[int, int]]:
    rows = session.exec(select(Listing.category_main_cb, Listing.category_type_cb).distinct()).all()
    return sorted(set(rows))


def _days_on_market_samples(session: Session, category_main_cb: int, category_type_cb: int) -> list[float]:
    """Blended sample: right-censored (now - first_seen_at) for currently active
    listings, plus finalized (removed_at - first_seen_at) for listings removed
    within the lookback window. This is a simplification, not a survival-analysis
    correction -- documented in docs/METHODOLOGY.md."""
    now = datetime.utcnow()
    since = now - timedelta(days=DAYS_ON_MARKET_LOOKBACK_DAYS)

    listings = session.exec(
        select(Listing).where(
            Listing.category_main_cb == category_main_cb,
            Listing.category_type_cb == category_type_cb,
        )
    ).all()

    samples = []
    for listing in listings:
        if listing.is_active:
            samples.append((now - listing.first_seen_at).total_seconds() / 86400)
        elif listing.removed_at and listing.removed_at >= since:
            samples.append((listing.removed_at - listing.first_seen_at).total_seconds() / 86400)
    return samples


def _price_change_stats(session: Session, listing_ids: list[int]) -> tuple[float | None, list[bool]]:
    """Returns (median_first_to_last_price_change_pct, [had_any_drop, ...])."""
    changes_pct = []
    had_drop_flags = []
    for listing_id in listing_ids:
        history = session.exec(
            select(PriceHistory).where(PriceHistory.listing_id == listing_id).order_by(PriceHistory.recorded_at)
        ).all()
        if len(history) < 2:
            had_drop_flags.append(False)
            continue
        first_price, last_price = history[0].price_czk, history[-1].price_czk
        if first_price:
            changes_pct.append((last_price - first_price) / first_price * 100)
        had_drop = any(history[i + 1].price_czk < history[i].price_czk for i in range(len(history) - 1))
        had_drop_flags.append(had_drop)

    median_change = statistics.median(changes_pct) if changes_pct else None
    return median_change, had_drop_flags


def compute_market_dynamics_snapshot(session: Session, snapshot_date: date | None = None) -> list[AnalyticSnapshot]:
    """Computes and persists one AnalyticSnapshot row per (category_main_cb,
    category_type_cb) segment for snapshot_date (defaults to today, UTC).
    Returns the created rows."""

    snapshot_date = snapshot_date or datetime.utcnow().date()
    created: list[AnalyticSnapshot] = []

    for category_main_cb, category_type_cb in _distinct_segments(session):
        active_listings = session.exec(
            select(Listing).where(
                Listing.category_main_cb == category_main_cb,
                Listing.category_type_cb == category_type_cb,
                Listing.is_active == True,  # noqa: E712
            )
        ).all()

        prices = [listing.price_czk for listing in active_listings if listing.price_czk]
        avg_price = statistics.mean(prices) if prices else None
        median_price = statistics.median(prices) if prices else None

        price_per_m2_values = []
        for listing in active_listings:
            detail = session.exec(select(ListingDetail).where(ListingDetail.listing_id == listing.id)).first()
            if listing.price_czk and detail and detail.usable_area:
                price_per_m2_values.append(listing.price_czk / detail.usable_area)
        avg_price_per_m2 = statistics.mean(price_per_m2_values) if price_per_m2_values else None

        # new/removed "since previous snapshot for this segment"
        previous_snapshot = session.exec(
            select(AnalyticSnapshot)
            .where(
                AnalyticSnapshot.category_main_cb == category_main_cb,
                AnalyticSnapshot.category_type_cb == category_type_cb,
                AnalyticSnapshot.location_id.is_(None),
            )
            .order_by(AnalyticSnapshot.snapshot_date.desc())
        ).first()
        window_start = (
            datetime.combine(previous_snapshot.snapshot_date, datetime.min.time())
            if previous_snapshot
            else datetime.utcnow() - timedelta(days=1)
        )

        new_count = session.exec(
            select(Listing).where(
                Listing.category_main_cb == category_main_cb,
                Listing.category_type_cb == category_type_cb,
                Listing.first_seen_at >= window_start,
            )
        ).all()
        removed_count = session.exec(
            select(Listing).where(
                Listing.category_main_cb == category_main_cb,
                Listing.category_type_cb == category_type_cb,
                Listing.removed_at.is_not(None),
                Listing.removed_at >= window_start,
            )
        ).all()

        dom_samples = _days_on_market_samples(session, category_main_cb, category_type_cb)
        median_dom = statistics.median(dom_samples) if dom_samples else None
        avg_dom = statistics.mean(dom_samples) if dom_samples else None

        median_change_pct, had_drop_flags = _price_change_stats(
            session, [listing.id for listing in active_listings]
        )
        price_drop_share = (sum(had_drop_flags) / len(had_drop_flags)) if had_drop_flags else None

        snapshot = AnalyticSnapshot(
            snapshot_date=snapshot_date,
            location_id=None,
            category_main_cb=category_main_cb,
            category_type_cb=category_type_cb,
            listing_count=len(active_listings),
            avg_price_czk=avg_price,
            median_price_czk=median_price,
            avg_price_per_m2=avg_price_per_m2,
            new_count=len(new_count),
            removed_count=len(removed_count),
            median_days_on_market=median_dom,
            avg_days_on_market=avg_dom,
            price_drop_share=price_drop_share,
            median_first_to_last_price_change_pct=median_change_pct,
        )
        session.add(snapshot)
        created.append(snapshot)

    session.commit()
    for snapshot in created:
        session.refresh(snapshot)
    return created
