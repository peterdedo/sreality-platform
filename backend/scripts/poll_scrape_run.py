"""Poll a scraping run until it completes or timeout."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api"
RUN_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 3
INTERVAL = int(sys.argv[3]) if len(sys.argv) > 3 else 20
TIMEOUT = int(sys.argv[4]) if len(sys.argv) > 4 else 900


def fetch_run() -> dict | None:
    with urllib.request.urlopen(f"{BASE}/scraping/runs?limit=20", timeout=60) as response:
        runs = json.load(response)
    for run in runs:
        if run["id"] == RUN_ID:
            return run
    return None


def snapshot(run: dict) -> dict:
    keys = [
        "id",
        "status",
        "pages_fetched",
        "items_seen",
        "items_new",
        "items_updated",
        "items_removed",
        "error_count",
        "error_message",
        "started_at",
        "finished_at",
    ]
    return {k: run.get(k) for k in keys}


def main() -> None:
    deadline = time.time() + TIMEOUT
    last: dict | None = None
    while time.time() < deadline:
        run = fetch_run()
        if run is None:
            print(json.dumps({"error": f"run {RUN_ID} not found"}))
            sys.exit(1)
        snap = snapshot(run)
        if snap != last:
            print(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **snap}), flush=True)
            last = snap
        if run["status"] != "running":
            print(json.dumps({"completed": True, **snap}))
            return
        time.sleep(INTERVAL)

    run = fetch_run()
    print(json.dumps({"completed": False, "still_running": True, **snapshot(run or {})}))


if __name__ == "__main__":
    main()
