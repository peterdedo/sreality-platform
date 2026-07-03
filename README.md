# Sreality Platform

Realitní analytická platforma nad daty [sreality.cz](https://www.sreality.cz) — scraping, historie cen, a analytický dashboard v jednom nasazení.

This project unifies and supersedes four standalone sreality.cz scrapers audited in [`../repo_audit.md`](../repo_audit.md); see [`../architecture.md`](../architecture.md) for the full design rationale. The originals (`JirkaZelenka/Sreality`, `Anzywiz/sreality-scraper`, `karlosmatos/sreality-scraper`, `eternalvision/Sreality.cz-Parser`) are left untouched — this is a clean, standalone rebuild.

**This README distinguishes what has been verified with real runtime execution from what is only scaffolded/partial.** See [`../production_verification.md`](../production_verification.md) for the full evidence trail (exact commands run, exact outputs, exact bugs found and fixed).

## Stack

- **Backend:** FastAPI, SQLModel, PostgreSQL, Alembic, Redis, APScheduler, httpx + tenacity (scraping), Playwright (fallback path), pandas + scikit-learn (Pokročilé analýzy valuation model)
- **Frontend:** React + TypeScript + Vite + Tailwind CSS, Leaflet (map + spatial heatmap), Recharts (charts) — UI is entirely in Czech
- **Deployment:** Docker Compose (postgres, redis, backend, frontend)

## Configuration & security

All configuration is environment-variable driven (`app/core/config.py`, loaded from env or a `.env` file). Every value has a safe local-dev default; production is validated fail-loud at startup.

### Environment

- `APP_ENV` — `dev` (default) or `production`. In `production` the app refuses to start if secrets are left at their dev defaults (see below), and it skips the `create_all()` dev bootstrap so **Alembic migrations are the sole schema authority**. In `dev` it runs `create_all()` for zero-setup local bootstrapping.

### API key (guards state-changing / heavy endpoints)

- `API_KEY` — shared secret required on: `POST /api/scraping/trigger`, `POST /api/analytics/advanced/recompute`, and all `GET /api/export/*` endpoints. Send it as the `X-API-Key` request header. Read-only endpoints (listings, analytics reads, run history) stay open.
- Local dev default: `dev-local-key` (no setup needed). In `production`, leaving it at the default is a fatal startup error — set a real value.
- **Frontend:** set `VITE_API_KEY` at build time so the SPA sends the header on trigger/recompute/export; it defaults to `dev-local-key` for local work.
- Heavy endpoints are also rate-limited (in-process, 10 requests / 60 s, keyed by API key or client IP), returning `429` when exceeded.

### Scheduler (periodic jobs)

- `ENABLE_SCHEDULER` — `true` (default) / `false`. When enabled, three cron jobs are registered (`app/scheduler.py`), each configurable via a cron "hour" expression:
  - `INCREMENTAL_SCRAPE_CRON_HOUR` (default `*/6` — every 6 h)
  - `FULL_SCRAPE_CRON_HOUR` (default `3` — daily 03:00)
  - `ANALYTICS_SNAPSHOT_HOUR` (default `4` — daily 04:00; recomputes Pokročilé analýzy so valuation/anomaly/market data doesn't go stale)
  - All jobs run with `coalesce=True` and `misfire_grace_time=3600` so a brief outage doesn't skip or stampede runs. A test (`tests/test_security_and_ops.py`) asserts every `*_hour` setting is actually wired to a job.

## Pokročilé analýzy (Advanced Analytics)

A second product layer on top of the base scraping/dashboard platform: market dynamics over time, a transparent baseline fair-price model, rule-based anomaly detection, a comparables engine, and grid-based spatial heatmaps — all under a new **"Pokročilé analýzy"** nav section. Built staged and interpretable-first (descriptive → rule-based → OLS regression; no black-box ML). Full methodology, formulas, thresholds, and explicit limitations: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md); architecture: [`../architecture.md`](../architecture.md) §9. Real-database verification for this feature: see the "Advanced analytics" entries in [`../production_verification.md`](../production_verification.md).

## ✅ Verified working (real runtime execution, not just code review)

- Alembic migration `0001_initial` applied cleanly to a fresh PostgreSQL database (all 8 domain tables + `alembic_version` confirmed via `\dt`).
- Full backend + frontend running together, exercised through a real browser: all 6 pages (Přehled trhu, Nabídky, Detail nabídky, Mapa, Analytika, Historie cen, Správa scrapingu) load real data end-to-end.
- All 9 API endpoints return correct JSON when hit directly.
- Deduplication by `hash_id`, price-history append-on-change (not overwrite), and delisting detection (`is_active`/`removed_at`), verified with a two-round scenario against a real database, asserting on actual rows — see `backend/tests/test_pipeline_dry_run.py`.
- The "Spustit scraping" admin trigger fires a real background job, which is correctly recorded (including failure status and error message) and visible in the UI within seconds.
- Codebook translation for `building_type`, `building_condition`, `ownership`, `energy_efficiency_rating` — verified not just internally consistent, but **byte-for-byte identical to the `name` fields sreality.cz's own live API currently returns for these same codes** (see "Codebooks" section below).
- Two real bugs found and fixed during verification, both now covered by permanent unit tests: a Postgres-only `JSONB` column that broke portability, and a digit-extraction bug in the area parser (`"65 m2"` → `652` instead of `65`).
- Czech UI text: no leftover English strings found anywhere in `frontend/src`.
- **Pokročilé analýzy**: the full recompute pipeline (market dynamics → valuation → anomaly → spatial) was run against a real Postgres database with a 41-listing synthetic dataset engineered to include known outliers, duplicates, and price drops — every expected flag/classification/metric was verified correct via direct DB assertions (`backend/tests/test_advanced_pipeline.py`) *and* independently re-verified through the real API and real browser UI (Odhad tržní ceny, Podezřelé nabídky, Segmentace trhu, Prostorová heatmapa, Historie výpočtů all confirmed rendering correct data). The `POST /recompute` HTTP trigger was also exercised directly and correctly created a new `AnalyticsRun` row. One real UI bug was found and fixed during this pass: a "share" percentage (price-drop share) was incorrectly showing a `+` sign meant only for directional changes — see `formatPercentPlain` in `frontend/src/constants.ts`.

## ⚠️ Known partial / incomplete (stated explicitly, not glossed over)

- **`docker-compose.yml` itself has never been executed successfully.** Docker Desktop could not be started in the verification sandbox — see "Docker Desktop limitation" below. All the above verification was done by running the same services natively instead. The Compose file's own service wiring (container networking, env var propagation, the `alembic upgrade head` entrypoint) is unverified and should be re-checked on a machine where Docker actually works before relying on it.
- **Live scraping via `/api/v1/estates/search` is verified working** (run 26, 2026-07-03: ~105k listings recovered). See [`docs/SCRAPE_COMPLETENESS.md`](docs/SCRAPE_COMPLETENESS.md) for coverage numbers and residual gaps. The old `/api/cs/v2/estates` path remains dead (404).
- Redis is declared in `docker-compose.yml`/`.env.example`/`requirements.txt` but is not wired into any code path yet (APScheduler runs with its default in-memory jobstore).
- The Playwright browser-automation fallback (`app/scraping/browser_fallback.py`) collects listing URLs from search-result pages but does not extract full detail fields from the rendered DOM.
- `energy_performance_certificate` (which legal decree an energy label was issued under) is documented in sreality's own codebook but not mapped in `app/domain/codebooks.py`, since it isn't a field this scraper currently extracts.
- Some Czech UI strings are hardcoded inline in a couple of pages instead of routed through `locale/cs.ts` — cosmetic/maintainability only, not a translation error.
- **Pokročilé analýzy's fair-price model** needs a post-backfill recompute on the full ~105k listing dataset — accuracy on real data is pending that operational step (see [`docs/SCRAPE_COMPLETENESS.md`](docs/SCRAPE_COMPLETENESS.md) § What remains).
- Duplicate-listing detection in the anomaly module is O(n²) over active listings — fine at current volumes, a scaling consideration if listing volume grows substantially.
- District/region spatial grouping in Pokročilé analýzy returns mostly empty groups today, for the same reason `price-per-m2` region breakdown does in the base dashboard — see `docs/METHODOLOGY.md` §6.

## Current sreality.cz API status (as of this verification)

sreality.cz has changed its API since these repos were built. Tested directly with `curl` and with Playwright driving a real, cookie-consented browser session:

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/v1/estates/search` (list/search — **current scraper path**) | **200**, public | **Verified working** with `offset` pagination + region/sub fan-out; ~105k listings recovered in run 26 (2026-07-03). See [`docs/SCRAPE_COMPLETENESS.md`](docs/SCRAPE_COMPLETENESS.md). |
| `GET /api/cs/v2/estates` (legacy list/search) | **404** | Gone entirely |
| `GET /api/v1/estates` (bulk list/search) | **401** | Unauthorized, even replayed with a real browser session's exact headers/cookies |
| `GET /api/v1/estates/search/clusters` (map aggregate) | **200**, public | Returns geohash-clustered counts; at high zoom (`zoom=19`) it starts returning **individual estate records with `hash_id`**, which is a real, currently-working way to discover listing ids without the blocked search endpoint |
| `GET /api/v1/estates/{hash_id}` (individual detail) | **200**, public | **Works today**, no auth needed — but its response schema is different from the old `/api/cs/v2/estates/{hash_id}` schema this project's parser (`app/scraping/parser.py`) was built against (e.g. `advert_description` instead of `text.value`, flat `building_type`/`ownership`/etc. objects shaped `{"name": ..., "value": ...}` instead of raw codes under `recommendations_data`) |
| `GET /api/v1/localities/geometries` | **200**, public | Locality data, unauthenticated |

**Important:** sreality.cz's `robots.txt` sets `User-agent: * / Disallow: /` — it blocks every path for generic/unnamed crawlers and only grants (partial) access to specifically-named bots (Googlebot, SeznamBot, Bingbot, etc.), several of which still explicitly `Disallow: /api/`. The fact that an endpoint *responds* 200 to a plain `curl` or a default-configured scraper does not mean sreality.cz's stated crawling policy permits it. This project's scraper identifies with a generic browser User-Agent and does not spoof a named bot to bypass this — that would cross into access-control evasion, which is out of scope here regardless of technical feasibility.

**Net assessment:** the fast path uses `/api/v1/estates/search` with `offset` pagination and multi-level fan-out (region × subcategory). Scrape completeness is **closed** for listing discovery (~105k active listings). Residual structural gaps (~0–2% per category) are logged via `coverage_gap`. Detail backfill and analytics recompute are the remaining operational steps — not scraper debugging.

## Docker Desktop limitation encountered during verification

Docker Desktop could not be started in the sandboxed environment this project was verified in:
- `com.docker.service` (the privileged Windows service Docker Desktop depends on) was **Stopped**, and this shell had no rights to start it (`Start-Service` failed: "cannot open service").
- The `docker-desktop` WSL2 distro was crash-looping (a new `init.log.*` file appeared roughly every 8 minutes in Docker's own log directory), consistent with the sandbox not exposing the nested virtualization Docker Desktop's backend VM needs.

If you hit the same thing on your own machine, check `Get-Service com.docker.service` and whether WSL2 nested virtualization is actually available before assuming the project is broken — this is an environment issue, not a bug in `docker-compose.yml` (which, to be clear, is *itself* still unverified — see above).

## WSL verification path (what was actually used instead)

With Docker unavailable, verification used **real, unmodified PostgreSQL** via the [`pgserver`](https://pypi.org/project/pgserver/) PyPI package (an embeddable Postgres distribution), run inside **WSL2 Ubuntu** rather than Windows directly.

Why WSL and not native Windows: this machine's Windows account name contains a non-ASCII character (`ď`), which makes PostgreSQL's `initdb` fail with `invalid byte sequence for encoding "UTF8"` — a real, reproducible limitation confirmed with three different workarounds (different data directory paths, `--locale=C`, overriding the `USERNAME` env var) that all failed identically, because `initdb` reads the OS token's username directly rather than any environment variable. WSL2 Ubuntu's own account name is plain ASCII, so the identical approach works immediately there.

### Exact commands to reproduce this verification path

```bash
# 1. One-time: get a fast, isolated Python 3.11 inside WSL2 Ubuntu (no admin/sudo needed)
wsl -d Ubuntu -e bash -c "curl -LsSf https://astral.sh/uv/install.sh | bash"
wsl -d Ubuntu -e bash -c "export PATH=\$HOME/.local/bin:\$PATH; mkdir -p ~/verify2 && cd ~/verify2 && uv venv .venv --python 3.11"

# 2. Copy the backend into WSL's native filesystem (faster + avoids Windows path issues)
wsl -d Ubuntu -e bash -c "rsync -a --exclude='.venv-verify' --exclude='__pycache__' '/mnt/c/path/to/sreality-platform/backend/' ~/verify2/backend/"

# 3. Install dependencies (uv makes this fast) including pgserver for the embedded Postgres
wsl -d Ubuntu -e bash -c "export PATH=\$HOME/.local/bin:\$PATH; cd ~/verify2 && uv pip install --python .venv/bin/python -r backend/requirements.txt pgserver pytest"

# 4. Start a real Postgres server (creates ~/verify2/pgdata on first run)
wsl -d Ubuntu -e bash -c "cd ~/verify2 && .venv/bin/python -c \"
import pathlib, pgserver
s = pgserver.get_server(pathlib.Path.home()/'verify2'/'pgdata', cleanup_mode=None)
print(s.get_uri())
s.psql('CREATE DATABASE sreality;')
\""

# 5. Run Alembic migrations against it
wsl -d Ubuntu -e bash -c "cd ~/verify2/backend && export DATABASE_URL='postgresql+psycopg2://postgres@/sreality?host=/home/peterdeo/verify2/pgdata' && ../.venv/bin/python -m alembic upgrade head"

# 6. Run the full test suite, including the real-database dry-run pipeline test
wsl -d Ubuntu -e bash -c "cd ~/verify2/backend && export DATABASE_URL='postgresql+psycopg2://postgres@/sreality?host=/home/peterdeo/verify2/pgdata' VERIFY_DATABASE_URL=\$DATABASE_URL && ../.venv/bin/python -m pytest -v"

# 7. Start the real API server (WSL2 auto-forwards this port to Windows localhost)
wsl -d Ubuntu -e bash -c "cd ~/verify2/backend && export DATABASE_URL='postgresql+psycopg2://postgres@/sreality?host=/home/peterdeo/verify2/pgdata' ENABLE_SCHEDULER=false && nohup ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8123 > /tmp/uvicorn.log 2>&1 & disown"

# 8. From Windows: point the frontend's dev-server proxy at it and browse normally
#    (set VITE_API_PROXY_TARGET=http://localhost:8123 in .claude/launch.json or your shell,
#    then `npm run dev` in frontend/ as usual)
curl http://localhost:8123/health   # {"status":"ok"} confirms the tunnel works
```

If Docker works on your machine, prefer the normal `docker compose up` path (see below) — this WSL path exists purely as a documented fallback and reproducibility record for this specific verification session.

## Quick start (Docker Compose — **not yet verified end-to-end**, see above)

```bash
cp .env.example .env
make up        # builds and starts postgres, redis, backend, frontend
make migrate   # applies Alembic migrations (also runs automatically on backend start)
make seed      # optional: triggers one incremental scrape (requires live Sreality API access)
```

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs

## Project layout

```
backend/
  app/
    core/        # config, db session, logging
    models/      # SQLModel tables: listing, listing_detail, price_history, location,
                 # image, scraping_run, raw_payload, analytic_snapshot
    domain/      # codebooks.py -- Czech label mappings for sreality's numeric codebook
                 # fields, sourced from sreality's own official import-interface docs
    scraping/    # HTTP client (retry/backoff), parser, pipeline orchestrator, browser fallback
    analytics/   # aggregation queries backing /api/analytics/*
      advanced/  # Pokročilé analýzy: market dynamics, segments, valuation, anomaly, comparables, spatial, pipeline
    api/         # FastAPI routers: listings, analytics, analytics_advanced, locations, scraping
    scheduler.py # APScheduler wiring for periodic incremental scrapes
  alembic/       # migrations (source of truth for schema)
  scripts/seed.py
  tests/
docs/
  sreality_import_specification.pdf  # authoritative source for app/domain/codebooks.py
  METHODOLOGY.md                      # authoritative source for Pokročilé analýzy methodology
frontend/
  src/
    pages/       # Přehled trhu, Nabídky, Detail nabídky, Mapa, Analytika, Historie cen, Pokročilé analýzy, Správa scrapingu
    components/
      advanced/  # KpiCardsAdvanced, ValuationTable, AnomalyTable, SegmentComparisonCharts, SpatialHeatmap, ComparablesPanel, MethodologyNotes
    api/         # typed fetch client
    locale/cs.ts # all UI strings, centralized
```

## Codebooks

`app/domain/codebooks.py` translates sreality's numeric `_cb` fields (`building_type`, `building_condition`, `ownership`, `energy_efficiency_rating`, `object_kind`) into Czech labels shown on the Detail nabídky page. Every mapping is sourced from Sreality/Seznam.cz's own official XML-RPC import interface documentation (`docs/sreality_import_specification.pdf`, fetched from `admin.sreality.cz/doc/import.pdf`), not guessed — none of the four audited source repos had these mappings. The mappings were additionally cross-checked against a real, currently-live sreality.cz listing (fetched via `/api/v1/estates/{hash_id}`, which embeds its own `name` field per code) and matched character-for-character.

## How the scraper works

1. **Fast path:** `GET /api/v1/estates/search` across all 15 `category_main_cb` × `category_type_cb` combinations, using **`offset`** pagination (`per_page` ≤ 100). Large queries auto-split by dispozice and/or kraj; over-cap sub-slices get a third-level region split. Results are unioned by `hash_id`.
2. **Pipeline:** validate → deduplicate → diff against the database (new / price-changed / no-longer-listed) → persist → snapshot price → detail backfill for new listings.
3. **Delisting detection:** any active listing absent from a full sweep is marked `removed_at`.
4. **Concurrency safety:** Postgres advisory locks prevent concurrent sweeps or backfills from corrupting ground truth.
5. **Coverage logging:** probed-vs-recovered shortfalls are persisted as `RunItemLog` rows with `stage=coverage_gap`.
6. **Fallback path:** Playwright browser automation (`app/scraping/browser_fallback.py`) if the JSON API fails repeatedly — partial; not used in the verified full sweep.
7. **Raw payload retention:** every API response is stored in `raw_payloads` before parsing.

Scraping runs on a schedule via APScheduler (`ENABLE_SCHEDULER`, `INCREMENTAL_SCRAPE_CRON_HOUR` in `.env`) or on demand from **Správa scrapingu** / `POST /api/scraping/trigger` (guarded; 10 req/min rate limit). **Verified:** run 26 recovered **105 480** listings (2026-07-03). See [`docs/SCRAPE_COMPLETENESS.md`](docs/SCRAPE_COMPLETENESS.md).

## Dataset scope & intentional limits

Analytics, maps, and dashboards operate on the **full locally scraped database**, not a demo sample. See [`docs/DATASET_SCOPE.md`](docs/DATASET_SCOPE.md) for the statistics-truth vs UI-presentation split.

| Layer | Behaviour |
| --- | --- |
| **Scraping** | All 15 category×deal combinations; **offset** pagination (`per_page` ≤ 100). Large categories auto-split by dispozice or kraj when above ~9 900 results/query. |
| **Statistics truth** | Aggregates (`dataset-summary`, `inventory-by-region`, `price-drops`, segments, valuation/anomaly summaries, spatial heatmap) scan the full stored dataset. |
| **Listings API** | Paginated (`page_size` up to **1000**); the map client fetches **all pages** sequentially. |
| **Regional aggregates** | Every active listing counted; rows without a resolved region appear under **Neznámý**. |
| **Price drops** | Scans all active listings; optional `limit` only caps table rows for UI previews. |
| **Valuation/anomaly lists** | No default row cap; omit `limit` to return all rows. Use `/valuation/summary` and `/anomalies/summary` for KPI counts. |
| **Map** | Shows all active listings **with GPS**; listings without coordinates are in `dataset-summary` but not drawn. |
| **Export** | Safety cap `max_export_rows` (default **500 000**); `X-Export-Truncated` header when capped. |
| **Comparables** | Up to **8** nearest listings per detail view (by design, not a market aggregate). |
| **Přehled trhu** | Price-drop preview shows top **5** with a link to the full Analytika table. |

Use `GET /api/analytics/dataset-summary` for live coverage numbers (active count, GPS/region/valuation coverage, last successful scrape).

**Scrape completeness is closed** (~105k active listings as of run 26). Remaining work is operational: detail backfill → analytics recompute. See [`docs/SCRAPE_COMPLETENESS.md`](docs/SCRAPE_COMPLETENESS.md).

## Development without Docker

Backend:
```bash
cd backend
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
playwright install chromium
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
cd backend && pytest                 # unit tests (parser, codebooks) run without a database
VERIFY_DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/db" pytest tests/test_pipeline_dry_run.py -v
                                      # real-database integration test (insert/update/delist scenario)
cd frontend && npx tsc -b            # type-check
```
