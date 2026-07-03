"""Operator verification: freshness states and per-slice reconciliation."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, create_engine

from app.scraping.count_reconciliation import (
    assess_dataset_completeness,
    assess_dataset_freshness,
    classify_slice_reconciliation,
    count_reconciliation_report,
)


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Set DATABASE_URL", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(db_url)
    with Session(engine) as session:
        report = await count_reconciliation_report(session, live_sreality=True)
        payload = report.to_dict()

    print("=== FRESHNESS ===")
    print(f"dataset_freshness:     {payload['dataset_freshness']}")
    print(f"snapshot_state_label:  {payload.get('snapshot_state_label_cs')}")
    print(f"is_count_final:        {payload.get('is_count_final')}")
    print(f"global_comparison_safe:{payload.get('global_comparison_safe')}")
    print(f"running_scrape:        {payload.get('running_scrape')}")
    print(f"compare_guidance:      {payload.get('compare_guidance_cs', '')[:120]}...")

    print("\n=== GLOBAL COUNTS ===")
    print(f"DB active:             {payload['db_active_total']:,}")
    print(f"Sreality API sum:      {payload.get('sreality_api_slice_sum'):,}")
    print(f"Delta:                 {payload.get('db_vs_sreality_slice_delta'):,}")
    print(f"not_started slices:    {payload.get('not_started_slice_count')}")
    print(f"coverage_gap slices:   {payload.get('coverage_gap_slice_count')}")
    print(
        f"delta explainable:     {payload.get('global_delta_explainable_by_not_started')}"
    )

    print("\n=== PER-SLICE (non-aligned) ===")
    labels = payload.get("slice_status_labels_cs", {})
    for row in payload["categories"]:
        status = row["reconciliation_status"]
        if status == "aligned":
            continue
        label = labels.get(status, status)
        print(
            f"  {row['name']}: API={row['sreality_api_total']:,} DB={row['db_active_count']:,} "
            f"delta={row['delta']:+,} [{label}]"
        )

    aligned = [c for c in payload["categories"] if c["reconciliation_status"] == "aligned"]
    if aligned:
        sample = aligned[0]
        print("\n=== SAMPLE ALIGNED SLICE ===")
        print(f"  {sample['name']}: API={sample['sreality_api_total']:,} DB={sample['db_active_count']:,}")

    # Static classification sanity
    assert classify_slice_reconciliation(1000, 0, scrape_in_progress=True) == "not_started"
    assert classify_slice_reconciliation(1000, 0, scrape_in_progress=False) == "missing"
    assert classify_slice_reconciliation(1000, 980, scrape_in_progress=False) == "aligned"
    assert classify_slice_reconciliation(1000, 900, scrape_in_progress=False) == "coverage_gap"
    assert classify_slice_reconciliation(1000, 900, scrape_in_progress=True) == "in_progress"

    print("\n=== CLASSIFICATION SANITY: OK ===")

    if payload["dataset_freshness"] == "in_progress":
        print("\nPASS: Active run detected — counts must NOT be treated as final.")
        if not payload.get("global_comparison_safe"):
            print("PASS: global_comparison_safe=false during in_progress.")
    elif payload["dataset_freshness"] == "final_complete":
        print("\nPASS: Dataset final and complete — global comparison allowed.")
    else:
        print(f"\nNOTE: freshness={payload['dataset_freshness']} — review slice table above.")


if __name__ == "__main__":
    asyncio.run(main())
