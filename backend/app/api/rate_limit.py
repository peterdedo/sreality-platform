"""Minimal in-process fixed-window rate limiter.

Chosen over slowapi/redis: the guarded set is a handful of heavy admin
endpoints on a single-process app, so a small in-memory fixed-window counter
is enough and adds no new dependency or external service. If the app ever
scales to multiple worker processes, this must move to a shared store (redis)
-- documented here rather than silently assumed single-process.

Keyed by the client's API key when present (so a legitimate operator isn't
throttled by an attacker's unauthenticated floods on the same IP), falling
back to client host otherwise.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.api.deps import API_KEY_HEADER


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # key -> (window_start_epoch, count)
        self._hits: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

    def _identity(self, request: Request) -> str:
        api_key = request.headers.get(API_KEY_HEADER)
        if api_key:
            return f"key:{api_key}"
        client = request.client
        return f"ip:{client.host if client else 'unknown'}"

    def __call__(self, request: Request) -> None:
        now = time.monotonic()
        identity = self._identity(request)
        window_start, count = self._hits[identity]

        if now - window_start >= self.window_seconds:
            # new window
            self._hits[identity] = (now, 1)
            return

        if count >= self.max_requests:
            retry_after = int(self.window_seconds - (now - window_start)) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Příliš mnoho požadavků. Zkuste to prosím později.",
                headers={"Retry-After": str(retry_after)},
            )

        self._hits[identity] = (window_start, count + 1)


# Heavy endpoints (export, scrape trigger, analytics recompute): a scrape or
# full recompute is expensive, so a low ceiling is appropriate.
heavy_endpoint_limiter = RateLimiter(max_requests=10, window_seconds=60)
