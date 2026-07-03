"""Bootstrap script: creates tables (dev convenience) and runs one incremental
scrape for a small subset of categories, so a fresh install has data to show
in the dashboard immediately."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session

from app.core.db import engine, init_db
from app.scraping.pipeline import run_incremental_scrape


async def main() -> None:
    init_db()
    with Session(engine) as session:
        # Seed with just "Byty - Prodej" to keep the first run fast.
        categories = [{"name": "Byty - Prodej", "category_main_cb": 1, "category_type_cb": 1}]
        run = await run_incremental_scrape(session, categories=categories)
        print(f"Seed run finished: status={run.status}, new={run.items_new}, seen={run.items_seen}")


if __name__ == "__main__":
    asyncio.run(main())
