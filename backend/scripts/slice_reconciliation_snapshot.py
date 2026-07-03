"""Point-in-time per-slice reconciliation while scrape may be in progress."""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func, text
from sqlmodel import Session, create_engine, select

from app.models import Listing, ScrapingRun
from app.scraping.client import SrealityClient
from app.scraping.constants import CATEGORY_COMBINATIONS, DEAL_TYPES, PROPERTY_TYPES
from app.scraping.count_reconciliation import probe_sreality_category_totals
from app.scraping.pipeline import _probe_search_total


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Set DATABASE_URL", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(db_url)
    print("Probing live Sreality API totals...")
    api_totals = await probe_sreality_category_totals()

    with Session(engine) as session:
        running = session.exec(
            select(ScrapingRun).where(ScrapingRun.status == "running").order_by(ScrapingRun.id.desc())
        ).first()
        db_active = session.exec(
            select(func.count()).select_from(Listing).where(Listing.is_active == True)  # noqa: E712
        ).one()
        dup = session.exec(
            text("SELECT COUNT(*) FROM (SELECT hash_id FROM listing GROUP BY hash_id HAVING COUNT(*)>1) t")
        ).scalar()

        rows = session.exec(
            select(Listing.category_main_cb, Listing.category_type_cb, func.count())
            .where(Listing.is_active == True)  # noqa: E712
            .group_by(Listing.category_main_cb, Listing.category_type_cb)
        ).all()
        db_by = {(m, d): c for m, d, c in rows}

    api_sum = sum(api_totals.values())
    print("\n=== RUN STATE ===")
    if running:
        print(
            f"Run #{running.id} RUNNING: items_seen={running.items_seen:,} pages={running.pages_fetched:,} "
            f"new={running.items_new:,} removed={running.items_removed}"
        )
    else:
        print("No running scrape")

    print(f"\nDB active total:        {db_active:,}")
    print(f"Run items_seen (dedup): {running.items_seen if running else 'n/a'}")
    print(f"DB vs run items_seen:   {db_active - (running.items_seen if running else 0):+,}")
    print(f"Sreality API slice sum: {api_sum:,}")
    print(f"DB vs API sum:          {db_active - api_sum:+,}")
    print(f"Duplicate hash_ids:     {dup}")

    print("\n=== PER SLICE (same query: category_main_cb + category_type_cb only) ===")
    print(f"{'Slice':<45} {'Sreality API':>12} {'DB active':>12} {'Delta':>10} {'Status':>12}")
    print("-" * 95)

    results = []
    for cat in CATEGORY_COMBINATIONS:
        key = (cat["category_main_cb"], cat["category_type_cb"])
        api = api_totals.get(key, 0)
        db = db_by.get(key, 0)
        delta = db - api
        if api == 0 and db == 0:
            status = "empty"
        elif db == 0 and api > 0:
            status = "NOT STARTED"
        elif abs(delta) <= max(2, int(api * 0.025)):
            status = "OK (~2%)"
        elif db < api:
            status = "IN PROGRESS" if running else "UNDER"
        else:
            status = "OVER (+timing?)"

        name = cat["name"]
        print(f"{name:<45} {api:>12,} {db:>12,} {delta:>+10,} {status:>12}")
        results.append(
            {
                "name": name,
                "category_main_cb": key[0],
                "category_type_cb": key[1],
                "sreality_api_total": api,
                "db_active_count": db,
                "delta": delta,
                "status": status,
            }
        )

    out = {
        "running_run": {
            "id": running.id,
            "items_seen": running.items_seen,
            "pages_fetched": running.pages_fetched,
        }
        if running
        else None,
        "db_active_total": db_active,
        "sreality_api_slice_sum": api_sum,
        "slices": results,
    }
    path = os.environ.get("AUDIT_OUTPUT", "slice_reconciliation_snapshot.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
