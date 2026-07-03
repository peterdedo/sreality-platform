"""Maps raw sreality.cz API JSON payloads onto our normalized fields.

The list-endpoint field extraction is modeled on karlosmatos/sreality-scraper's
SrealityItem; the detail-endpoint field extraction is modeled on
JirkaZelenka/Sreality's scrape_specific_estates(), the richest per-listing
extraction found across the audited repos.
"""

import re
from datetime import datetime
from typing import Any, Optional

from app.domain.floor import parse_floor_fraction
from app.scraping.constants import DETAIL_ITEM_FIELD_MAP
from app.scraping.sreality_url import build_public_listing_url


def parse_list_item(estate: dict[str, Any]) -> dict[str, Any]:
    """Parse one item from the current /api/v1/estates/search results array.

    The parser stays tolerant of the legacy v2 shape so unit tests and any
    older fixtures keep working, but the live path now prefers the v1 fields.
    """
    seo = estate.get("seo", {}) or {}
    locality = estate.get("locality", {}) if isinstance(estate.get("locality"), dict) else {}
    price_raw = estate.get("price_czk")
    price_obj = price_raw if isinstance(price_raw, dict) else {}
    gps = estate.get("gps", {}) or {}

    category_main_cb = _code_value(estate.get("category_main_cb") or seo.get("category_main_cb"))
    category_type_cb = _code_value(estate.get("category_type_cb") or seo.get("category_type_cb"))
    category_sub_cb = _code_value(estate.get("category_sub_cb") or seo.get("category_sub_cb"))
    title = estate.get("advert_name") or estate.get("name")
    locality_text = _format_locality_text(
        estate.get("locality") if isinstance(estate.get("locality"), str) else locality
    )
    gps_lat = gps.get("lat") or locality.get("gps_lat") or estate.get("locality_gps_lat")
    gps_lon = gps.get("lon") or locality.get("gps_lon") or estate.get("locality_gps_lon")

    return {
        "hash_id": str(estate.get("hash_id")),
        "title": title,
        "category_main_cb": _safe_int(category_main_cb) or 0,
        "category_type_cb": _safe_int(category_type_cb) or 0,
        "category_sub_cb": _safe_int(category_sub_cb),
        "price_czk": _safe_int(price_obj.get("value_raw") or estate.get("price_czk") or estate.get("price")),
        "price_czk_unit": price_obj.get("unit"),
        "gps_lat": _safe_float(gps_lat),
        "gps_lon": _safe_float(gps_lon),
        "locality": locality_text,
        "source_url": build_public_listing_url(estate),
    }


