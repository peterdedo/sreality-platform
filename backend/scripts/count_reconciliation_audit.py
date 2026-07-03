"""CLI wrapper for count reconciliation audit. See app/scraping/count_reconciliation.py."""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, create_engine

from app.scraping.count_reconciliation import count_reconciliation_report


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Set DATABASE_URL", file=sys.stderr)
        sys.exit(1)

    live = os.environ.get("AUDIT_LIVE", "1").lower() in ("1", "true", "yes")
    engine = create_engine(db_url)
    with Session(engine) as session:
        report = await count_reconciliation_report(session, live_sreality=live)

    out_path = os.environ.get("AUDIT_OUTPUT", "count_reconciliation_report.json")
    payload = report.to_dict()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("=== COUNT RECONCILIATION ===")
    print(f"DB active:              {report.db_active_total:,}")
    if report.sreality_api_slice_sum is not None:
        print(f"Sreality API slice sum: {report.sreality_api_slice_sum:,}")
        print(f"Delta:                  {report.db_active_total - report.sreality_api_slice_sum:,}")
    print(f"Completeness:           {report.dataset_completeness}")
    print(f"Category slices in DB:  {report.active_category_slice_count}/{report.expected_category_slice_count}")
    print(f"Inventory check:        {'OK' if report.inventory_sum_matches_active else 'MISMATCH'}")
    if report.partial_or_running_runs:
        print(f"Partial/running runs:   {report.partial_or_running_runs}")
    print(f"\nReport: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
