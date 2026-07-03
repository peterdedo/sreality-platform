"""Czech kraj (NUTS3) reference data and offline point-in-polygon lookup.

Polygons are bundled as TopoJSON (jlacko/powerbi-cesko, ČÚZK-derived boundaries)
and decoded without external GIS dependencies.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "czech_kraje.topojson"

# Sreality locality_region_id 1–14 (matches app.scraping.constants.CZECH_REGION_IDS).
#
# IMPORTANT: sreality's numbering is NOT the NUTS/alphabetical kraj order.
# This mapping was verified live against the API (2026-07-03) by reading the
# `locality.region` + `locality.region_id` fields the search API itself
# returns per listing -- e.g. region_id=10 listings all carry
# region="Hlavní město Praha", region_id=11 "Středočeský kraj". An earlier
# NUTS-ordered assumption here mislabeled ~97 % of resolved region names.
SREALITY_REGION_NAMES: dict[int, str] = {
    1: "Jihočeský kraj",
    2: "Plzeňský kraj",
    3: "Karlovarský kraj",
    4: "Ústecký kraj",
    5: "Liberecký kraj",
    6: "Královéhradecký kraj",
    7: "Pardubický kraj",
    8: "Olomoucký kraj",
    9: "Zlínský kraj",
    10: "Hlavní město Praha",
    11: "Středočeský kraj",
    12: "Moravskoslezský kraj",
    13: "Kraj Vysočina",
    14: "Jihomoravský kraj",
}

NUTS3_TO_SREALITY_ID: dict[str, int] = {
    "CZ010": 10,  # Hlavní město Praha
    "CZ020": 11,  # Středočeský kraj
    "CZ031": 1,  # Jihočeský kraj
    "CZ032": 2,  # Plzeňský kraj
    "CZ041": 3,  # Karlovarský kraj
    "CZ042": 4,  # Ústecký kraj
    "CZ051": 5,  # Liberecký kraj
    "CZ052": 6,  # Královéhradecký kraj
    "CZ053": 7,  # Pardubický kraj
    "CZ063": 13,  # Kraj Vysočina
    "CZ064": 14,  # Jihomoravský kraj
    "CZ071": 8,  # Olomoucký kraj
    "CZ072": 9,  # Zlínský kraj
    "CZ080": 12,  # Moravskoslezský kraj
}

VALID_SREALITY_REGION_IDS = frozenset(SREALITY_REGION_NAMES)

# Rough WGS84 guard used before polygon lookup.
CZECH_LAT_MIN = 48.0
CZECH_LAT_MAX = 51.2
CZECH_LON_MIN = 12.0
CZECH_LON_MAX = 19.0


@dataclass(frozen=True)
class CzechRegionPolygon:
    region_id: int
    name: str
    exterior: tuple[tuple[float, float], ...]
    holes: tuple[tuple[tuple[float, float], ...], ...]


def _normalize_key(name: str) -> str:
    text = unicodedata.normalize("NFKD", name.strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


_NAME_LOOKUP: dict[str, tuple[int, str]] = {}
for rid, canonical in SREALITY_REGION_NAMES.items():
    _NAME_LOOKUP[_normalize_key(canonical)] = (rid, canonical)
    short = canonical.replace(" kraj", "").replace("Hlavní město ", "")
    _NAME_LOOKUP[_normalize_key(short)] = (rid, canonical)
_NAME_LOOKUP[_normalize_key("Praha")] = (10, SREALITY_REGION_NAMES[10])
_NAME_LOOKUP[_normalize_key("Praha 1")] = (10, SREALITY_REGION_NAMES[10])


def normalize_region_name(name: str | None) -> tuple[int, str] | None:
    """Map free-text kraj names from API payloads onto canonical id + label."""
    if not name or not str(name).strip():
        return None
    key = _normalize_key(str(name))
    if key in _NAME_LOOKUP:
        return _NAME_LOOKUP[key]
    for fragment, mapped in _NAME_LOOKUP.items():
        if fragment and fragment in key:
            return mapped
    return None


def region_from_locality_id(locality_region_id: int | None) -> tuple[int, str] | None:
    if locality_region_id is None or locality_region_id not in VALID_SREALITY_REGION_IDS:
        return None
    return locality_region_id, SREALITY_REGION_NAMES[locality_region_id]


def _decode_arcs(raw_arcs: list) -> list[list[tuple[float, float]]]:
    """Decode bundled kraje TopoJSON arcs (absolute lon/lat per vertex)."""
    decoded: list[list[tuple[float, float]]] = []
    for arc in raw_arcs:
        ring = [(float(point[0]), float(point[1])) for point in arc]
        decoded.append(ring)
    return decoded


def _ring_from_arcs(decoded_arcs: list[list[tuple[float, float]]], arc_refs: list[int]) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for index, arc_ref in enumerate(arc_refs):
        reverse = arc_ref < 0
        arc = decoded_arcs[~arc_ref if reverse else arc_ref]
        segment = list(reversed(arc)) if reverse else arc
        if index > 0:
            segment = segment[1:]
        coords.extend(segment)
    return coords


def _load_polygons() -> list[CzechRegionPolygon]:
    with _DATA_FILE.open(encoding="utf-8") as handle:
        topo = json.load(handle)
    decoded = _decode_arcs(topo["arcs"])
    regions: list[CzechRegionPolygon] = []
    for geom in topo["objects"]["kraje"]["geometries"]:
        props = geom.get("properties") or {}
        nuts3 = props.get("KOD_CZNUTS3") or props.get("id")
        region_id = NUTS3_TO_SREALITY_ID.get(str(nuts3))
        if region_id is None:
            continue
        name = props.get("NAZ_CZNUTS3") or SREALITY_REGION_NAMES[region_id]
        if geom["type"] == "Polygon":
            arc_groups = [geom["arcs"]]
        else:
            arc_groups = geom["arcs"]
        for arc_group in arc_groups:
            exterior = tuple(_ring_from_arcs(decoded, arc_group[0]))
            holes = tuple(tuple(_ring_from_arcs(decoded, hole)) for hole in arc_group[1:])
            regions.append(CzechRegionPolygon(region_id=region_id, name=name, exterior=exterior, holes=holes))
    return regions


@lru_cache(maxsize=1)
def region_polygons() -> tuple[CzechRegionPolygon, ...]:
    return tuple(_load_polygons())


def _point_in_ring(lon: float, lat: float, ring: Iterable[tuple[float, float]]) -> bool:
    inside = False
    points = list(ring)
    if len(points) < 3:
        return False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]
        xj, yj = points[j]
        intersects = (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_region(lon: float, lat: float, region: CzechRegionPolygon) -> bool:
    if not _point_in_ring(lon, lat, region.exterior):
        return False
    return not any(_point_in_ring(lon, lat, hole) for hole in region.holes)


def is_plausible_gps(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    if abs(lat) > 90 or abs(lon) > 180:
        return False
    if lat == 0.0 and lon == 0.0:
        return False
    return True


def is_inside_czech_bbox(lat: float, lon: float) -> bool:
    return CZECH_LAT_MIN <= lat <= CZECH_LAT_MAX and CZECH_LON_MIN <= lon <= CZECH_LON_MAX


def region_from_gps(lat: float | None, lon: float | None) -> tuple[int, str] | None:
    """Resolve kraj from WGS84 coordinates using bundled NUTS3 polygons."""
    if not is_plausible_gps(lat, lon):
        return None
    assert lat is not None and lon is not None
    if not is_inside_czech_bbox(lat, lon):
        return None
    matches = [poly for poly in region_polygons() if _point_in_region(lon, lat, poly)]
    if not matches:
        return None
    if len(matches) == 1:
        poly = matches[0]
        return poly.region_id, SREALITY_REGION_NAMES[poly.region_id]
    # Prefer smallest exterior ring when boundaries overlap numerically.
    poly = min(matches, key=lambda p: len(p.exterior))
    return poly.region_id, SREALITY_REGION_NAMES[poly.region_id]
