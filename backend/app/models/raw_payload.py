from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.common import PortableJSON


class RawPayload(SQLModel, table=True):
    """Unparsed API response retained verbatim, so field-mapping bugs (like the
    CSV pipeline silently dropping fields, documented in karlosmatos'
    SCRAPING_REVIEW.md) can be replayed without re-scraping."""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: Optional[int] = Field(default=None, foreign_key="listing.id", index=True)
    hash_id: Optional[str] = Field(default=None, index=True)
    payload_type: str  # "list" | "detail"
    payload: dict = Field(sa_column=Column(PortableJSON))
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
