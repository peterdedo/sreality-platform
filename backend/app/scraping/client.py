"""Resilient HTTP client for the sreality.cz JSON API.

Retry/backoff/header choices are carried over from karlosmatos/sreality-scraper's
Scrapy settings.py (RETRY_TIMES, RETRY_HTTP_CODES, AUTOTHROTTLE, realistic
browser-like headers), reimplemented on top of httpx + tenacity since the rest
of this project is plain asyncio rather than Scrapy/Twisted.
"""

import asyncio
import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {500, 502, 503, 504, 408, 429, 520, 521, 522, 523, 524}

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "cs,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.sreality.cz/hledani/prodej/byty",
}


class RetryableHTTPError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Retryable HTTP status {status_code}")


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, (httpx.TransportError, RetryableHTTPError))


class SrealityClient:
    """Thin async wrapper around httpx with retry, jittered backoff and a
    request-rate delay, mirroring karlosmatos' AUTOTHROTTLE configuration."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(headers=HEADERS, timeout=30.0)
        self._semaphore = asyncio.Semaphore(settings.scrape_concurrency)
        self.consecutive_failures = 0

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=20),
        reraise=True,
    )
    async def _get(self, url: str) -> httpx.Response:
        response = await self._client.get(url)
        if response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryableHTTPError(response.status_code)
        response.raise_for_status()
        return response

    async def get_json(self, url: str) -> dict:
        async with self._semaphore:
            await asyncio.sleep(settings.scrape_request_delay_seconds)
            try:
                response = await self._get(url)
                self.consecutive_failures = 0
                return response.json()
            except Exception:
                self.consecutive_failures += 1
                logger.error("Request failed for %s (consecutive failures: %d)", url, self.consecutive_failures)
                raise

    @property
    def should_fall_back_to_browser(self) -> bool:
        return self.consecutive_failures >= settings.scrape_consecutive_failures_before_fallback
