from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ListingRead(BaseModel):
    """The row shape used both for the listings table (GET /listings) and the
    `listing` summary embedded in the detail response -- one shared shape so
    the frontend can use a single Listing type across list and detail views.

    Fields beyond the core Listing columns come from a LEFT JOIN against
    ListingDetail/Location (nullable if that listing has no detail/location
    yet) or are computed at serve time (price_per_m2, days_on_market,
    price_change_count, has_price_drop, image_count, description_length) --
    deliberately not stored, to avoid staleness. See app/api/listings.py.
    """

    id: int
    hash_id: str
    title: Optional[str]
    category_main_cb: int
    category_type_cb: int
    category_sub_cb: Optional[int]
    price_czk: Optional[int]
    price_per_m2: Optional[float]
    gps_lat: Optional[float]
    gps_lon: Optional[float]
    is_active: bool
    first_seen_at: datetime
    last_seen_at: datetime
    last_updated_at: Optional[datetime]
    removed_at: Optional[datetime]
    source_url: Optional[str]
    locality_text: Optional[str]
    seller_type: Optional[str]

    # from ListingDetail (nullable: not every listing has a detail row yet)
    usable_area: Optional[int] = None
    floor_area: Optional[int] = None
    land_area: Optional[int] = None
    floor: Optional[str] = None
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    ownership: Optional[str] = None
    building_type: Optional[str] = None
    building_condition: Optional[str] = None
    energy_efficiency_rating: Optional[str] = None
    furnished: Optional[str] = None
    elevator: Optional[str] = None
    balcony: Optional[bool] = None
    terrace: Optional[bool] = None
    cellar: Optional[bool] = None
    garage: Optional[bool] = None
    garden: Optional[bool] = None
    parking_lots: Optional[int] = None

    # from Location (nullable, and often null even when present -- see
    # docs/METHODOLOGY.md §6: district/region name resolution is a known gap)
    region: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None

    # computed at serve time, not stored
    days_on_market: Optional[int] = None
    price_change_count: int = 0
    has_price_drop: bool = False
    image_count: int = 0
    description_length: Optional[int] = None

    class Config:
        from_attributes = True


class ListingDetailRead(BaseModel):
    listing: ListingRead
    description: Optional[str]
    usable_area: Optional[int]
    floor_area: Optional[int]
    floor: Optional[str]
    ownership: Optional[str]
    building_type: Optional[str]
    building_condition: Optional[str]
    energy_efficiency_rating: Optional[str]
    furnished: Optional[str]
    elevator: Optional[str]
    balcony: Optional[bool]
    terrace: Optional[bool]
    loggia: Optional[bool]
    cellar: Optional[bool]
    garage: Optional[bool]
    garden: Optional[bool]
    parking_lots: Optional[int]
    broker_company: Optional[str]
    note_about_price: Optional[str]
    images: list[str] = []
    price_history: list[dict] = []


class ListingsPage(BaseModel):
    items: list[ListingRead]
    total: int
    page: int
    page_size: int
