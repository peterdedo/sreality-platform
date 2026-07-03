# Pokročilé analýzy — Methodology

This document is the authoritative, developer-facing description of every derived metric in the "Pokročilé analýzy" (Advanced Analytics) module. The in-app Czech "Metodika a omezení" panel is a condensed translation of this document — if the two ever disagree, this document is correct and the UI text should be updated to match.

Every metric below is explicitly labeled as one of:
- **Implemented** — real, tested code, computed from real data.
- **Heuristic** — a reasonable, documented rule that is *not* sourced from an authoritative reference (contrast with `app/domain/codebooks.py`'s codebook translations, which *are* sourced from sreality's own official documentation).
- **Future work** — described but not built, with the reason stated.

## 0. Data availability caveat (read this first)

As documented in `production_verification.md`, live scraping of new sreality.cz listings is currently blocked (401 on the bulk search API). Everything in this module was built and tested against synthetic fixture data (see `backend/tests/test_advanced_pipeline.py`), not a large real-world dataset. Every method below includes explicit minimum-sample-size guards specifically because of this: with too little data, the system reports "unavailable" / "low confidence" rather than fabricating a confident-looking number. Once real scraped data accumulates at volume, these thresholds should be revisited, and the valuation model's actual accuracy (which cannot be honestly assessed today, since the largest dataset it has ever been fit on is a synthetic test fixture) should be measured against held-out data before being presented as trustworthy to end users.

## 1. Market dynamics — **Implemented** (descriptive)

Module: `backend/app/analytics/advanced/market_dynamics.py`. Computes one `AnalyticSnapshot` row per `(category_main_cb, category_type_cb)` segment each time the recompute pipeline runs.

- **Active inventory** = count of currently active listings in the segment.
- **New / removed count** = counted *since the previous snapshot for this segment* (falling back to a 1-day window if no prior snapshot exists), so the resulting time series is additive regardless of how often the recompute job runs.
- **Days on market (median/avg)**: a blended sample of (a) right-censored duration (`now - first_seen_at`) for currently active listings, and (b) finalized duration (`removed_at - first_seen_at`) for listings removed within the last 90 days. This is a **simplification, not a proper survival-analysis (Kaplan-Meier) estimate** — active listings' censored durations understate their eventual true time-on-market. Documented here explicitly so it isn't mistaken for a rigorous estimate.
- **Price-drop share** = fraction of the segment's active listings with at least one recorded price decrease anywhere in their `PriceHistory`.
- **Median first-to-last price change %** = median of `(last_price - first_price) / first_price * 100` over listings with ≥2 price history rows.

