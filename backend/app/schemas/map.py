from typing import Optional

from pydantic import BaseModel


class MapMarker(BaseModel):
    id: int
    gps_lat: float
    gps_lon: float
    price_czk: Optional[int] = None
    title: Optional[str] = None
    category_main_cb: int
    category_type_cb: int
    source_url: Optional[str] = None


class MapMarkersPage(BaseModel):
    items: list[MapMarker]
    total: int
    # True when `total` (matches within the requested bounds) exceeds the
    # rows actually returned -- i.e. `limit` truncated the response. The
    # frontend uses this to tell the user to zoom in rather than silently
    # showing a subset as if it were everything in view.
    truncated: bool = False
