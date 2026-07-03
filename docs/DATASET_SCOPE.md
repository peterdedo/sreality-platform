# Dataset scope: statistics truth vs UI presentation

This platform is a **data product**: analytics must reflect the **most complete local scrape** stored in Postgres, not a convenience sample.

## Three layers

| Layer | Purpose | Default behaviour |
| --- | --- | --- |
| **Full scraped dataset** | Statistics truth | All aggregate endpoints scan every matching row in the local DB. Responses include `data_scope: "full_local_dataset"`. |
| **Paginated UI views** | Presentation only | Nabídky table (`GET /listings`), optional `limit` on list endpoints when a browser table would be unwieldy. |
| **UI previews** | Navigation hints | e.g. Přehled trhu price-drop top 5 — explicitly labelled, not used for aggregates. |

There is **no** “representative sample” mode for analytics.

## Truth-layer endpoints (no row cap)

- `GET /api/analytics/dataset-summary` — coverage counts (active, GPS, region, valuation, anomaly).
- `GET /api/analytics/inventory-by-region` — every active listing; unknown region → **Neznámý** (uses `resolved_region_name`, not raw `Location.region`).
- `GET /api/analytics/price-drops` — scans all active listings; `total_matched` is always full count.
- `GET /api/analytics/advanced/segments` — GROUP BY over all active listings; NULL dimensions → **Neznámý**.
- `GET /api/analytics/advanced/valuation/summary` — classification counts over full valuation table.
- `GET /api/analytics/advanced/anomalies/summary` — anomaly counts over full anomaly table.
- `GET /api/analytics/advanced/spatial/heatmap` — all GPS listings in grid cells.
- Market dynamics snapshots — pre-aggregated time series over the stored dataset.

## Presentation-only limits (documented)

| Limit | Reason |
| --- | --- |
| `GET /listings` pagination | Browser table performance |
| Optional `limit` on valuation/anomaly/price-drop **list** endpoints | Large HTML tables; omit `limit` to fetch all rows |
| Map markers | Only listings with `gps_lat` / `gps_lon` (source data gap, not arbitrary sampling) |
| Comparables (max 8) | Per-listing feature, not market-wide statistic |
| Export `max_export_rows` (default 500 000) | Memory safety when serializing one file; `X-Export-Truncated` header when hit |
| Detail page images (6) | Display layout only |
| Scraping `per_page` ≤ 100 | Sreality API maximum per request |
| Scraping uses **`offset`**, not `page` | The `page` query param repeats the same ~100 rows; offset pagination is required |
| Scraping offset ceiling ~9 900/query | API stops returning new rows; scraper auto-splits (region × sub; third level for over-cap subs). Residual gaps logged as `coverage_gap`. |

## Scrape completeness (closed)

Listing discovery is **verified complete** for practical analytics: run 26 recovered **105 480** active listings (from ~1 223 pre-fix). Residual structural gaps are **0–2%** per category and visible in logs — not silent sampling.

Full verification record: [`docs/SCRAPE_COMPLETENESS.md`](SCRAPE_COMPLETENESS.md).

**Operational follow-up only:** finish detail backfill → trigger analytics recompute.

## Verification checklist

After a scrape, confirm:

1. `dataset-summary.active_listing_count` matches `SELECT COUNT(*) FROM listing WHERE is_active`.
2. Sum of `inventory-by-region` `listing_count` equals `active_listing_count` (includes **Neznámý**).
3. `price-drops.total_matched` is computed without a `limit` query param.
4. Map loaded count (from `listingsAll`) equals `active_with_gps_count` when filters are `is_active=true`.
5. `valuation/summary.total_valued_listings` matches rows in `listing_valuation` for active listings.
6. Segment breakdown `listing_count_sum` equals `active_listing_count` for each dimension.

Example:

```bash
curl -s http://localhost:8000/api/analytics/dataset-summary | jq .
curl -s http://localhost:8000/api/analytics/inventory-by-region | jq '.listing_count_sum, .items | length'
curl -s "http://localhost:8000/api/analytics/price-drops?min_drop_pct=5" | jq '.total_matched, (.items | length)'
```

Restart the backend after code changes so new routes are registered.

Slow re-verification of scrape coverage (do not rapid-fire guarded endpoints):

```bash
python backend/scripts/live_coverage_probe.py      # needs DATABASE_URL
python backend/scripts/diagnose_rate_limits.py     # app 429 vs Sreality 200
python backend/scripts/backfill_resolved_regions.py  # after alembic upgrade 0005
```
