# Scrape completeness — verified status (2026-07-03)

**The data-completeness work is closed.** Listing search ingestion now recovers the bulk of the Sreality market (~105k active listings vs ~1.2k before the offset/fan-out fix). What remains is **operational follow-up only**: let the ad hoc detail backfill finish, then trigger analytics recompute once details are populated.

## Live deployment (verified)

| Metric | Value |
| --- | --- |
| Last successful full sweep | Run **26**, finished `2026-07-03T08:58:28` |
| `items_seen` (run 26) | **105 480** |
| `active_listing_count` (post sweep) | **105 480** (was ~**1 223** pre-fix) |
| Uvicorn restart for fix | **Not required** — fixed pipeline was already live during run 26 |

Accidental rapid `POST /api/scraping/trigger` calls during verification diagnosis created runs **27–37**; all were **correctly rejected** by the Postgres advisory sweep lock (zero pages fetched, no delisting side effects).

## Scraper behaviour (current)

1. **`offset` pagination** — the `page` query param repeats the same ~100 rows; all fetches use `offset` + `per_page`.
2. **2D fan-out** — when a category×deal query exceeds ~9 900 results, split by `locality_region_id` (14 Czech regions) **and** `category_sub_cb`, union by `hash_id`.
3. **3D fan-out** — when an individual subcategory slice still exceeds the cap (e.g. rodinné domy / sub 37), that sub alone is further split by region.
4. **`coverage_gap` logging** — any probed-vs-recovered shortfall is written to `RunItemLog` (`stage=coverage_gap`), increments `error_count`, and surfaces in Správa scrapingu.

Verification scripts (slow, safe — do not hammer guarded endpoints):

- `backend/scripts/diagnose_rate_limits.py` — separates app 429 vs Sreality 200
- `backend/scripts/live_coverage_probe.py` — live-probes `_fetch_category_estates` for byty/domy/pozemky

## Live coverage results

### Probe run 38 (`_fetch_category_estates`, live API)

| Category | API probed total | Recovered | Gap | After missing |
| --- | ---: | ---: | ---: | ---: |
| byty/prodej | 20 029 | 20 028 | 1 | **0.00499%** |
| domy/prodej | 21 844 | 21 401 | 443 | **2.02802%** |
| pozemky/prodej | 20 894 | 20 793 | 101 | **0.48339%** |

### Production sweep run 26 (`coverage_gap` logs)

| Category | Gap | After missing |
| --- | --- | ---: |
| byty/prodej | *(none — full recovery)* | **0%** |
| domy/prodej | 295 / 21 853 | **~1.3%** |
| pozemky/prodej | 57 / 20 887 | **~0.3%** |
| komerční/pronájem | 33 / 14 650 | **~0.2%** |

Small differences vs probe 38 are expected — Sreality totals drift between runs.

Example `coverage_gap` log line:

```text
dům - prodej: probed_total=21853 recovered=21558 gap=295 (1.3%)
```

## Final residual gap (structural, not a pagination bug)

| Category | Residual | Cause |
| --- | --- | --- |
| byty/prodej | ~0.005% | Negligible; likely timing/API edge |
| pozemky/prodej | ~0.3–0.5% | Listings with no `locality_region_id` in the search API |
| domy/prodej | ~1.3–2.03% | Same structural limit at any region-based fan-out depth |

**No fourth fan-out dimension** is attempted. Remaining gaps are fully visible through `coverage_gap` logging and pipeline warnings (`fan-out recovered X/Y`).

## Rate limit diagnosis (verification incident)

Three layers were checked by response status code and body:

| Source | Symptom | Status | Body / signature |
| --- | --- | ---: | --- |
| App inbound limiter (`heavy_endpoint_limiter`: 10 req / 60 s on guarded endpoints) | After 10 rapid `POST /api/scraping/trigger` | **429** | `{"detail":"Příliš mnoho požadavků. Zkuste to prosím později."}` + `Retry-After` |
| Sreality outbound | 20 rapid + 20 slow search probes | **200** | Normal JSON (`pagination`, `results`) |
| In-flight backfill / sweep | Competes for outbound bandwidth | — | Not a rate limiter; backfill logs showed intermittent detail-fetch retries, not 429 storms |

The English message *"Server was temporarily limiting requests"* does **not** match the app's middleware (Czech 429 body above). It was likely a misread app 429 from a rapid verification probe, or a transient CDN/Sreality HTML error under combined load (run 26 + backfill + probe). It was **not** DB saturation: API health and `dataset-summary` stayed responsive throughout.

**Resolution:** did not loosen `heavy_endpoint_limiter`; did not restart uvicorn; did not interrupt the ad hoc `backfill_missing_details.py` process. Verification probes use built-in scrape delays plus extra pauses between categories.

## Advisory lock (verified live)

Concurrent sweep triggers while run 26 held the lock failed instantly with:

```text
Another scraping sweep is already in progress (advisory lock held); this trigger was skipped.
```

## What remains (operational only)

1. **Detail backfill** — ad hoc `backfill_missing_details.py` continues fetching `/api/v1/estates/{hash_id}` for active listings without `ListingDetail` rows. Do not restart or duplicate while it runs (backfill advisory lock).
2. **Analytics recompute** — after backfill completes, trigger `POST /api/analytics/advanced/recompute` so valuation/anomaly/snapshots reflect the full dataset with detail fields populated.
3. **Routine sweeps** — scheduled/triggered incremental scrapes maintain freshness; expect small `coverage_gap` percentages on domy/pozemky as documented above.
