"""Report coverage_gap logs for scrape runs and classify delist eligibility.

Usage:
  python -m scripts.report_coverage_gaps 317
  python -m scripts.report_coverage_gaps 317 --api https://sreality-platform.vercel.app/api
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from app.scraping.coverage_gaps import (
    DELIST_MAX_ABS_GAP,
    DELIST_MAX_GAP_PCT,
    category_delist_plan,
    parse_coverage_gap_message,
)


def _fetch_json(url: str) -> object:
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_ids", nargs="+", type=int)
    parser.add_argument(
        "--api",
        default="http://127.0.0.1:8000/api",
        help="API base including /api (default: local)",
    )
    args = parser.parse_args(argv)
    api = args.api.rstrip("/")

    print(
        f"Delist threshold: abs_gap<={DELIST_MAX_ABS_GAP} OR gap_pct<={DELIST_MAX_GAP_PCT}%\n"
    )

    for rid in args.run_ids:
        try:
            items = _fetch_json(f"{api}/scraping/runs/{rid}/items?limit=2000")
        except Exception as exc:
            print(f"run {rid}: failed to fetch items ({exc})")
            continue

        gaps = [i for i in items if i.get("stage") == "coverage_gap"]
        delist_skipped = [i for i in items if i.get("stage") == "delist_skipped"]
        messages = [g.get("message") or "" for g in gaps]

        print(f"run {rid}: coverage_gap={len(gaps)} delist_skipped={len(delist_skipped)}")
        for msg in messages:
            parsed = parse_coverage_gap_message(msg)
            if parsed is None:
                print(f"  (unparsed) {msg}")
                continue
            flag = "DELIST_OK" if parsed.allows_delist else "DELIST_BLOCKED"
            print(
                f"  [{flag}] {parsed.category_name}: "
                f"probed={parsed.probed_total} recovered={parsed.recovered} "
                f"gap={parsed.gap} ({parsed.gap_pct}%)"
            )

        to_delist, skipped = category_delist_plan(messages)
        print(f"  would_delist_slices={len(to_delist)} blocked_slices={len(skipped)}")
        for cat, gap in skipped:
            detail = f"gap={gap.gap} ({gap.gap_pct}%)" if gap else "unknown"
            print(f"    blocked: {cat['name']} ({detail})")
        byty = next((c for c in to_delist if c["category_main_cb"] == 1 and c["category_type_cb"] == 1), None)
        print(f"  byt-prodej delist eligible: {byty is not None}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
