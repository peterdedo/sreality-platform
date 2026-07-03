"""Build public https://www.sreality.cz/detail/... URLs for listings.

The v1 read API does not expose a ready-made browser URL (only the JSON
endpoints). Legacy v2 list payloads may include ``seo.locality``.

Verified behaviour (2026): Sreality resolves any well-formed detail path
when the trailing ``hash_id`` is valid; the locality and subtype segments
may be approximate and the server redirects to the canonical slug.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Optional
from urllib.parse import quote

from app.scraping.constants import ROOM_LAYOUTS

_CATEGORY_SUB_SLUGS: dict[int, str] = {
    36: "jine-nemovitosti",
}

# URL path segments (ASCII, no diacritics) — distinct from Czech display labels.
_DEAL_SLUGS: dict[int, str] = {
    1: "prodej",
    2: "pronajem",
    3: "drazby",
    4: "prodej",
}

_PROPERTY_SLUGS: dict[int, str] = {
    1: "byt",
    2: "dum",
    3: "pozemek",
    4: "komercni",
    5: "ostatni",
}

_FALLBACK_LOCALITY_SLUG = "detail"
_API_URL_MARKERS = ("/api/v1/estates/", "/api/cs/v2/estates/")


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _code_value(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        return _safe_int(value.get("value"))
    return _safe_int(value)


def _subtype_slug(category_sub_cb: Any, title: str | None = None) -> str:
    code = _code_value(category_sub_cb)
    if code and code in _CATEGORY_SUB_SLUGS:
        return _CATEGORY_SUB_SLUGS[code]

    if isinstance(category_sub_cb, dict):
        name = category_sub_cb.get("name")
        if name and str(name).strip().lower() not in ("n/a", "ostatní", "ostatni"):
            return _slugify_segment(str(name))

    if code and code in ROOM_LAYOUTS:
        label = ROOM_LAYOUTS[code]
        if label and label not in ("N/A",):
            return _slugify_segment(label)
    if title:
        for token in title.replace("\u00a0", " ").split():
            if "+" in token:
                return _slugify_segment(token)
    return "ostatni"


def _slugify_segment(value: str) -> str:
    """Keep dispozice like ``3+kk``; otherwise emit an ASCII slug."""
    text = value.strip().lower().replace("\u00a0", " ")
    if "+" in text and " " not in text:
        return text
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").strip().lower()
    )
    return quote(ascii_text.replace(" ", "-"), safe="+")


def _locality_slug(estate: dict[str, Any]) -> str:
    seo = estate.get("seo") or {}
    if isinstance(seo, dict):
        legacy = seo.get("locality")
        if legacy:
            return str(legacy)

    locality = estate.get("locality")
    if isinstance(locality, dict):
        parts: list[str] = []
        for key in (
            "city_seo_name",
            "citypart_seo_name",
            "ward_seo_name",
            "street_seo_name",
            "municipality_seo_name",
            "district_seo_name",
            "quarter_seo_name",
        ):
            val = locality.get(key)
            if val:
                parts.append(str(val))
        if parts:
            return "-".join(parts)

    return _FALLBACK_LOCALITY_SLUG


def build_public_listing_url(estate: dict[str, Any]) -> Optional[str]:
    """Construct the browser detail URL from a list- or detail-shaped payload."""
    hash_id = estate.get("hash_id")
    if hash_id is None:
        return None

    category_main_cb = _code_value(estate.get("category_main_cb")) or 0
    category_type_cb = _code_value(estate.get("category_type_cb")) or 0
    deal = _DEAL_SLUGS.get(category_type_cb, "prodej")
    prop = _PROPERTY_SLUGS.get(category_main_cb, "ostatni")
    subtype = _subtype_slug(estate.get("category_sub_cb"), estate.get("advert_name") or estate.get("name"))
    locality = _locality_slug(estate)

    return f"https://www.sreality.cz/detail/{deal}/{prop}/{subtype}/{locality}/{hash_id}"


def build_public_listing_url_from_fields(
    *,
    hash_id: str,
    category_main_cb: int,
    category_type_cb: int,
    category_sub_cb: int | None = None,
    title: str | None = None,
) -> str:
    """Fallback when only persisted Listing columns are available."""
    estate = {
        "hash_id": hash_id,
        "category_main_cb": category_main_cb,
        "category_type_cb": category_type_cb,
        "category_sub_cb": category_sub_cb,
        "advert_name": title,
    }
    built = build_public_listing_url(estate)
    if built:
        return built
    return f"https://www.sreality.cz/detail/prodej/byt/2+kk/{_FALLBACK_LOCALITY_SLUG}/{hash_id}"


def is_api_source_url(source_url: str | None) -> bool:
    return bool(source_url and any(marker in source_url for marker in _API_URL_MARKERS))


def resolve_public_source_url(
    *,
    source_url: str | None,
    hash_id: str,
    category_main_cb: int,
    category_type_cb: int,
    category_sub_cb: int | None = None,
    title: str | None = None,
) -> str | None:
    """Return a browser URL, upgrading legacy API endpoint values when needed."""
    if source_url and not is_api_source_url(source_url):
        return source_url
    return build_public_listing_url_from_fields(
        hash_id=hash_id,
        category_main_cb=category_main_cb,
        category_type_cb=category_type_cb,
        category_sub_cb=category_sub_cb,
        title=title,
    )
