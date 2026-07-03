"""Aggregation queries backing the /api/analytics endpoints. New capability --
none of the four audited repos had any analytics layer at all."""

from datetime import datetime, timedelta

from sqlalchemy import func, text, literal
from sqlmodel import Session, select

from app.models import Listing, ListingAnomaly, ListingDetail, ListingValuation, Location, PriceHistory, ScrapingRun
from app.models.scraping_run import RunStatus, RunType
from app.scraping.count_reconciliation import (
    EXPECTED_CATEGORY_SLICES,
    _active_category_slice_count,
    _last_full_sweep,
    _running_sweep,
    assess_dataset_completeness,
    assess_dataset_freshness,
)
from app.scraping.snapshot_metadata import (
    build_snapshot_metadata,
    get_last_dataset_update_at,
)

UNKNOWN_REGION = "Neznámý"


def price_per_m2_by_location(session: Session, category_main_cb: int | None = None) -> list[dict]:
    region_col = func.coalesce(Listing.resolved_region_name, literal(UNKNOWN_REGION))
    stmt = (
        select(
            region_col,
            Location.district,
            Location.municipality,
            func.avg(Listing.price_czk).label("avg_price"),
            func.avg(Listing.price_czk / func.nullif(ListingDetail.usable_area, 0)).label("avg_price_per_m2"),
            func.count(Listing.id).label("listing_count"),
        )
        .join(ListingDetail, ListingDetail.listing_id == Listing.id, isouter=True)
        .join(Location, Location.id == Listing.location_id, isouter=True)
        .where(Listing.is_active == True)  # noqa: E712
    )
    if category_main_cb:
        stmt = stmt.where(Listing.category_main_cb == category_main_cb)
    stmt = stmt.group_by(region_col, Location.district, Location.municipality)

    rows = session.exec(stmt).all()
    return [
        {
            "region": r[0],
            "district": r[1],
            "municipality": r[2],
            "avg_price_czk": float(r[3]) if r[3] else None,
            "avg_price_per_m2": float(r[4]) if r[4] else None,
            "listing_count": r[5],
        }
        for r in rows
    ]


def price_evolution(session: Session, listing_id: int | None = None, days: int = 365) -> list[dict]:
    """Price history for one listing, or empty when listing_id is omitted."""
    if listing_id is None:
        return []
    since = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.listing_id == listing_id, PriceHistory.recorded_at >= since)
        .order_by(PriceHistory.recorded_at)
    )
    rows = session.exec(stmt).all()
    return [{"listing_id": r.listing_id, "price_czk": r.price_czk, "recorded_at": r.recorded_at} for r in rows]


def inventory_by_region(session: Session) -> list[dict]:
    """Count every active listing by resolved kraj (falls back to Neznámý)."""
    region_label = func.coalesce(Listing.resolved_region_name, literal(UNKNOWN_REGION))
    stmt = (
        select(region_label, func.count(Listing.id))
        .select_from(Listing)
        .where(Listing.is_active == True)  # noqa: E712
        .group_by(region_label)
    )
    rows = session.exec(stmt).all()
    results = [{"region": r[0], "listing_count": r[1]} for r in rows]
    results.sort(key=lambda row: (row["region"] == UNKNOWN_REGION, -row["listing_count"], row["region"] or ""))
    return results


