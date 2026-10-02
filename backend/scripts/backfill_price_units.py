"""CLI: backfill price_czk_unit for active byty/prodej from live list API.

  cd backend && python -m scripts.backfill_price_units
"""

from __future__ import annotations

import asyncio
import sys

from sqlmodel import Session

from app.core.db import engine
from app.scraping.price_unit_backfill import backfill_price_units_from_list


def main() -> int:
    async def _run() -> dict:
        with Session(engine) as session:
            return await backfill_price_units_from_list(session)

    result = asyncio.run(_run())
    print(result)
    return 0 if result.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
