from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.common import PortableJSON


class ListingAnomaly(SQLModel, table=True):
    """Latest rule-based anomaly score per listing (see docs/METHODOLOGY.md §4).
    Explicitly NOT a learned/ML score -- anomaly_score is a transparent,
    capped weighted sum of the triggered flags, so it stays auditable."""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", unique=True, index=True)

    anomaly_score: float = Field(default=0.0, index=True, description="0-100, higher = more anomalous")
    anomaly_flags: list = Field(sa_column=Column(PortableJSON))
    confidence_score: float = Field(default=0.0, description="0-1, scales with how much segment data was available")

    computed_at: datetime = Field(default_factory=datetime.utcnow, index=True)
