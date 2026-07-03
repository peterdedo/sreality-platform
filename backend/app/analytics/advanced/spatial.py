"""Stage 1 (descriptive): grid-based spatial aggregation. Primary spatial
method in this project -- see docs/METHODOLOGY.md §6 for why resolved
district/region names (the alternative) are not reliably populated today.
"""

import math
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.analytics.advanced.geo import GRID_STEP_DEGREES, grid_cell, grid_step_for_zoom
from app.models import Listing, ListingDetail, PriceHistory, SpatialGridMetric

PRICE_DROP_LOOKBACK_DAYS = 90
TURNOVER_LOOKBACK_DAYS = 30


def _listing_ids_with_recent_drop(session: Session, since: datetime) -> set[int]:
    """Listing ids that recorded at least one price decrease since ``since``."""
    ranked = (
        select(
            PriceHistory.listing_id,
            PriceHistory.price_czk,
            func.lag(PriceHistory.price_czk)
            .over(partition_by=PriceHistory.listing_id, order_by=PriceHistory.recorded_at)
            .label("prev_price"),
        )
        .where(PriceHistory.recorded_at >= since)
    ).subquery()
    rows = session.exec(
        select(ranked.c.listing_id).where(ranked.c.prev_price.is_not(None), ranked.c.price_czk < ranked.c.prev_price).distinct()
    ).all()
    return set(rows)


def _empty_cell(grid_id: str, lat_center: float, lon_center: float) -> dict:
    return {
        "grid_id": grid_id,
        "lat_center": lat_center,
        "lon_center": lon_center,
        "listing_count": 0,
        "new_30d": 0,
        "removed_30d": 0,
        "price_per_m2_sum": 0.0,
        "price_per_m2_count": 0,
        "drop_count": 0,
    }


def _bbox_filter_applied(
    south: float | None, west: float | None, north: float | None, east: float | None
) -> bool:
    return all(v is not None for v in (south, west, north, east))


def filter_cells_by_bbox(
    cells: list[dict],
    south: float | None,
    west: float | None,
    north: float | None,
    east: float | None,
) -> list[dict]:
    if not _bbox_filter_applied(south, west, north, east):
        return cells
    assert south is not None and west is not None and north is not None and east is not None
    return [
        cell
        for cell in cells
        if south <= cell["lat_center"] <= north and west <= cell["lon_center"] <= east
    ]


def aggregate_cells(cells: list[dict], target_step: float) -> list[dict]:
    """Merge fine grid cells into a coarser grid for lower zoom levels."""
    if target_step <= GRID_STEP_DEGREES + 1e-12:
        return cells

    merged: dict[str, dict] = {}
    for cell in cells:
        lat_bin = math.floor(cell["lat_center"] / target_step)
        lon_bin = math.floor(cell["lon_center"] / target_step)
        grid_id = f"a{lat_bin}_{lon_bin}_{target_step:g}"
        center_lat = (lat_bin + 0.5) * target_step
        center_lon = (lon_bin + 0.5) * target_step
        count = cell["listing_count"]

        bucket = merged.get(grid_id)
        if bucket is None:
            merged[grid_id] = {
                "grid_id": grid_id,
                "lat_center": center_lat,
                "lon_center": center_lon,
                "listing_count": count,
                "_price_weighted_sum": (cell["avg_price_per_m2"] or 0) * count if cell.get("avg_price_per_m2") else 0.0,
                "_drop_weighted_sum": (cell["price_drop_intensity"] or 0) * count,
                "_turnover_weighted_sum": (cell["turnover_rate"] or 0) * count,
            }
            continue

        bucket["listing_count"] += count
        if cell.get("avg_price_per_m2"):
            bucket["_price_weighted_sum"] += cell["avg_price_per_m2"] * count
        bucket["_drop_weighted_sum"] += (cell["price_drop_intensity"] or 0) * count
        bucket["_turnover_weighted_sum"] += (cell["turnover_rate"] or 0) * count

    results: list[dict] = []
    for bucket in merged.values():
        count = bucket["listing_count"]
        if count == 0:
            continue
        avg_price = bucket["_price_weighted_sum"] / count if bucket["_price_weighted_sum"] else None
        results.append(
            {
                "grid_id": bucket["grid_id"],
                "lat_center": bucket["lat_center"],
                "lon_center": bucket["lon_center"],
                "listing_count": count,
                "avg_price_per_m2": round(avg_price, 0) if avg_price else None,
                "price_drop_intensity": round(bucket["_drop_weighted_sum"] / count, 3),
                "turnover_rate": round(bucket["_turnover_weighted_sum"] / count, 3),
            }
        )
    return results


