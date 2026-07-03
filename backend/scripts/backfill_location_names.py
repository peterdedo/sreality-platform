"""One-off backfill: resolve Location.region names from stored raw payloads."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session

from app.core.db import engine
from app.scraping.location_backfill import backfill_location_names


def main() -> None:
    with Session(engine) as session:
        result = backfill_location_names(session)
    print(f"Location name backfill finished: {result}")


if __name__ == "__main__":
    main()
