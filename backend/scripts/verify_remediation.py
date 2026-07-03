"""Post-remediation verification against a running API."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api"


def get(path: str, timeout: float = 30) -> tuple[int, dict | list | str, float, int]:
    url = f"{BASE}{path}"
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read()
        elapsed = (time.perf_counter() - started) * 1000
        text = body.decode("utf-8")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = text
        return response.status, payload, elapsed, len(body)


def main() -> None:
    checks: list[dict] = []

    def record(name: str, ok: bool, **extra):
        checks.append({"check": name, "ok": ok, **extra})

    # dataset-summary operational fields
    status, summary, ms, nbytes = get("/analytics/dataset-summary")
    record(
        "dataset-summary exposes schema_revision",
        status == 200 and isinstance(summary, dict) and "schema_revision" in summary,
        ms=round(ms, 1),
        schema_revision=summary.get("schema_revision") if isinstance(summary, dict) else None,
        needs_region_backfill=summary.get("needs_region_backfill") if isinstance(summary, dict) else None,
    )

    # map-markers
    status, markers, ms, nbytes = get("/listings/map-markers?is_active=true&limit=3")
    item_keys = list(markers["items"][0].keys()) if isinstance(markers, dict) and markers.get("items") else []
    record(
        "map-markers returns 200 lightweight DTO",
        status == 200
        and isinstance(markers, dict)
        and set(item_keys) <= {"id", "gps_lat", "gps_lon", "price_czk", "title", "category_main_cb", "category_type_cb", "source_url"},
        ms=round(ms, 1),
        total=markers.get("total") if isinstance(markers, dict) else None,
        item_keys=item_keys,
    )

    # price-evolution without listing_id
    status, evo, ms, nbytes = get("/analytics/price-evolution?days=365")
    record(
        "price-evolution without listing_id is empty",
        status == 200 and isinstance(evo, dict) and evo.get("items") == [],
        ms=round(ms, 1),
        bytes=nbytes,
    )

    # price-drops preview
    status, drops, ms, _ = get("/analytics/price-drops?min_drop_pct=5&limit=5&include_total=false")
    record(
        "price-drops preview honors include_total=false",
        status == 200 and isinstance(drops, dict) and len(drops.get("items", [])) <= 5,
        ms=round(ms, 1),
        items=len(drops.get("items", [])) if isinstance(drops, dict) else None,
    )

    # listing detail
    try:
        status, detail, ms, _ = get("/listings/1")
        listing = detail.get("listing", {}) if isinstance(detail, dict) else {}
        record(
            "listing detail returns 200 with price stats",
            status == 200 and "has_price_drop" in listing and "price_change_count" in listing,
            ms=round(ms, 1),
            has_price_drop=listing.get("has_price_drop"),
            price_change_count=listing.get("price_change_count"),
        )
    except urllib.error.HTTPError as exc:
        record("listing detail returns 200 with price stats", False, status=exc.code)

    # listings pagination
    status, page, ms, nbytes = get("/listings?page=1&page_size=25&is_active=true")
    record(
        "listings paginated page_size=25",
        status == 200 and isinstance(page, dict) and page.get("page_size") == 25 and len(page.get("items", [])) <= 25,
        ms=round(ms, 1),
        total=page.get("total") if isinstance(page, dict) else None,
        bytes=nbytes,
    )

    print(json.dumps({"base": BASE, "checks": checks, "all_ok": all(c["ok"] for c in checks)}, indent=2))


if __name__ == "__main__":
    main()
