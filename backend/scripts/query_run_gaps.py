"""Query coverage_gap RunItemLog rows for given run ids via local API."""
import json
import sys
import urllib.request

API = "http://127.0.0.1:8000/api"


def main() -> None:
    run_ids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [23, 26]
    with urllib.request.urlopen(f"{API}/scraping/runs?limit=50") as resp:
        runs = {r["id"]: r for r in json.load(resp)}

    for rid in run_ids:
        r = runs.get(rid)
        if not r:
            print(f"run {rid}: not in recent list")
            continue
        print(
            f"run {rid}: status={r['status']} items_seen={r['items_seen']} "
            f"errors={r['error_count']} finished={r.get('finished_at')}"
        )
        with urllib.request.urlopen(f"{API}/scraping/runs/{rid}/items?limit=2000") as resp:
            items = json.load(resp)
        gaps = [i for i in items if i.get("stage") == "coverage_gap"]
        print(f"  coverage_gap logs: {len(gaps)}")
        for g in gaps:
            print(f"    {g.get('message')}")


if __name__ == "__main__":
    main()
