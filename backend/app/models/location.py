from typing import Optional

from sqlmodel import Field, SQLModel


class Location(SQLModel, table=True):
    """Normalized administrative location, mirrors sreality's locality hierarchy
    (kraj/okres/obec) plus GPS centroid. Reused idea from JirkaZelenka/Sreality's
    GeoData Kraj-Okres-Mesto parsing, but sourced from the API's own locality ids
    where possible instead of reverse-geocoding every listing."""

    id: Optional[int] = Field(default=None, primary_key=True)

    region: Optional[str] = Field(default=None, index=True, description="Kraj")
    district: Optional[str] = Field(default=None, index=True, description="Okres")
    municipality: Optional[str] = Field(default=None, index=True, description="Obec / Město")
    quarter: Optional[str] = Field(default=None, description="Čtvrť / městská část")
    country: str = Field(default="Česká republika")

    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None

    locality_region_id: Optional[int] = Field(default=None, index=True)
    locality_district_id: Optional[int] = Field(default=None, index=True)
    locality_municipality_id: Optional[int] = Field(default=None, index=True)
    locality_ward_id: Optional[int] = None
    locality_quarter_id: Optional[int] = None
    locality_street_id: Optional[int] = None
