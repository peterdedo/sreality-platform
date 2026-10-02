"""Coverage-gap parsing and per-category delist eligibility.

A full sweep logs ``coverage_gap`` RunItemLog rows with messages like::

    byt - prodej: probed_total=22540 recovered=22539 gap=1 (0.0%)

Structural residuals (listings without locality_region_id) leave small gaps
on some slices. Global "any gap → skip all delisting" blocked apartment
freshness; instead each category may delist independently when its gap is
within the completeness threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.scraping.constants import CATEGORY_COMBINATIONS

# A slice is "sufficiently complete" for delisting when either absolute gap
# or percentage is at/under these caps (byty/prodej gap=1 qualifies).
DELIST_MAX_ABS_GAP = 5
DELIST_MAX_GAP_PCT = 0.05

_GAP_MESSAGE_RE = re.compile(
    r"^(?P<name>.+):\s*probed_total=(?P<probed>\d+)\s+recovered=(?P<recovered>\d+)\s+"
    r"gap=(?P<gap>\d+)\s+\((?P<pct>[0-9.]+)%\)\s*$"
)


@dataclass(frozen=True)
class CoverageGap:
    category_name: str
    probed_total: int
    recovered: int
    gap: int
    gap_pct: float

    @property
    def allows_delist(self) -> bool:
        return gap_allows_delist(self.gap, self.gap_pct)


def gap_allows_delist(gap: int, gap_pct: float) -> bool:
    """True when residual gap is small enough to delist that category safely."""
    if gap <= 0:
        return True
    return gap <= DELIST_MAX_ABS_GAP or gap_pct <= DELIST_MAX_GAP_PCT


def parse_coverage_gap_message(message: str) -> CoverageGap | None:
    if not message:
        return None
    match = _GAP_MESSAGE_RE.match(message.strip())
    if not match:
        return None
    return CoverageGap(
        category_name=match.group("name").strip(),
        probed_total=int(match.group("probed")),
        recovered=int(match.group("recovered")),
        gap=int(match.group("gap")),
        gap_pct=float(match.group("pct")),
    )


def gaps_by_category_name(messages: list[str]) -> dict[str, CoverageGap]:
    out: dict[str, CoverageGap] = {}
    for message in messages:
        parsed = parse_coverage_gap_message(message)
        if parsed is not None:
            out[parsed.category_name] = parsed
    return out


def category_delist_plan(
    gap_messages: list[str],
    *,
    categories: list[dict] | None = None,
) -> tuple[list[dict], list[tuple[dict, CoverageGap | None]]]:
    """Return (categories_to_delist, categories_skipped_with_gap).

    Categories with no gap log are treated as fully recovered (delist OK).
    """
    cats = categories or CATEGORY_COMBINATIONS
    by_name = gaps_by_category_name(gap_messages)
    to_delist: list[dict] = []
    skipped: list[tuple[dict, CoverageGap | None]] = []
    for cat in cats:
        gap = by_name.get(cat["name"])
        if gap is None or gap.allows_delist:
            to_delist.append(cat)
        else:
            skipped.append((cat, gap))
    return to_delist, skipped
