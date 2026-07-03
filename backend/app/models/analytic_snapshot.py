from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class AnalyticSnapshot(SQLModel, table=True):
    """Precomputed daily rollup so dashboard queries don't aggregate the full
    listings/price_history tables on every page load. New concept -- none of the
    four source repos had any analytics layer at all."""

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_date: date = Field(index=True)
    location_id: Optional[int] = Field(default=None, foreign_key="location.id", index=True)
    category_main_cb: Optional[int] = Field(default=None, index=True)
    category_type_cb: Optional[int] = Field(default=None, index=True)

    listing_count: int = 0
    avg_price_czk: Optional[float] = None
    median_price_czk: Optional[float] = None
    avg_price_per_m2: Optional[float] = None
    new_count: int = 0
    removed_count: int = 0

    # Added for Pokročilé analýzy / market dynamics (see docs/METHODOLOGY.md).
    median_days_on_market: Optional[float] = None
    avg_days_on_market: Optional[float] = None
    price_drop_share: Optional[float] = None  # 0..1, share of listings with >=1 recorded price drop
    median_first_to_last_price_change_pct: Optional[float] = None
