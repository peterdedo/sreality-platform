from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class IngestStage(str, Enum):
    validate = "validate"
    parse = "parse"
    detail_fetch = "detail_fetch"
    persist = "persist"
    page_fetch = "page_fetch"
    # A category's fan-out (region ∪ subcategory) fetched fewer unique
    # listings than sreality's own probed total for that query. Persisted
    # (not just logger.warning'd) so silent truncation is queryable via
    # GET /scraping/runs/{id}/items instead of only visible in stdout logs.
    coverage_gap = "coverage_gap"


class RunItemLog(SQLModel, table=True):
    """One row per per-item failure during a scraping run. Fills the
    observability gap left by ScrapingRun's aggregate-only `error_count` +
    single overwritable `error_message`: before this table, the specific
    hash_id and reason for each failure were discarded the moment the
    counter was incremented (see app/scraping/pipeline.py)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="scrapingrun.id", index=True)
    hash_id: Optional[str] = Field(default=None, index=True)
    # Explicit sa_column=Column(String), NOT the SQLModel-inferred plain
    # `IngestStage` type annotation: with a bare Enum annotation, SQLAlchemy's
    # newer bulk "insertmanyvalues" path (triggered when 2+ rows are added in
    # one flush -- see _log_item_failure()'s call sites, which can log
    # multiple failures per run) emits an explicit `::ingeststage` PG enum
    # cast in the generated SQL, even though the migration created this
    # column as plain VARCHAR. That mismatch raises
    # `psycopg2.errors.UndefinedObject: type "ingeststage" does not exist`
    # the moment a run logs its second failing item. Forcing String here
    # avoids the native-enum cast entirely; IngestStage is still used
    # everywhere else as the Python-side value type.
    stage: IngestStage = Field(sa_column=Column(String))
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
