from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class PriceHistory(SQLModel, table=True):
    """Append-only price time series per listing. Directly reused idea from
    JirkaZelenka/Sreality's price_history table -- the only source repo with a
    genuine time series rather than upsert-overwrite snapshots."""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    price_czk: int
    recorded_at: datetime = Field(default_factory=datetime.utcnow, index=True)