def parse_detail(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse the /api/v1/estates/{hash_id} detail endpoint response.

    The current live API wraps the object in a top-level ``result`` key and
    exposes most fields directly. The legacy v2 shape is still supported so
    fixtures and older integration tests can continue to run.
    """
    raw = payload.get("result", payload) or {}
    rec = raw.get("recommendations_data", {}) or {}
    seller = ((raw.get("_embedded") or {}).get("seller") or {})
    premise = raw.get("premise") or ((seller.get("_embedded") or {}).get("premise") or {})
    locality = raw.get("locality") if isinstance(raw.get("locality"), dict) else {}
    floor_number = _safe_int(raw.get("floor_number"))
    total_floors = _safe_int(raw.get("floors") or raw.get("total_floors"))
    floor = raw.get("floor")
    if not floor and floor_number is not None and total_floors is not None:
        floor = f"{floor_number}/{total_floors}"

    detail: dict[str, Any] = {
        "description": raw.get("advert_description")
        or raw.get("description")
        or (raw.get("text", {}).get("value") if isinstance(raw.get("text"), dict) else None),
        "meta_description": raw.get("meta_description"),
        # furnished_cb is a 3-value codebook (1=Ano,2=Ne,3=Castecne -- see
        # app/domain/codebooks.py FURNISHED), stored as a raw code string like
        # ownership/building_type, NOT a bool: bool(rec.get("furnished")) would
        # mis-cast "2" (Ne) to True.
        "furnished": _code_value(raw.get("furnished") or rec.get("furnished")),
        "elevator": _code_value(raw.get("elevator") or rec.get("elevator")),
        "garden": _safe_bool(raw.get("garden") if raw.get("garden") is not None else rec.get("garden")),
        "object_kind": _code_value(raw.get("object_kind") or rec.get("object_kind")),
        "building_type": _code_value(raw.get("building_type") or rec.get("building_type")),
        "building_condition": _code_value(raw.get("building_condition") or rec.get("building_condition")),
        "ownership": _code_value(raw.get("ownership") or rec.get("ownership")),
        "parking_lots": _safe_int(raw.get("parking_lots") or rec.get("parking_lots")),
        "terrace": _safe_bool(raw.get("terrace") if raw.get("terrace") is not None else rec.get("terrace")),
        "balcony": _safe_bool(raw.get("balcony") if raw.get("balcony") is not None else rec.get("balcony")),
        "loggia": _safe_bool(raw.get("loggia") if raw.get("loggia") is not None else rec.get("loggia")),
        "basin": _safe_bool(raw.get("basin") if raw.get("basin") is not None else rec.get("basin")),
        "cellar": _safe_bool(raw.get("cellar") if raw.get("cellar") is not None else rec.get("cellar")),
        "garage": _safe_bool(raw.get("garage") if raw.get("garage") is not None else rec.get("garage")),
        "low_energy": _safe_bool(raw.get("low_energy") if raw.get("low_energy") is not None else rec.get("low_energy")),
        "easy_access": _safe_bool(raw.get("easy_access") if raw.get("easy_access") is not None else rec.get("easy_access")),
        "energy_efficiency_rating": _code_value(
            raw.get("energy_efficiency_rating_cb") or rec.get("energy_efficiency_rating_cb")
        ),
        "broker_id": _safe_str((seller or {}).get("user_id") or (premise or {}).get("ask_id")),
        "broker_company": (premise or {}).get("name"),
        "location": {
            **_extract_admin_names(locality, rec),
            "locality_street_id": _safe_int(raw.get("street_id") or rec.get("locality_street_id")),
            "locality_district_id": _safe_int(locality.get("district_id") or rec.get("locality_district_id")),
            "locality_ward_id": _safe_int(locality.get("ward_id") or rec.get("locality_ward_id")),
            "locality_region_id": _safe_int(locality.get("region_id") or rec.get("locality_region_id")),
            "locality_quarter_id": _safe_int(locality.get("quarter_id") or rec.get("locality_quarter_id")),
            "locality_municipality_id": _safe_int(locality.get("municipality_id") or rec.get("locality_municipality_id")),
            "gps_lat": _safe_float(locality.get("gps_lat") or rec.get("locality_gps_lat")),
            "gps_lon": _safe_float(locality.get("gps_lon") or rec.get("locality_gps_lon")),
        },
    }

    for item in raw.get("items", []) or []:
        name = item.get("name")
        field = DETAIL_ITEM_FIELD_MAP.get(name)
        if field:
            detail[field] = item.get("value")

    # The current API exposes several fields directly; keep the legacy item-
    # table override above, but fall back to direct values when the item table
    # is absent or incomplete.
    detail["usable_area"] = detail.get("usable_area") or _extract_leading_int(raw.get("usable_area"))
    detail["floor_area"] = detail.get("floor_area") or _extract_leading_int(raw.get("floor_area"))
    detail["land_area"] = detail.get("land_area") or _extract_leading_int(raw.get("land_area"))
    detail["floor"] = detail.get("floor") or floor
    detail["floor_number"] = detail.get("floor_number") or floor_number
    detail["total_floors"] = detail.get("total_floors") or total_floors
    if "built_up_area" not in detail:
        detail["built_up_area"] = _extract_leading_int(raw.get("building_area"))

    for area_field in ("usable_area", "floor_area", "land_area"):
        if area_field in detail:
            detail[area_field] = _extract_leading_int(detail[area_field])

    if detail.get("floor"):
        detail["floor_number"], detail["total_floors"] = parse_floor_fraction(detail["floor"])

    if "last_update" in detail:
        detail["last_updated_at"] = _parse_czech_date(detail.pop("last_update"))
    elif raw.get("edited"):
        try:
            detail["last_updated_at"] = datetime.strptime(str(raw.get("edited")).strip(), "%Y-%m-%d")
        except ValueError:
            detail["last_updated_at"] = None

    images: list[str] = []
    for img in raw.get("advert_images", []) or []:
        if isinstance(img, dict):
            url = img.get("url") or img.get("href")
        else:
            url = img
        if url:
            images.append(url)
    if not images:
        embedded_images = (
            raw.get("_embedded", {})
            .get("images", {})
            .get("_embedded", {})
            .get("images", [])
            or []
        )
        images = [img.get("href") for img in embedded_images if img.get("href")]
    detail["images"] = images

    return detail


def _extract_leading_int(value: Any) -> Optional[int]:
    """Extract the leading numeric token from strings like "65 m²" or "65,5 m²".
    Only digits from the leading run are used -- earlier code concatenated every
    digit found anywhere in the string, so "65 m2" (a unit suffix containing a
    digit) was misparsed as 652 instead of 65."""
    if value is None:
        return None
    match = re.match(r"\s*(\d+)", str(value))
    return int(match.group(1)) if match else None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _safe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(int(value)) if isinstance(value, (int, str)) and str(value).isdigit() else bool(value)


def _parse_czech_date(value: Any) -> Optional[datetime]:
    """Parses sreality's "Aktualizace" item, a date string in Czech DD.MM.YYYY
    format (e.g. "31.12.2025"). Returns None rather than guessing on any
    unrecognized format, consistent with this project's "don't fabricate
    data" convention."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%d.%m.%Y")
    except ValueError:
        return None


def _safe_str(value: Any) -> Optional[str]:
    return str(value) if value is not None else None


def _code_value(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        value = value.get("value")
    return _safe_str(value)


def _extract_admin_names(locality: Any, rec: dict[str, Any] | None = None) -> dict[str, Optional[str]]:
    """Map sreality locality string fields onto Location.region/district/municipality/quarter."""
    loc = locality if isinstance(locality, dict) else {}
    rec = rec or {}

    def _name(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get("name")
        text = str(value).strip()
        return text or None

    def _pick(*candidates: Any) -> Optional[str]:
        for value in candidates:
            name = _name(value)
            if name:
                return name
        return None

    municipality = _pick(loc.get("municipality"), loc.get("city"), rec.get("municipality"), rec.get("city"))
    quarter = _pick(loc.get("quarter"), loc.get("citypart"), loc.get("ward"), rec.get("quarter"), rec.get("citypart"))

    return {
        "region": _pick(loc.get("region"), rec.get("region")),
        "district": _pick(loc.get("district"), rec.get("district")),
        "municipality": municipality,
        "quarter": quarter,
    }


def _format_locality_text(locality: Any) -> Optional[str]:
    if locality is None:
        return None
    if isinstance(locality, str):
        return locality
    district = locality.get("district")
    city = locality.get("city")
    citypart = locality.get("citypart") or locality.get("quarter") or locality.get("ward")
    street = locality.get("street")

    primary = district or city or citypart or street
    if not primary:
        return None
    secondary = citypart if primary != citypart else street
    if secondary and secondary != primary:
        return f"{primary} - {secondary}"
    return primary
