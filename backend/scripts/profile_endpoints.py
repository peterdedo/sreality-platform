"""Quick endpoint timing against a running API (default http://127.0.0.1:8000)."""

from __future__ import annotations

import json
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api"

ENDPOINTS = [
    "/analytics/dataset-summary",
    "/analytics/new-vs-removed?days=30",
    "/analytics/inventory-by-region",
    "/analytics/price-drops?min_drop_pct=5&limit=5&include_total=false",
    "/analytics/price-per-m2",
    "/analytics/price-evolution?days=365",
    "/listings?page=1&page_size=25&is_active=true",
    "/listings/map-markers?is_active=true",
    "/analytics/advanced/market-dynamics?days=180",
    "/analytics/advanced/segments?dimension=region",
    "/analytics/advanced/spatial/heatmap",
    "/analytics/advanced/runs?limit=20",
    "/scraping/runs?limit=50",
]


def timed_get(path: str) -> dict:
    url = f"{BASE}{path}"
    started = time.perf_counter()
    try:
        with urlopen(Request(url), timeout=120) as response:
            body = response.read()
            elapsed_ms = (time.perf_counter() - started) * 1000
            return {
                "path": path,
                "status": response.status,
                "ms": round(elapsed_ms, 1),
                "bytes": len(body),
            }
    except URLError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {"path": path, "status": "error", "ms": round(elapsed_ms, 1), "error": str(exc)}


def main() -> None:
    results = [timed_get(path) for path in ENDPOINTS]
    results.sort(key=lambda row: row.get("ms", 0), reverse=True)
    print(json.dumps({"base": BASE, "results": results}, indent=2))


if __name__ == "__main__":
    main()
