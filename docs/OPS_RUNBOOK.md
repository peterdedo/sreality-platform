# Ops runbook — Sreality Platform

Single-operator production notes for Railway (API + scheduler + scrape) and Vercel (SPA).

## Secrets

| Where | Variable | Notes |
|---|---|---|
| Railway | `API_KEY` | Required in production; never `dev-local-key` |
| Vercel | `API_KEY` | **Same value** as Railway. Injected by Edge Middleware for write/export paths — **do not** set `VITE_API_KEY` (removed from SPA) |
| Railway | `DATABASE_URL` | Postgres on volume |
| Railway | `CORS_ORIGINS` | `["https://sreality-platform.vercel.app"]` |
| Railway | `INCREMENTAL_SCRAPE_CRON_HOUR` | Default `2` (02:00 UTC) |
| Railway | `INCREMENTAL_SCRAPE_CRON_DAY_OF_WEEK` | Default `sun` (once weekly) |
| Railway | `PRUNE_RAW_PAYLOADS_HOUR` | Default `5` |
| Railway | `ANALYTICS_SNAPSHOT_HOUR` | Default `4` |
| Optional | `SENTRY_DSN` | Backend error reporting |

## Scheduler

Jobs (APScheduler in-process):

1. `incremental_scrape` — weekly full-category sweep + delisting (Sunday 02:00 UTC; when no coverage_gap)
2. `analytics_snapshot` — Pokročilé analýzy recompute
3. `prune_list_raw_payloads` — delete archival `rawpayload` list rows + VACUUM

There is **no** separate `full_scrape` job (it was redundant with incremental).

## Redeploy / drain

The API process is a single Railway service. On SIGTERM the lifespan **requests cooperative scrape shutdown** (finish current page/item → `partial` with a clear redeploy message), then waits up to **150s** for scrape advisory locks to clear. Prefer:

1. Do not click „Spustit scraping“ immediately before a redeploy.
2. Prefer redeploying outside the Sunday 02:00–05:00 UTC scrape/prune window. If `GET /health` shows `scrape_busy: true`, wait for the run to finish or accept a `partial` result.
3. Soft shutdown uses a redeploy-specific message; hard kill (process dies before the flag is checked) is closed on next startup by orphan reconciliation with a different message.

Delisting is **per-category**: a slice may delist when its `coverage_gap` is within threshold (abs ≤ 5 or ≤ 0.05%). Structural gaps on domy/pozemky no longer block byt/prodej delisting. Report gaps with `python -m scripts.report_coverage_gaps <run_id> --api https://sreality-platform.vercel.app/api`.

Index-4 handoff: after a complete-enough sweep + unit backfill, write immutable CSV+manifest via `python -m scripts.export_byty_prodej_snapshot ./exports` or `GET /api/export/snapshots/byty-prodej`. Manifest includes `price_czk_unit_counts` / `price_czk_unit_non_czk_counts` — EUR/USD must not be treated as Kč by importers.

Manual prune (disk pressure):

```bash
curl -X POST -H "X-API-Key: $API_KEY" \
  https://sreality-platform-production.up.railway.app/api/scraping/prune-raw-payloads
```

## Backup / restore (RPO ~24h)

**Target:** daily logical dump; restore drill at least monthly.

### Backup (example)

```bash
# From a host that can reach Postgres (Railway CLI / one-off):
./backend/scripts/backup_pg.sh
# or:
pg_dump "$DATABASE_URL" -Fc -f "sreality-$(date -u +%Y%m%d).dump"
```

Store dumps off-volume (S3 / local encrypted drive). Keep ≥7 daily + 4 weekly.

### Restore drill checklist

1. Provision empty Postgres (local or Railway temp).
2. `pg_restore -d "$RESTORE_URL" sreality-YYYYMMDD.dump`
3. `alembic upgrade head` if dump is pre-migration (usually not needed for `-Fc` full dump).
4. Point a local backend `DATABASE_URL` at restore DB; hit `/health` and `/api/analytics/dataset-summary`.
5. Record time-to-restore (RTO) and any schema surprises.

## Health

`GET /health` returns `{ status, database, scrape_busy }`.

- `503` only when DB is unreachable (Railway healthcheck must stay green during scrapes).
- `scrape_busy: true` means sweep/backfill lock is held — informational only.

## After deploy smoke checks

1. `/health` → 200, `database: connected`
2. SPA deep link e.g. `/mapa` loads (Vercel SPA rewrite)
3. Správa scrapingu: lock-skip shows **Přeskočeno**, not Selhal
4. DevTools: client bundle must not contain the production API key string
