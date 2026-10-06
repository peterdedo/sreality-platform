#!/bin/sh
# Railway start: retry migrations, then always bind HTTP so the public domain
# stays attached. `alembic && uvicorn` previously left no active deployment
# when Postgres was briefly unreachable (host migration / disk blip).
attempt=1
max_attempts=8
while [ "$attempt" -le "$max_attempts" ]; do
  if alembic upgrade head; then
    break
  fi
  echo "alembic upgrade head failed (attempt ${attempt}/${max_attempts})"
  if [ "$attempt" -eq "$max_attempts" ]; then
    echo "starting API without a successful migration so /live stays routable"
    break
  fi
  attempt=$((attempt + 1))
  sleep 5
done

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
