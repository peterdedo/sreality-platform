"""Unit tests for spatial heatmap aggregation helpers (no database required)."""

from app.analytics.advanced.spatial import aggregate_cells, filter_cells_by_bbox


def _cell(lat: float, lon: float, count: int = 10) -> dict:
    return {
        "grid_id": f"{lat}_{lon}",
        "lat_center": lat,
        "lon_center": lon,
        "listing_count": count,
        "avg_price_per_m2": 100_000.0,
        "price_drop_intensity": 0.1,
        "turnover_rate": 0.2,
    }


def test_filter_cells_by_bbox():
    cells = [_cell(50.0, 14.0), _cell(49.0, 13.0)]
    filtered = filter_cells_by_bbox(cells, 49.5, 13.5, 50.5, 14.5)
    assert len(filtered) == 1
    assert filtered[0]["lat_center"] == 50.0


def test_aggregate_cells_merges_neighbors():
    cells = [_cell(50.0, 14.0, 10), _cell(50.01, 14.01, 5)]
    merged = aggregate_cells(cells, 0.04)
    assert len(merged) == 1
    assert merged[0]["listing_count"] == 15


def test_aggregate_cells_keeps_fine_step():
    cells = [_cell(50.0, 14.0)]
    assert aggregate_cells(cells, 0.01) == cells
