from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class RunType(str, Enum):
    full = "full"
    incremental = "incremental"
    detail_backfill = "detail_backfill"


class RunStatus(str, Enum):
    running = "running"
    success = "success"
    failed = "failed"
    partial = "partial"


class ScrapingRun(SQLModel, table=True):
    """One row per scraping job execution -- formalizes the stats that
    karlosmatos/sreality-scraper only logged to stdout in spider.closed()."""

    id: Optional[int] = Field(default=None, primary_key=True)
    # Explicit sa_column=Column(String) on both enum fields: see
    # app/models/run_item_log.py's RunItemLog.stage docstring for the full
    # mechanism. A bare Enum annotation makes SQLAlchemy's batch
    # "insertmanyvalues" INSERT path emit an explicit `::runtype`/`::runstatus`
    # PG native-enum CAST, which only works today because those orphan types
    # happen to already exist in this dev DB (created as a side effect of
    # SQLModel.metadata.create_all() in app/core/db.py's init_db(), never by
    # the Alembic migrations, which declare these columns as plain VARCHAR --
    # see alembic/versions/0001_initial.py). On a real migrations-only
    # production database the type would not exist and inserting 2+ rows in
    # one flush would fail with psycopg2.errors.UndefinedObject.
    run_type: RunType = Field(sa_column=Column(String))
    category: Optional[str] = None
    status: RunStatus = Field(default=RunStatus.running, sa_column=Column(String))

    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    pages_fetched: int = 0
    items_seen: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_removed: int = 0
    error_count: int = 0
    error_message: Optional[str] = None
