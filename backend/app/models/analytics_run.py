from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class AdvancedAnalyticsRunType(str, Enum):
    market_dynamics = "market_dynamics"
    valuation = "valuation"
    anomaly = "anomaly"
    spatial = "spatial"
    all = "all"


class AdvancedAnalyticsRunStatus(str, Enum):
    running = "running"
    success = "success"
    failed = "failed"
    partial = "partial"


class AnalyticsRun(SQLModel, table=True):
    """One row per Pokročilé analýzy recompute execution -- mirrors
    ScrapingRun's shape so the admin UI pattern (trigger button + run-history
    table) stays consistent across both scraping and advanced analytics."""

    id: Optional[int] = Field(default=None, primary_key=True)
    # sa_column=Column(String): see ScrapingRun.status's docstring
    # (app/models/scraping_run.py) for why a bare Enum annotation is unsafe.
    run_type: AdvancedAnalyticsRunType = Field(sa_column=Column(String))
    status: AdvancedAnalyticsRunStatus = Field(default=AdvancedAnalyticsRunStatus.running, sa_column=Column(String))

    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    items_processed: int = 0
    error_count: int = 0
    error_message: Optional[str] = None
