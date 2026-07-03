"""Live coverage probe via _fetch_category_estates (slow, standalone).

Uses a throwaway ScrapingRun row and does NOT acquire the sweep lock path
(run_incremental_scrape) — calls _fetch_category_estates directly so an
in-flight sweep is not disturbed. Respects scrape_request_delay_seconds and
adds extra delay between categories to avoid competing with production traffic.
"""
import asyncio
import os
import sys
from datetime import datetime

# Allow running from repo: python scripts/live_coverage_probe.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.models import RunItemLog, ScrapingRun
from app.scraping.client import SrealityClient
from app.scraping.constants import PROPERTY_TYPES, DEAL_TYPES
from app.scraping.pipeline import _fetch_category_estates, _probe_search_total

# Historical baselines (pre third-level fan-out / offset fix) for reporting.
BASELINE_PCT = {
    (1, 1): {"label": "byty/prodej", "before_pct": 10.5, "note": "region-only undercount"},
    (2, 1): {"label": "domy/prodej", "before_pct": 2.6, "note": "sub37×region residual (418/16143)"},
    (3, 1): {"label": "pozemky/prodej", "before_pct": 11.0, "note": "region-only undercount (approx)"},
}

PROBE_CATEGORIES = [
    {"name": f"{PROPERTY_TYPES[main]} - {DEAL_TYPES[deal]}", "category_main_cb": main, "category_type_cb": deal}
    for main, deal in [(1, 1), (2, 1), (3, 1)]
]

EXTRA_DELAY_BETWEEN_CATEGORIES_S = 2.0


async def probe_category(session: Session, run: ScrapingRun, category: dict) -> dict:
    client = SrealityClient()
    base = f"category_main_cb={category['category_main_cb']}&category_type_cb={category['category_type_cb']}"
    try:
        probed_total = await _probe_search_total(client, base)
        estates, pages = await _fetch_category_estates(client, category, session, run)
    finally:
        await client.aclose()

    key = (category["category_main_cb"], category["category_type_cb"])
    gap_logs = session.exec(
        select(RunItemLog).where(RunItemLog.run_id == run.id, RunItemLog.stage == "coverage_gap")
    ).all()
    gap_msg = next((g.message for g in gap_logs if category["name"] in (g.message or "")), None)

    recovered = len(estates)
    gap = max(0, probed_total - recovered)
    gap_pct = (gap / probed_total * 100) if probed_total else 0.0

    baseline = BASELINE_PCT.get(key, {})
    return {
        "category": baseline.get("label", category["name"]),
        "probed_total": probed_total,
        "recovered": recovered,
        "gap": gap,
        "pages": pages,
        "gap_msg": gap_msg,
        "gap_pct": gap_pct,
        "before_pct_missing": baseline.get("before_pct"),
        "baseline_note": baseline.get("note"),
    }


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Set DATABASE_URL", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(db_url)
    run = ScrapingRun(run_type="incremental", category="live_coverage_probe", started_at=datetime.utcnow())
    with Session(engine) as session:
        session.add(run)
        session.commit()
        session.refresh(run)

        print(f"Probe run id={run.id} delay={settings.scrape_request_delay_seconds}s + {EXTRA_DELAY_BETWEEN_CATEGORIES_S}s/category")
        results = []
        for cat in PROBE_CATEGORIES:
            print(f"Probing {cat['name']} ...")
            results.append(await probe_category(session, run, cat))
            await asyncio.sleep(EXTRA_DELAY_BETWEEN_CATEGORIES_S)

        print("\n=== LIVE COVERAGE RESULTS ===")
        for r in results:
            before = r["before_pct_missing"]
            after = r["gap_pct"] if r["gap_pct"] is not None else 0.0
            print(f"{r['category']}: probed={r['probed_total']} recovered={r['recovered']} gap={r['gap']} pages={r['pages']}")
            print(f"  before missing: {before}% ({r['baseline_note']})")
            print(f"  after missing:  {after}%")
            if r["gap_msg"]:
                print(f"  coverage_gap log: {r['gap_msg']}")
            else:
                print("  coverage_gap log: (none — full recovery)")

        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()


if __name__ == "__main__":
    asyncio.run(main())