def dataset_summary(session: Session) -> dict:
    """Coverage stats for the locally scraped dataset (not live Sreality totals)."""
    active_filter = Listing.is_active == True  # noqa: E712

    listing_row = session.exec(
        select(
            func.count(Listing.id).filter(active_filter),
            func.count(Listing.id),
            func.count(Listing.id).filter(
                active_filter,
                Listing.gps_lat.is_not(None),
                Listing.gps_lon.is_not(None),
            ),
            func.count(Listing.id).filter(active_filter, Listing.resolved_region_name.is_not(None)),
            func.count(Listing.id).filter(active_filter, Listing.region_source.is_(None)),
        )
    ).one()

    with_detail_count = session.exec(
        select(func.count(ListingDetail.id))
        .join(Listing, Listing.id == ListingDetail.listing_id)
        .where(active_filter)
    ).one()
    with_valuation_count = session.exec(
        select(func.count(ListingValuation.id))
        .join(Listing, Listing.id == ListingValuation.listing_id)
        .where(active_filter)
    ).one()
    with_anomaly_count = session.exec(
        select(func.count(ListingAnomaly.id))
        .join(Listing, Listing.id == ListingAnomaly.listing_id)
        .where(active_filter)
    ).one()

    region_source_rows = session.exec(
        select(Listing.region_source, func.count(Listing.id)).where(active_filter).group_by(Listing.region_source)
    ).all()
    region_source_counts = {(row[0] or "unset"): row[1] for row in region_source_rows}

    last_success = session.exec(
        select(ScrapingRun)
        .where(
            ScrapingRun.run_type == RunType.incremental,
            ScrapingRun.status == RunStatus.success,
            ScrapingRun.items_seen > 0,
        )
        .order_by(ScrapingRun.finished_at.desc())
    ).first()

    active_count, total_count, with_gps_count, with_region_count, unset_region_count = listing_row

    last_full_sweep = _last_full_sweep(session)
    running_sweep = _running_sweep(session)
    active_slice_count = _active_category_slice_count(session)
    completeness = assess_dataset_completeness(
        session,
        active_total=active_count,
        active_slice_count=active_slice_count,
        last_full_sweep=last_full_sweep,
    )
    freshness = assess_dataset_freshness(
        session,
        running_sweep=running_sweep,
        completeness=completeness,
    )
    last_update = get_last_dataset_update_at(session, running_sweep=running_sweep)
    snapshot_meta = build_snapshot_metadata(
        freshness=freshness,
        running_sweep=running_sweep,
        last_full_sweep_at=last_full_sweep.finished_at if last_full_sweep else None,
        last_successful_scrape_at=last_success.finished_at if last_success else None,
        last_dataset_update_at=last_update,
    )

    schema_revision: str | None = None
    try:
        schema_revision = session.exec(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    except Exception:
        schema_revision = None

    return {
        "active_listing_count": active_count,
        "total_listing_count": total_count,
        "active_with_gps_count": with_gps_count,
        "active_with_region_count": with_region_count,
        "active_with_detail_count": with_detail_count,
        "active_with_valuation_count": with_valuation_count,
        "active_with_anomaly_count": with_anomaly_count,
        "active_without_gps_count": max(0, active_count - with_gps_count),
        "active_without_region_count": max(0, active_count - with_region_count),
        "region_source_counts": region_source_counts,
        "region_unknown_reason_counts": {
            row[0] or "unset": row[1]
            for row in session.exec(
                select(Listing.region_unknown_reason, func.count(Listing.id))
                .where(active_filter, Listing.region_source == "unknown")
                .group_by(Listing.region_unknown_reason)
            ).all()
        },
        "unset_region_source_count": unset_region_count,
        "inventory_region_listing_sum": active_count,
        "last_successful_scrape_at": last_success.finished_at if last_success else None,
        "last_full_sweep_at": last_full_sweep.finished_at if last_full_sweep else None,
        "last_full_sweep_items_seen": last_full_sweep.items_seen if last_full_sweep else None,
        "dataset_completeness": completeness,
        "dataset_freshness": freshness,
        "active_category_slice_count": active_slice_count,
        "expected_category_slice_count": EXPECTED_CATEGORY_SLICES,
        "running_scrape": (
            {
                "id": running_sweep.id,
                "started_at": running_sweep.started_at,
                "items_seen": running_sweep.items_seen,
                "pages_fetched": running_sweep.pages_fetched,
                "items_new": running_sweep.items_new,
            }
            if running_sweep
            else None
        ),
        "schema_revision": schema_revision,
        "needs_region_backfill": unset_region_count > 0 or (region_source_counts.get("unset", 0) > 0),
        **snapshot_meta,
    }


def price_drops(
    session: Session,
    min_drop_pct: float = 5.0,
    limit: int | None = None,
    include_total: bool = True,
) -> dict:
    """Listings whose latest price is lower than the previous recorded price.

    Uses a single window-function query over the full active dataset (no N+1).
    """
    ranked = (
        select(
            PriceHistory.listing_id,
            PriceHistory.price_czk,
            func.row_number()
            .over(partition_by=PriceHistory.listing_id, order_by=PriceHistory.recorded_at.desc())
            .label("rn"),
        )
        .join(Listing, Listing.id == PriceHistory.listing_id)
        .where(Listing.is_active == True)  # noqa: E712
    ).subquery()

    latest = select(ranked.c.listing_id, ranked.c.price_czk.label("current_price_czk")).where(ranked.c.rn == 1).subquery()
    previous = select(ranked.c.listing_id, ranked.c.price_czk.label("previous_price_czk")).where(ranked.c.rn == 2).subquery()

    drop_pct = (previous.c.previous_price_czk - latest.c.current_price_czk) / previous.c.previous_price_czk * 100
    stmt = (
        select(
            Listing.id,
            Listing.title,
            previous.c.previous_price_czk,
            latest.c.current_price_czk,
            drop_pct.label("drop_pct"),
        )
        .join(latest, latest.c.listing_id == Listing.id)
        .join(previous, previous.c.listing_id == Listing.id)
        .where(previous.c.previous_price_czk > 0)
        .where(drop_pct >= min_drop_pct)
        .order_by(drop_pct.desc())
    )

    total_matched = (
        session.exec(select(func.count()).select_from(stmt.subquery())).one()
        if include_total
        else None
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = session.exec(stmt).all()
    results = [
        {
            "listing_id": row[0],
            "title": row[1],
            "previous_price_czk": row[2],
            "current_price_czk": row[3],
            "drop_pct": round(float(row[4]), 1),
        }
        for row in rows
    ]
    if not include_total and limit is not None:
        total_matched = len(results)
    return {"items": results, "total_matched": total_matched, "limit": limit}


def new_vs_removed(session: Session, days: int = 30) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    new_count = session.exec(
        select(func.count(Listing.id)).where(Listing.first_seen_at >= since)
    ).one()
    removed_count = session.exec(
        select(func.count(Listing.id)).where(Listing.removed_at.is_not(None), Listing.removed_at >= since)
    ).one()
    return {"new_count": new_count, "removed_count": removed_count, "period_days": days}
