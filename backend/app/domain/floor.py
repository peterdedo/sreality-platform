"""Parses sreality's "floor" strings (e.g. "3/5" meaning floor 3 of 5 total)
into structured (floor_number, total_floors) integers.

Previously duplicated privately in app/analytics/advanced/valuation.py
(`_parse_floor_number`) for the valuation model's feature engineering, and
never applied to persist real `ListingDetail.floor_number`/`total_floors`
columns at all. Extracted here so both the scraper (to populate the columns)
and the valuation model (as a feature) share one implementation.
"""

import re
from typing import Optional


def parse_floor_fraction(floor: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """"3/5" -> (3, 5); "2" -> (2, None); None/unparseable -> (None, None)."""
    if not floor:
        return None, None

    match = re.match(r"\s*(-?\d+)\s*(?:/\s*(-?\d+))?", str(floor))
    if not match:
        return None, None

    floor_number = int(match.group(1))
    total_floors = int(match.group(2)) if match.group(2) is not None else None
    return floor_number, total_floors


def parse_floor_number(floor: Optional[str]) -> Optional[int]:
    """Convenience wrapper returning just the floor number (used by the
    valuation model, which doesn't need total_floors as a feature)."""
    floor_number, _ = parse_floor_fraction(floor)
    return floor_number
