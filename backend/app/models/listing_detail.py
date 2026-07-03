from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ListingDetail(SQLModel, table=True):
    """1:1 detail record per listing. Field set is modeled directly on
    JirkaZelenka/Sreality's scrape_specific_estates(), the richest per-listing
    extraction found in the audit."""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", unique=True, index=True)

    description: Optional[str] = None
    meta_description: Optional[str] = None

    usable_area: Optional[int] = None
    floor_area: Optional[int] = None
    built_up_area: Optional[int] = None
    land_area: Optional[int] = Field(default=None, description="Plot size (m2) -- sreality's 'estate_area'/'Plocha pozemku', relevant for houses/land")
    floor: Optional[str] = None
    floor_number: Optional[int] = Field(default=None, description="Parsed from `floor` (e.g. '3/5' -> 3) via app/domain/floor.py")
    total_floors: Optional[int] = Field(default=None, description="Parsed from `floor` (e.g. '3/5' -> 5) via app/domain/floor.py")

    ownership: Optional[str] = None
    building_type: Optional[str] = None
    building_condition: Optional[str] = None
    material: Optional[str] = None
    object_kind: Optional[str] = None

    energy_efficiency_rating: Optional[str] = None
    # Raw codebook value (1=Ano, 2=Ne, 3=Castecne -- see app/domain/codebooks.py FURNISHED),
    # stored as a string like ownership/building_type/etc, NOT a bool: sreality's
    # furnished_cb is a 3-way codebook, and a naive bool() cast previously mis-stored
    # "Ne" (2) as True. See docs/METHODOLOGY.md / repo_audit history for the fix.
    furnished: Optional[str] = None
    elevator: Optional[str] = Field(default=None, description="Raw codebook value (1=Ano, 2=Ne) -- see app/domain/codebooks.py ELEVATOR")
    balcony: Optional[bool] = None
    terrace: Optional[bool] = None
    loggia: Optional[bool] = None
    cellar: Optional[bool] = None
    garage: Optional[bool] = None
    garden: Optional[bool] = Field(default=None, description="Best-effort: not independently confirmed to exist in the read API's recommendations_data, unlike balcony/terrace/cellar/garage")
    basin: Optional[bool] = None
    parking_lots: Optional[int] = None
    low_energy: Optional[bool] = None
    easy_access: Optional[bool] = None
    no_barriers: Optional[str] = None

    broker_id: Optional[str] = None
    broker_company: Optional[str] = None
    note_about_price: Optional[str] = None
    id_of_order: Optional[str] = None
    start_of_offer: Optional[str] = None
    last_updated_at: Optional[datetime] = Field(default=None, description="Sreality's own 'Aktualizace' listing-update date, parsed from Czech DD.MM.YYYY format")

    updated_at: datetime = Field(default_factory=datetime.utcnow)