def read_cached_heatmap(
    session: Session,
    category_main_cb: int | None = None,
    category_type_cb: int | None = None,
    max_age_hours: int = 24,
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
) -> list[dict] | None:
    """Return latest persisted grid snapshot when fresh enough for page load."""
    latest_date = session.exec(select(func.max(SpatialGridMetric.metric_date))).one()
    if latest_date is None:
        return None
    cutoff_date = (datetime.utcnow() - timedelta(hours=max_age_hours)).date()
    if latest_date < cutoff_date:
        return None

    stmt = select(SpatialGridMetric).where(SpatialGridMetric.metric_date == latest_date)
    if category_main_cb is None:
        stmt = stmt.where(SpatialGridMetric.category_main_cb.is_(None))
    else:
        stmt = stmt.where(SpatialGridMetric.category_main_cb == category_main_cb)
    if category_type_cb is None:
        stmt = stmt.where(SpatialGridMetric.category_type_cb.is_(None))
    else:
        stmt = stmt.where(SpatialGridMetric.category_type_cb == category_type_cb)

    if _bbox_filter_applied(south, west, north, east):
        assert south is not None and north is not None and west is not None and east is not None
        stmt = stmt.where(
            SpatialGridMetric.lat_center >= south,
            SpatialGridMetric.lat_center <= north,
            SpatialGridMetric.lon_center >= west,
            SpatialGridMetric.lon_center <= east,
        )

    rows = session.exec(stmt).all()
    if not rows:
        return None
    return [
        {
            "grid_id": row.grid_id,
            "lat_center": row.lat_center,
            "lon_center": row.lon_center,
            "listing_count": row.listing_count,
            "avg_price_per_m2": row.avg_price_per_m2,
            "price_drop_intensity": row.price_drop_intensity,
            "turnover_rate": row.turnover_rate,
        }
        for row in rows
        if row.listing_count > 0
    ]


