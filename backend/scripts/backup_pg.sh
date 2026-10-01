#!/usr/bin/env bash
# Logical Postgres backup for Sreality Platform.
# Usage: DATABASE_URL=postgresql://... ./backend/scripts/backup_pg.sh [output_dir]
set -euo pipefail

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

# SQLAlchemy-style URLs use postgresql+psycopg2:// — strip the driver for pg_dump.
PG_URL="${DATABASE_URL/postgresql+psycopg2:\/\//postgresql:\/\/}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/sreality-${STAMP}.dump"

echo "Writing ${OUT_FILE}"
pg_dump "$PG_URL" -Fc -f "$OUT_FILE"
echo "Done: ${OUT_FILE} ($(du -h "$OUT_FILE" | cut -f1))"
