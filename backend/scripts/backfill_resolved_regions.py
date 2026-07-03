"""One-off backfill: compute resolved_region_* for all active listings."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session

from app.core.db import engine
from app.scraping.region_backfill import backfill_resolved_regions


def main() -> None:
    with Session(engine) as session:
        result = backfill_resolved_regions(session)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
