from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Listing(SQLModel, table=True):
    """Current-state row per sreality hash_id. Historical prices live in PriceHistory,
    not here -- directly reusing the listings/price_history split from JirkaZelenka/Sreality,
    the strongest data-model idea found across all four audited repos."""

    id: Optional[int] = Field(default=None, primary_key=True)
    hash_id: str = Field(unique=True, index=True)

    # sreality category codes (see app.scraping.constants for Czech label tables)
    category_main_cb: int = Field(index=True)  # 1=Byt, 2=Dům, 3=Pozemek, 4=Komerční, 5=Ostatní
    category_type_cb: int = Field(index=True)  # 1=Prodej, 2=Pronájem, 3=Dražba
    category_sub_cb: Optional[int] = Field(default=None, index=True)  # dispozice (1+kk, 2+1, ...)

    title: Optional[str] = None
    price_czk: Optional[int] = Field(default=None, index=True)
    price_czk_unit: Optional[str] = None
    currency: str = "CZK"

    locality_text: Optional[str] = Field(default=None, description="Raw free-text locality string from sreality's list endpoint, e.g. 'Praha 5 - Smíchov'")
    seller_type: Optional[str] = Field(
        default=None,
        index=True,
        description="Heuristic, not a confirmed API field: 'realitni_kancelar' if a broker_company was found, else 'soukroma_osoba'",
    )

    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    location_id: Optional[int] = Field(default=None, foreign_key="location.id", index=True)

    is_active: bool = Field(default=True, index=True)
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    removed_at: Optional[datetime] = Field(default=None, index=True)

    source_url: Optional[str] = None

    resolved_region_id: Optional[int] = Field(default=None, index=True, description="Sreality locality_region_id 1–14")
    resolved_region_name: Optional[str] = Field(default=None, index=True, description="Canonical Czech kraj name")
    region_source: Optional[str] = Field(
        default=None,
        index=True,
        description="detail | locality_region_id | gps_polygon | reverse_geocode | unknown",
    )
    region_unknown_reason: Optional[str] = Field(
        default=None,
        index=True,
        description="Set only when region_source=unknown: missing_gps | invalid_gps | outside_czech_bounding_box | polygon_miss | no_detail_no_region_no_gps | unresolved",
    )
