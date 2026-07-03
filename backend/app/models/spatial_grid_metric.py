from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class SpatialGridMetric(SQLModel, table=True):
    """Snapshot of grid-based spatial aggregates (see docs/METHODOLOGY.md §6).
    Grid cells are ~1.1km lat/lon bins, used as the primary spatial method
    because resolved district/region names are not populated for most
    listings today (see Limitations in the methodology doc). The heatmap API
    computes live by default; this table exists for future trend queries."""

    id: Optional[int] = Field(default=None, primary_key=True)
    grid_id: str = Field(index=True, description="'{lat_bin}_{lon_bin}'")
    lat_center: float
    lon_center: float

    category_main_cb: Optional[int] = Field(default=None, index=True, description="null = all property types")
    category_type_cb: Optional[int] = Field(default=None, index=True, description="null = all deal types")
    metric_date: date = Field(index=True)

    listing_count: int = 0
    avg_price_per_m2: Optional[float] = None
    price_drop_intensity: Optional[float] = Field(default=None, description="0..1, share of listings with a drop in last 90d")
    turnover_rate: Optional[float] = Field(default=None, description="(new_30d + removed_30d) / max(active, 1)")
