"""CLI: write immutable byty/prodej CSV + manifest under an output directory.

  cd backend && python -m scripts.export_byty_prodej_snapshot ./exports
"""

from __future__ import annotations

import sys

from sqlmodel import Session

from app.core.db import engine
from app.scraping.snapshot_export import write_byty_prodej_snapshot


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    out_dir = args[0] if args else "exports"
    scrape_run_id = int(args[1]) if len(args) > 1 else None
    with Session(engine) as session:
        csv_path, manifest_path, manifest = write_byty_prodej_snapshot(
            session, out_dir, scrape_run_id=scrape_run_id
        )
    print(f"csv={csv_path}")
    print(f"manifest={manifest_path}")
    print(
        f"rows={manifest['row_count']} sha256={manifest['sha256']} "
        f"unit_missing={manifest['price_czk_unit_missing']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
