"""Regression test for a production-only bug class: SQLModel fields typed as
a bare `str, Enum` subclass make SQLAlchemy's batch "insertmanyvalues" INSERT
path emit an explicit PostgreSQL native-enum CAST (e.g. `p6::valuationclassification`)
even when the actual column is plain VARCHAR (per the Alembic migrations).

This only "works" in the shared dev/verification database used throughout
this project because `app.core.db.init_db()` -- which calls
`SQLModel.metadata.create_all()` on every app startup -- silently created
orphan native PG enum types matching those class names as a side effect,
independent of the (VARCHAR) table columns. On a real production database,
where `db.py`'s own docstring says "Alembic migrations are the source of
truth ... this is only a convenience for local/dev bootstrapping", those
orphan types would never exist, and any code path that batches 2+ rows of
one of these models into a single session.commit() -- which
_write_valuation() in app/analytics/advanced/valuation.py does for every
Pokročilé analýzy recompute -- would hard-fail with
psycopg2.errors.UndefinedObject.

To make sure this test can't be fooled by that same orphan-type accident, the
`session` fixture below builds its own dedicated database and applies
*only* `alembic upgrade head` -- init_db()/create_all() is never called.
"""

import os
import subprocess

import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.models import AnalyticsRun, ListingValuation, RunItemLog, ScrapingRun
from app.models.analytics_run import AdvancedAnalyticsRunStatus, AdvancedAnalyticsRunType
from app.models.listing_valuation import ValuationClassification, ValuationConfidence
from app.models.run_item_log import IngestStage
from app.models.scraping_run import RunStatus, RunType

BASE_DATABASE_URL = os.environ.get("VERIFY_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not BASE_DATABASE_URL, reason="set VERIFY_DATABASE_URL to a real Postgres DSN to run this integration test"
)


@pytest.fixture(scope="module")
def migrations_only_database_url():
    """Builds a throwaway database and applies ONLY `alembic upgrade head`
    (never SQLModel.metadata.create_all()), so this test reflects a real
    production schema rather than the shared dev DB's create_all() history."""
    # These DSNs (from pgserver) look like
    # "postgresql://postgres:@/sreality?host=/home/.../pgdata" -- a naive
    # rsplit("/", 1) grabs the wrong "/" (inside the unix-socket path in the
    # query string). sqlalchemy.engine.make_url().set(database=...) parses it
    # correctly but then percent-encodes the socket path to "%2F..." on
    # render, which alembic's ConfigParser-based env.py then rejects
    # ("invalid interpolation syntax") because "%" is configparser's escape
    # character. So the database name is swapped with a plain string split on
    # "?" first (isolating the query string) before touching the "/" that
    # separates netloc from dbname, keeping the socket path unescaped.
    prefix, _, query = BASE_DATABASE_URL.partition("?")
    netloc, _, _old_db = prefix.rpartition("/")
    scratch_db = "sreality_enum_regression_test"
    admin_url = f"{netloc}/postgres" + (f"?{query}" if query else "")
    scratch_url = f"{netloc}/{scratch_db}" + (f"?{query}" if query else "")

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db}"'))
        conn.execute(text(f'CREATE DATABASE "{scratch_db}"'))
    admin_engine.dispose()

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=backend_dir,
        env={**os.environ, "DATABASE_URL": scratch_url},
        check=True,
        capture_output=True,
    )

    yield scratch_url

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db}"'))
    admin_engine.dispose()


@pytest.fixture()
def session(migrations_only_database_url):
    engine = create_engine(migrations_only_database_url)
    with engine.begin() as conn:
        for table in ("runitemlog", "listingvaluation", "analyticsrun", "scrapingrun", "listing"):
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    with Session(engine) as s:
        yield s
    # Dispose explicitly: the module-scoped migrations_only_database_url
    # fixture DROPs this database on teardown, which fails with
    # psycopg2.errors.ObjectInUse if any connection from this engine's pool
    # is still open.
    engine.dispose()


def test_scraping_run_batch_insert_on_migrations_only_schema(session):
    session.add(ScrapingRun(run_type=RunType.incremental, status=RunStatus.success))
    session.add(ScrapingRun(run_type=RunType.full, status=RunStatus.failed))
    session.commit()  # must not raise UndefinedObject

    rows = session.exec(select(ScrapingRun)).all()
    assert {r.status for r in rows} == {RunStatus.success, RunStatus.failed}


def test_analytics_run_batch_insert_on_migrations_only_schema(session):
    session.add(AnalyticsRun(run_type=AdvancedAnalyticsRunType.valuation, status=AdvancedAnalyticsRunStatus.success))
    session.add(AnalyticsRun(run_type=AdvancedAnalyticsRunType.anomaly, status=AdvancedAnalyticsRunStatus.failed))
    session.commit()

    rows = session.exec(select(AnalyticsRun)).all()
    assert {r.status for r in rows} == {AdvancedAnalyticsRunStatus.success, AdvancedAnalyticsRunStatus.failed}


def test_listing_valuation_batch_insert_on_migrations_only_schema(session):
    """This is the code path that matters most: _write_valuation() batches
    many rows like this into one commit per Pokročilé analýzy recompute."""
    from datetime import datetime

    from app.models import Listing

    listings = [
        Listing(
            hash_id=f"enumregress-{i}",
            title="t",
            category_main_cb=1,
            category_type_cb=1,
            price_czk=1,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
        )
        for i in range(3)
    ]
    session.add_all(listings)
    session.commit()
    for listing in listings:
        session.refresh(listing)

    classifications = [ValuationClassification.under_market, ValuationClassification.near_market, ValuationClassification.over_market]
    confidences = [ValuationConfidence.high, ValuationConfidence.medium, ValuationConfidence.low]
    for listing, classification, confidence in zip(listings, classifications, confidences):
        session.add(
            ListingValuation(listing_id=listing.id, expected_price_czk=1000, classification=classification, confidence=confidence)
        )
    session.commit()  # must not raise UndefinedObject

    rows = session.exec(select(ListingValuation)).all()
    assert {r.classification for r in rows} == set(classifications)


def test_run_item_log_batch_insert_on_migrations_only_schema(session):
    """Same check for the table that originally surfaced this bug class."""
    run = ScrapingRun(run_type=RunType.detail_backfill, status=RunStatus.success)
    session.add(run)
    session.commit()
    session.refresh(run)

    session.add(RunItemLog(run_id=run.id, hash_id="a", stage=IngestStage.detail_fetch, message="x"))
    session.add(RunItemLog(run_id=run.id, hash_id="b", stage=IngestStage.parse, message="y"))
    session.commit()

    rows = session.exec(select(RunItemLog)).all()
    assert len(rows) == 2
