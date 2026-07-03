"""Real-database integration test for GET /scraping/runs/{id}/items, the new
per-item ingest-log endpoint. Same VERIFY_DATABASE_URL convention as
test_listings_api.py / test_export.py.
"""

import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.models import RunItemLog, ScrapingRun
from app.models.run_item_log import IngestStage
from app.models.scraping_run import RunStatus, RunType

DATABASE_URL = os.environ.get("VERIFY_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN to run this integration test"
)


@pytest.fixture()
def session():
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for table in ("runitemlog", "scrapingrun"):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(session):
    from app.core.db import get_session
    from app.main import app

    def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    # See test_listings_api.py: avoid triggering app.main's lifespan (scheduler)
    # under TestClient.
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_run_items_returns_logged_failures(client, session):
    """Also a regression test: adding 2+ RunItemLog rows in one flush before
    committing triggers SQLAlchemy's batch "insertmanyvalues" path, which
    previously emitted a `::ingeststage` PG enum CAST against a column the
    migration created as plain VARCHAR -- see RunItemLog.stage's docstring."""
    run = ScrapingRun(run_type=RunType.detail_backfill, status=RunStatus.success, started_at=datetime.utcnow())
    session.add(run)
    session.commit()
    session.refresh(run)

    session.add(RunItemLog(run_id=run.id, hash_id="1234", stage=IngestStage.detail_fetch, message="timeout"))
    session.add(RunItemLog(run_id=run.id, hash_id="5678", stage=IngestStage.parse, message="unexpected shape"))
    session.commit()

    resp = client.get(f"/api/scraping/runs/{run.id}/items")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    hash_ids = {row["hash_id"] for row in body}
    assert hash_ids == {"1234", "5678"}
    stages = {row["stage"] for row in body}
    assert stages == {"detail_fetch", "parse"}


def test_list_run_items_404_for_unknown_run(client, session):
    resp = client.get("/api/scraping/runs/999999/items")
    assert resp.status_code == 404


def test_list_run_items_empty_for_clean_run(client, session):
    run = ScrapingRun(run_type=RunType.incremental, status=RunStatus.success, started_at=datetime.utcnow())
    session.add(run)
    session.commit()
    session.refresh(run)

    resp = client.get(f"/api/scraping/runs/{run.id}/items")
    assert resp.status_code == 200
    assert resp.json() == []
