"""Pure geo helper functions shared by spatial.py, comparables.py, valuation.py
and anomaly.py. See docs/METHODOLOGY.md §6 for why grid cells (not resolved
district/region names) are the primary spatial unit in this project today."""

import math

EARTH_RADIUS_KM = 6371.0

# ~0.01 degrees of latitude is ~1.11km; used as a practical, fixed grid size
# for the Czech Republic's latitude range (roughly 48.5-51 N), where a degree
# of longitude is close enough to a degree of latitude in km not to bother
# with latitude-dependent longitude scaling for this coarse a grid.
GRID_STEP_DEGREES = 0.01


def grid_step_for_zoom(zoom: int | None) -> float:
    """Coarser grid at lower zoom — full 0.01° cells only when zoomed in."""
    if zoom is None:
        return GRID_STEP_DEGREES
    if zoom <= 7:
        return 0.04
    if zoom <= 8:
        return 0.02
    return GRID_STEP_DEGREES


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def grid_cell(lat: float, lon: float, step_degrees: float = GRID_STEP_DEGREES) -> tuple[str, float, float]:
    """Bin a lat/lon point into a fixed-size grid cell.

    Returns (grid_id, cell_center_lat, cell_center_lon).
    """
    lat_bin = math.floor(lat / step_degrees)
    lon_bin = math.floor(lon / step_degrees)
    center_lat = (lat_bin + 0.5) * step_degrees
    center_lon = (lon_bin + 0.5) * step_degrees
    grid_id = f"{lat_bin}_{lon_bin}"
    return grid_id, center_lat, center_lon
