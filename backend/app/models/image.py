from typing import Optional

from sqlmodel import Field, SQLModel


class Image(SQLModel, table=True):
    """Listing images. None of the audited repos persisted more than a raw URL;
    downloaded_path is reserved for an optional future local-mirroring step."""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    url: str
    position: int = 0
    downloaded_path: Optional[str] = None
