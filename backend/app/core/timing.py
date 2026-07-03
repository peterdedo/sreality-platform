"""Request timing middleware — adds X-Response-Time-ms header and logs slow requests."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.timing")

SLOW_MS = 500


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
        if elapsed_ms >= SLOW_MS and request.url.path.startswith("/api"):
            logger.warning(
                "slow_request path=%s method=%s ms=%.1f",
                request.url.path,
                request.method,
                elapsed_ms,
            )
        return response
