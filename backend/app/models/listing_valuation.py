from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class ValuationClassification(str, Enum):
    under_market = "under_market"
    near_market = "near_market"
    over_market = "over_market"


class ValuationConfidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unavailable = "unavailable"  # no model fitted for this segment (see docs/METHODOLOGY.md)


class ListingValuation(SQLModel, table=True):
    """Latest fair-price estimate per listing (see docs/METHODOLOGY.md §3).
    Overwritten on each recompute -- history isn't kept per-listing, only the
    ValuationModel registry tracks model versions over time."""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", unique=True, index=True)
    model_id: Optional[int] = Field(default=None, foreign_key="valuationmodel.id")

    expected_price_czk: Optional[float] = None
    expected_price_per_m2: Optional[float] = None
    residual_absolute: Optional[float] = None
    residual_percent: Optional[float] = None

    # sa_column=Column(String) on both: see ScrapingRun.status's docstring
    # (app/models/scraping_run.py) for why a bare Enum annotation is unsafe
    # here -- _write_valuation() in app/analytics/advanced/valuation.py
    # batches many new ListingValuation rows into one session.commit() per
    # segment, which is exactly the code path that triggers the native-enum
    # CAST bug on a migrations-only database.
    classification: Optional[ValuationClassification] = Field(default=None, sa_column=Column(String))
    confidence: ValuationConfidence = Field(default=ValuationConfidence.unavailable, sa_column=Column(String))

    computed_at: datetime = Field(default_factory=datetime.utcnow, index=True)
