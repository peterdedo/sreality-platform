"""Rate limiting for heavy admin endpoints.

Uses Redis when ``REDIS_URL`` is reachable; otherwise falls back to an
in-process fixed-window counter (adequate for the single-worker Railway layout).

IMPORTANT: Do not add ``from __future__ import annotations`` here. FastAPI
dependency injection must see a live ``Request`` type object on ``__call__``;
postponed/string annotations make ``request`` look like a required query
param and break POST /api/scraping/trigger (and other heavy routes) with 422.
"""

import logging
import time
from collections import defaultdict
from typing import Union

from fastapi import HTTPException, Request, status

from app.api.deps import API_KEY_HEADER
from app.core.config import settings

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
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


class RedisRateLimiter:
    """Fixed-window counter backed by Redis INCR + EXPIRE."""

    def __init__(self, redis_client, max_requests: int, window_seconds: int):
        self._redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _identity(self, request: Request) -> str:
        api_key = request.headers.get(API_KEY_HEADER)
        if api_key:
            return f"key:{api_key}"
        client = request.client
        return f"ip:{client.host if client else 'unknown'}"

    def __call__(self, request: Request) -> None:
        identity = self._identity(request)
        key = f"rl:heavy:{identity}"
        try:
            count = self._redis.incr(key)
            if count == 1:
                self._redis.expire(key, self.window_seconds)
            if count > self.max_requests:
                ttl = int(self._redis.ttl(key) or self.window_seconds)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Příliš mnoho požadavků. Zkuste to prosím později.",
                    headers={"Retry-After": str(max(ttl, 1))},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Redis rate limit failed (%s); allowing request", exc)


def _build_heavy_limiter() -> Union[InMemoryRateLimiter, RedisRateLimiter]:
    max_requests = 10
    window_seconds = 60
    try:
        import redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
        client.ping()
        logger.info("Rate limiter using Redis at %s", settings.redis_url)
        return RedisRateLimiter(client, max_requests=max_requests, window_seconds=window_seconds)
    except Exception as exc:
        logger.info("Rate limiter using in-memory store (%s)", exc)
        return InMemoryRateLimiter(max_requests=max_requests, window_seconds=window_seconds)


# Heavy endpoints (export, scrape trigger, analytics recompute).
heavy_endpoint_limiter = _build_heavy_limiter()
