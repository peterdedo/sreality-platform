"""Tests for the Quick Wins hardening pass:
T1 API-key auth, T2 rate limiting, T3 scheduler job wiring, T4 create_all gating.

The API tests use a fresh TestClient with a dependency-overridden DB session
(no scheduler lifespan), same convention as test_listings_api.py. They don't
require a real database because the guarded behavior (auth/rate-limit) is
enforced before any DB access -- so these run without VERIFY_DATABASE_URL.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.main import app


@pytest.fixture()
def client():
    # No DB session override needed: auth/rate-limit reject before DB use, and
    # for the happy-path trigger tests the work is a no-op BackgroundTask that
    # never runs synchronously under TestClient. We only assert status codes.
    return TestClient(app)


# --- T1: API key ---------------------------------------------------------

def test_trigger_without_api_key_is_rejected(client):
    resp = client.post("/api/scraping/trigger")
    assert resp.status_code == 401


def test_trigger_with_wrong_api_key_is_rejected(client):
    resp = client.post("/api/scraping/trigger", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_recompute_without_api_key_is_rejected(client):
    resp = client.post("/api/analytics/advanced/recompute")
    assert resp.status_code == 401


def test_export_without_api_key_is_rejected(client):
    resp = client.get("/api/export/listings", params={"format": "csv"})
    assert resp.status_code == 401


def test_read_endpoint_does_not_require_api_key(client):
    """GET /scraping/runs is a read endpoint and must stay open (no key). Stub
    the DB session so this asserts the auth boundary, not DB availability."""
    from app.core.db import get_session

    class _FakeExec:
        def all(self):
            return []

    class _FakeSession:
        def exec(self, *a, **k):
            return _FakeExec()

    def _override():
        yield _FakeSession()

    app.dependency_overrides[get_session] = _override
    try:
        resp = client.get("/api/scraping/runs")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.pop(get_session, None)


# --- T2: rate limiting ---------------------------------------------------

def test_rate_limit_returns_429_after_threshold(client, monkeypatch):
    from app.api import rate_limit, scraping

    # Neutralize the background scrape the trigger would otherwise queue: under
    # TestClient BackgroundTasks run after the response and would attempt a real
    # DB/network scrape. We only care about the HTTP status here.
    async def _noop():
        return None

    monkeypatch.setattr(scraping, "_run_in_background", _noop)

    limiter = rate_limit.heavy_endpoint_limiter
    orig_max, orig_window = limiter.max_requests, limiter.window_seconds
    limiter.max_requests = 3
    limiter.window_seconds = 60
    limiter._hits.clear()
    try:
        headers = {"X-API-Key": settings.api_key}
        statuses = [client.post("/api/scraping/trigger", headers=headers).status_code for _ in range(4)]
        # first 3 pass auth+limit (200), 4th is limited (429)
        assert statuses[:3] == [200, 200, 200], statuses
        assert statuses[3] == 429, statuses
    finally:
        limiter.max_requests, limiter.window_seconds = orig_max, orig_window
        limiter._hits.clear()


# --- T3: scheduler wiring ------------------------------------------------

def test_scheduler_registers_a_job_for_every_cron_setting():
    from app.scheduler import JOB_SPECS

    # Every Settings field used as a scheduling cron expression must be wired.
    cron_fields = {name for name in Settings.model_fields if name.endswith("_hour")}
    # analytics_snapshot_hour + the two *_cron_hour fields
    wired_fields = {cron_attr for (cron_attr, _func) in JOB_SPECS.values()}
    assert cron_fields == wired_fields, f"cron settings {cron_fields} != wired {wired_fields}"


def test_scheduler_job_ids_are_stable():
    from app.scheduler import JOB_SPECS

    assert set(JOB_SPECS) == {"incremental_scrape", "full_scrape", "analytics_snapshot"}


# --- T4: create_all gating + production fail-loud ------------------------

def test_is_production_flag():
    assert Settings(app_env="dev").is_production is False
    # production instances need valid secrets (see fail-loud validator), so
    # supply them here just to exercise the flag itself.
    prod_kwargs = {"api_key": "a-real-key", "database_url": "postgresql+psycopg2://u:p@db:5432/x"}
    assert Settings(app_env="production", **prod_kwargs).is_production is True
    assert Settings(app_env="prod", **prod_kwargs).is_production is True


def test_production_rejects_default_api_key():
    with pytest.raises(ValueError, match="API_KEY"):
        Settings(
            app_env="production",
            api_key="dev-local-key",
            database_url="postgresql+psycopg2://u:p@db:5432/x",
        )


def test_production_rejects_default_database_url():
    # Pass the dev-default DSN explicitly: an init kwarg overrides any
    # DATABASE_URL env var (which is set in the CI/WSL DB-test environment),
    # keeping this assertion deterministic regardless of environment.
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            app_env="production",
            api_key="a-real-key",
            database_url="postgresql+psycopg2://sreality:sreality@localhost:5432/sreality",
        )


def test_production_accepts_proper_secrets():
    s = Settings(app_env="production", api_key="a-real-key", database_url="postgresql+psycopg2://u:p@db:5432/x")
    assert s.is_production is True