def compute_grid_metrics(
    session: Session,
    category_main_cb: int | None = None,
    category_type_cb: int | None = None,
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
) -> list[dict]:
    """Aggregate active GPS listings into grid cells without per-listing SQL."""

    now = datetime.utcnow()
    price_drop_since = now - timedelta(days=PRICE_DROP_LOOKBACK_DAYS)
    turnover_since = now - timedelta(days=TURNOVER_LOOKBACK_DAYS)

    stmt = select(
        Listing.id,
        Listing.gps_lat,
        Listing.gps_lon,
        Listing.price_czk,
        Listing.first_seen_at,
        Listing.removed_at,
    ).where(
        Listing.gps_lat.is_not(None),
        Listing.gps_lon.is_not(None),
        Listing.is_active == True,  # noqa: E712
    )
    if category_main_cb is not None:
        stmt = stmt.where(Listing.category_main_cb == category_main_cb)
    if category_type_cb is not None:
        stmt = stmt.where(Listing.category_type_cb == category_type_cb)
    if _bbox_filter_applied(south, west, north, east):
        assert south is not None and north is not None and west is not None and east is not None
        stmt = stmt.where(
            Listing.gps_lat >= south,
            Listing.gps_lat <= north,
            Listing.gps_lon >= west,
            Listing.gps_lon <= east,
        )
    listing_rows = session.exec(stmt).all()
    if not listing_rows:
        return []

    listing_ids = [row[0] for row in listing_rows]
    details = {
        row[0]: row[1]
        for row in session.exec(
            select(ListingDetail.listing_id, ListingDetail.usable_area).where(
                ListingDetail.listing_id.in_(listing_ids)
            )
        ).all()
    }
    drop_ids = _listing_ids_with_recent_drop(session, price_drop_since)

    cells: dict[str, dict] = {}
    for listing_id, gps_lat, gps_lon, price_czk, first_seen_at, removed_at in listing_rows:
        cell_id, center_lat, center_lon = grid_cell(gps_lat, gps_lon)
        cell = cells.setdefault(cell_id, _empty_cell(cell_id, center_lat, center_lon))
        cell["listing_count"] += 1
        if first_seen_at and first_seen_at >= turnover_since:
            cell["new_30d"] += 1
        if removed_at and removed_at >= turnover_since:
            cell["removed_30d"] += 1

        usable_area = details.get(listing_id)
        if price_czk and usable_area:
            cell["price_per_m2_sum"] += price_czk / usable_area
            cell["price_per_m2_count"] += 1
        if listing_id in drop_ids:
            cell["drop_count"] += 1

    results = []
    for cell in cells.values():
        count = cell["listing_count"]
        if count == 0:
            continue
        avg_price_per_m2 = (
            cell["price_per_m2_sum"] / cell["price_per_m2_count"] if cell["price_per_m2_count"] else None
        )
        price_drop_intensity = cell["drop_count"] / count
        turnover_rate = (cell["new_30d"] + cell["removed_30d"]) / max(count, 1)
        results.append(
            {
                "grid_id": cell["grid_id"],
                "lat_center": cell["lat_center"],
                "lon_center": cell["lon_center"],
                "listing_count": count,
                "avg_price_per_m2": round(avg_price_per_m2, 0) if avg_price_per_m2 else None,
                "price_drop_intensity": round(price_drop_intensity, 3),
                "turnover_rate": round(turnover_rate, 3),
            }
        )

    return results


def get_heatmap(
    session: Session,
    *,
    category_main_cb: int | None = None,
    category_type_cb: int | None = None,
    live: bool = False,
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
    zoom: int | None = None,
) -> dict:
    """Return heatmap cells for the requested viewport and zoom level."""
    target_step = grid_step_for_zoom(zoom)
    has_bbox = _bbox_filter_applied(south, west, north, east)

    items: list[dict] | None = None
    source = "live"
    if not live:
        items = read_cached_heatmap(
            session,
            category_main_cb,
            category_type_cb,
            south=south,
            west=west,
            north=north,
            east=east,
        )
        if items is not None:
            source = "cache"

    if items is None:
        items = compute_grid_metrics(
            session,
            category_main_cb,
            category_type_cb,
            south=south,
            west=west,
            north=north,
            east=east,
        )
    elif not has_bbox:
        items = list(items)

    aggregated = target_step > GRID_STEP_DEGREES + 1e-12
    if aggregated:
        items = aggregate_cells(items, target_step)

    return {
        "items": items,
        "grid_step_degrees": target_step,
        "bbox_applied": has_bbox,
        "cell_count": len(items),
        "aggregated": aggregated,
        "source": source,
    }


def snapshot_grid_metrics(
    session: Session,
    metric_date: date | None = None,
    category_main_cb: int | None = None,
    category_type_cb: int | None = None,
) -> list[SpatialGridMetric]:
    """Persists the current live computation into SpatialGridMetric, for
    future trend queries. The heatmap GET endpoint does not depend on this --
    it always computes live by default (see compute_grid_metrics)."""

    metric_date = metric_date or datetime.utcnow().date()
    rows = compute_grid_metrics(session, category_main_cb, category_type_cb)

    created = []
    for row in rows:
        snapshot = SpatialGridMetric(
            grid_id=row["grid_id"],
            lat_center=row["lat_center"],
            lon_center=row["lon_center"],
            category_main_cb=category_main_cb,
            category_type_cb=category_type_cb,
            metric_date=metric_date,
            listing_count=row["listing_count"],
            avg_price_per_m2=row["avg_price_per_m2"],
            price_drop_intensity=row["price_drop_intensity"],
            turnover_rate=row["turnover_rate"],
        )
        session.add(snapshot)
        created.append(snapshot)

    session.commit()
    for snapshot in created:
        session.refresh(snapshot)
    return created
