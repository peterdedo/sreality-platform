"""Compare spatial heatmap payload with and without viewport/zoom params."""

from __future__ import annotations

import json
import sys
import time
from urllib.request import Request, urlopen

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api"

CASES = [
    ("full (legacy)", "/analytics/advanced/spatial/heatmap"),
    ("cz viewport z7", "/analytics/advanced/spatial/heatmap?south=48.5&west=12.5&north=51.0&east=18.5&zoom=7"),
    ("prague z10", "/analytics/advanced/spatial/heatmap?south=49.9&west=14.3&north=50.2&east=14.7&zoom=10"),
    ("prague z7 agg", "/analytics/advanced/spatial/heatmap?south=49.9&west=14.3&north=50.2&east=14.7&zoom=7"),
]


def main() -> None:
    for label, path in CASES:
        started = time.perf_counter()
        with urlopen(Request(f"{BASE}{path}"), timeout=120) as response:
            body = response.read()
            ms = (time.perf_counter() - started) * 1000
            data = json.loads(body)
            print(
                f"{label:16} {ms:7.1f} ms  {len(body):>9} B  "
                f"cells={data.get('cell_count', len(data.get('items', [])))}  "
                f"step={data.get('grid_step_degrees')}  agg={data.get('aggregated')}"
            )


if __name__ == "__main__":
    main()
