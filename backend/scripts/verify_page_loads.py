"""Simulate each main page's API fan-out against the live backend."""

from __future__ import annotations

import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api"

PAGES = {
    "prehled-trhu": [
        "/analytics/dataset-summary",
        "/analytics/new-vs-removed?days=30",
        "/analytics/price-drops?min_drop_pct=5&limit=5&include_total=false",
        "/analytics/inventory-by-region",
    ],
    "nabidky": ["/listings?page=1&page_size=25&is_active=true"],
    "mapa": [
        "/listings/map-markers?is_active=true",
        "/analytics/dataset-summary",
    ],
    "analytika": [
        "/analytics/dataset-summary",
        "/analytics/inventory-by-region",
        "/analytics/price-per-m2",
        "/analytics/new-vs-removed?days=30",
        "/analytics/price-drops?min_drop_pct=5&limit=500&include_total=false",
    ],
    "historie-cen": [],
    "pokrocile-analyzy": [
        "/analytics/advanced/market-dynamics?days=180",
        "/analytics/dataset-summary",
        "/analytics/advanced/runs?limit=20",
        "/analytics/advanced/valuation?limit=200",
        "/analytics/advanced/anomalies?min_score=1&limit=200",
        "/analytics/advanced/segments?dimension=region",
        "/analytics/advanced/spatial/heatmap",
    ],
    "sprava-scrapingu": ["/scraping/runs?limit=50"],
}


def timed_get(path: str) -> dict:
    url = f"{BASE}{path}"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            body = response.read()
            return {
                "path": path,
                "status": response.status,
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "bytes": len(body),
            }
    except Exception as exc:
        return {
            "path": path,
            "status": "error",
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "error": str(exc),
        }


def main() -> None:
    report = {}
    for page, paths in PAGES.items():
        started = time.perf_counter()
        calls = [timed_get(p) for p in paths]
        report[page] = {
            "parallel_calls": len(paths),
            "page_ms": round((time.perf_counter() - started) * 1000, 1),
            "slowest_ms": max((c["ms"] for c in calls), default=0),
            "all_ok": all(c.get("status") == 200 for c in calls),
            "calls": calls,
        }
    print(json.dumps({"base": BASE, "pages": report}, indent=2))


if __name__ == "__main__":
    main()
