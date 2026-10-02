"""Backfill Listing.price_czk_unit from live sreality list search payloads.

Only writes a unit when the parser extracts evidence from the source payload
(``price_czk.unit`` or ``price_currency_cb.name``). Never invents \"Kč\".
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, select

from app.models import Listing
from app.models.scraping_run import RunType, ScrapingRun
from app.scraping.client import SrealityClient
from app.scraping.constants import CATEGORY_COMBINATIONS
from app.scraping.parser import parse_list_item
from app.scraping.pipeline import _fetch_category_estates

logger = logging.getLogger(__name__)

BYTY_PRODEJ = next(
    c for c in CATEGORY_COMBINATIONS if c["category_main_cb"] == 1 and c["category_type_cb"] == 1
)


async def backfill_price_units_from_list(
    session: Session,
    *,
    category: dict[str, Any] | None = None,
    only_missing: bool = True,
) -> dict[str, int]:
    """Fetch live list pages for one category slice and update price_czk_unit.

    Returns counters: seen, updated, still_null, skipped_unchanged, errors.
    """
    cat = category or BYTY_PRODEJ
    # Temporary run row so _fetch_category_estates can attach page-failure logs.
    run = ScrapingRun(run_type=RunType.incremental, category=f"unit-backfill:{cat['name']}")
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = run.id

    client = SrealityClient()
    updated = 0
    still_null = 0
    skipped_unchanged = 0
    errors = 0
    seen = 0

    try:
        estates, _pages = await _fetch_category_estates(client, cat, session, run)
        for raw in estates:
            try:
                parsed = parse_list_item(raw)
            except Exception:
                errors += 1
                logger.exception("Failed to parse list item during unit backfill")
                continue

            hash_id = parsed.get("hash_id")
            unit = parsed.get("price_czk_unit")
            if not hash_id:
                errors += 1
                continue
            seen += 1

            listing = session.exec(select(Listing).where(Listing.hash_id == hash_id)).first()
            if listing is None:
                continue
            if only_missing and listing.price_czk_unit:
                skipped_unchanged += 1
                continue
            if not unit:
                if not listing.price_czk_unit:
                    still_null += 1
                else:
                    skipped_unchanged += 1
                continue
            if listing.price_czk_unit == unit:
                skipped_unchanged += 1
                continue

            listing.price_czk_unit = unit
            session.add(listing)
            updated += 1
            if updated % 500 == 0:
                session.commit()

        session.commit()
    finally:
        await client.aclose()
        # Remove helper run (+ its item logs) so Správa scrapingu stays clean.
        from sqlalchemy import text

        session.execute(text("DELETE FROM runitemlog WHERE run_id = :rid"), {"rid": run_id})
        session.execute(text("DELETE FROM scrapingrun WHERE id = :rid"), {"rid": run_id})
        session.commit()

    return {
        "seen": seen,
        "updated": updated,
        "still_null": still_null,
        "skipped_unchanged": skipped_unchanged,
        "errors": errors,
    }
