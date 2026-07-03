"""Diagnose app inbound vs Sreality outbound rate limiting."""
import time

import httpx

APP = "http://127.0.0.1:8000"
SREALITY = "https://www.sreality.cz/api/v1/estates/search?category_main_cb=1&category_type_cb=1&per_page=1&offset=0"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.sreality.cz/",
}


def probe_app():
    print("=== App inbound (POST /api/scraping/trigger, 12 rapid) ===")
    for i in range(12):
        r = httpx.post(f"{APP}/api/scraping/trigger", headers={"X-API-Key": "dev-local-key"}, timeout=10)
        print(f"  {i + 1}: {r.status_code} {r.text[:200]}")


def probe_sreality(rapid: bool):
    label = "rapid (no delay)" if rapid else "slow (0.5s delay)"
    print(f"=== Sreality outbound ({label}, 20 requests) ===")
    for i in range(20):
        r = httpx.get(SREALITY, headers=HEADERS, timeout=15)
        snippet = r.text[:200].replace("\n", " ")
        print(f"  {i + 1}: {r.status_code} {snippet}")
        if not rapid:
            time.sleep(0.5)


if __name__ == "__main__":
    probe_app()
    probe_sreality(rapid=True)
    probe_sreality(rapid=False)