Region/district is intentionally **not** a second time-series dimension in the snapshot table (would multiply rows by a mostly-null dimension given §6's location gap) — region-level breakdowns are available point-in-time via `segments` instead.

## 2. Segment analytics — **Implemented** (descriptive)

Module: `backend/app/analytics/advanced/segments.py`. Plain SQL `GROUP BY` — count, avg price, avg price/m² — over an allow-listed dimension: `category_main_cb`, `category_type_cb`, `category_sub_cb`, `building_condition`, `ownership`, `energy_efficiency_rating`, `region`. Labels reuse `app/domain/codebooks.py` (sourced from sreality's own import-interface documentation) and `app/scraping/constants.py` — not re-translated.

## 3. Fair-price model (valuation) — **Implemented, baseline only**

Module: `backend/app/analytics/advanced/valuation.py`.

**Model:** ordinary least squares (`sklearn.linear_model.LinearRegression`) on:

```
log(price_czk) ~ log(usable_area) + category_sub_cb + building_condition +
                  ownership + energy_efficiency_rating + floor_number +
                  balcony + terrace + loggia + cellar + garage + location_grid_cell
```

Fit **separately per `(category_main_cb, category_type_cb)` segment** (e.g. "Byty-Prodej" gets its own model from "Byty-Pronájem"), since price formation differs fundamentally between sale and rent and between property types. Categorical features are one-hot encoded (`drop_first=True`); the location grid cell (see §6) is also one-hot encoded, with cells containing fewer than 3 listings in the segment collapsed into a single `OTHER` bucket to bound dimensionality on small datasets.

**Minimum training size:** segments with fewer than 30 listings with both `usable_area` and `price_czk` populated get **no model** — every listing in that segment gets `classification=null, confidence="unavailable"`. This is a hard floor, not a soft warning: the system does not produce a number it can't stand behind.

**Confidence levels:**
- `high`: n_samples ≥ 100 **and** R² ≥ 0.4
- `medium`: n_samples ≥ 30 (the training floor)
- `low`: reserved for future use if a softer floor is ever introduced (currently unreachable — a segment is either ≥30, giving at least `medium`, or has no model at all)
- `unavailable`: no model for this segment

**Classification thresholds** (stated assumptions, not statistically derived cutoffs):
- `under_market`: residual ≤ -10% of expected price
- `over_market`: residual ≥ +10% of expected price
- `near_market`: otherwise

**What this model is not:** it is a transparent baseline for relative comparison within a segment, not a certified valuation. R² and coefficients are stored per-model in `ValuationModel` specifically so a reviewer can inspect *why* a listing was classified a certain way — e.g. `dict(zip(feature_list, coefficients))` gives the % price effect of each feature directly (since the target is log-price, `exp(coefficient) - 1` is the approximate multiplicative price effect).

**Future work (not built):** gradient boosting (XGBoost/LightGBM) is a natural next step if residual analysis on the linear model shows systematic non-linearity the linear form can't capture — but this was deliberately not attempted now, per the product direction to start with the simplest interpretable model and only add complexity when justified by evidence from the simpler model's residuals.

## 4. Anomaly detection — **Implemented** (rule-based, explicitly not ML)

Module: `backend/app/analytics/advanced/anomaly.py`. Every flag is a named, auditable rule. `anomaly_score` is a capped weighted sum of triggered flags (weights below) — not a learned/black-box score.

| Flag | Rule | Weight | Guard |
|---|---|---|---|
| `extreme_price_per_m2` | \|z-score\| > 2.5 vs the listing's `(category_main_cb, category_type_cb, category_sub_cb)` segment | 30 | segment needs ≥10 samples with price/m² |
| `unusual_price_change` | any single step in `PriceHistory` changes price by ≥30% | 25 | none (works with as few as 2 history points) |
| `area_layout_mismatch` | `usable_area` < 50% of a heuristic minimum plausible area for the stated `category_sub_cb` (**Heuristic**, see table below — not from an authoritative source) | 20 | none |
| `stale_listing` | age > segment's 90th percentile age (or a fixed 180-day fallback if segment has <10 samples) | 15 | none (uses fallback threshold if segment small) |
| `possible_duplicate` | another active listing within ~50m, same `category_sub_cb`, `usable_area` within ±5%, different `hash_id` | 35 | none |

`anomaly_score = min(100, sum of triggered flag weights)`. `confidence_score = min(1.0, segment_n / 30)` — scales with how much comparable data existed for the z-score and percentile calculations specifically (not a statement about the duplicate/price-change flags, which don't depend on segment size).

**Heuristic minimum-area table** (`MIN_PLAUSIBLE_AREA_BY_SUB_CB` in `anomaly.py`) — reasonable common-sense bounds for Czech flat layouts, explicitly **not** sourced from an authoritative document (contrast with the codebook translations in `app/domain/codebooks.py`, which are):

| Dispozice | Min. plausible m² |
|---|---|
| 1+kk | 15 |
| 1+1 | 20 |
| 2+kk | 25 |
| 2+1 | 35 |
| 3+kk | 45 |
| 3+1 | 55 |
| 4+kk | 60 |
| 4+1 | 70 |
| 5+kk | 75 |
| 5+1 | 85 |
| 6 a více | 100 |

**Performance note:** the duplicate check is O(n²) over active listings in the current implementation. Fine at current/expected near-term data volumes; flagged here as a scaling consideration if listing volume grows substantially (e.g. after live scraping resumes and accumulates a large national dataset), not fixed preemptively.

## 5. Comparables engine — **Implemented**

Module: `backend/app/analytics/advanced/comparables.py`. Computed per-request, not materialized.

Candidate pool: active listings, same `category_main_cb` + `category_type_cb`, `category_sub_cb` within ±1, `usable_area` within ±25%. Ranked by haversine distance on `(gps_lat, gps_lon)`. Search radius expands 5km → 10km → 20km until at least 3 comparables are found (or the 20km radius is exhausted). Returns up to 8, plus the median comparable price/m² and the subject listing's deviation from it. If fewer than 3 comparables are found even at 20km, the result includes an explicit low-confidence note rather than presenting a thin sample as reliable.

## 6. Spatial analytics — **Implemented** (grid-based primary method)

Module: `backend/app/analytics/advanced/spatial.py`, shared binning logic in `geo.py`.

**Why grid cells, not administrative districts:** `Location.region`/`district`/`municipality` are defined in the schema but **not populated** by the current scraper — only the numeric `locality_*_id` codes from sreality's API are stored, and nothing in the pipeline resolves those ids to human-readable names (this is a pre-existing gap in the base platform, not introduced by this feature; see `app/scraping/parser.py`'s `location` dict, which only ever sets the numeric ids and GPS coordinates). Grid cells (lat/lon rounded to 0.01°, ≈1.1km at Czech latitudes) are therefore the **primary** spatial unit, computed directly from `gps_lat`/`gps_lon`, which *are* reliably populated. District/region grouping remains available via the `segments` endpoint (`dimension=region`) for whenever that data gap is closed, but will return mostly empty groups today.

Per grid cell: `avg_price_per_m2` (mean over active listings with area), `price_drop_intensity` (share of active listings in the cell with ≥1 price drop in the last 90 days), `turnover_rate` ((new + removed in last 30 days) / max(active, 1)), `listing_count`.

The heatmap API computes this live on every request (cheap at current data volumes, always fresh). `SpatialGridMetric` exists as a snapshot table for future trend-over-time queries but is not read by the current heatmap endpoint.

## 7. Limitations summary

- Valuation model accuracy is unverified against real-world held-out data (§0).
- Days-on-market is a blended censored/finalized estimate, not a survival-analysis correction (§1).
- Area/layout heuristic thresholds are not authoritative (§4).
- Duplicate detection is O(n²) (§4).
- District/region spatial grouping is mostly empty today; grid cells are the reliable spatial unit (§6).
- No gradient boosting or other ML beyond OLS regression has been built (§3) — deliberately deferred pending evidence it's needed.
