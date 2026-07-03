"""Backfill Location.region/district/municipality from stored raw API payloads.

Re-parses persisted detail (and list fallback) payloads so existing rows get
admin names without a full re-scrape.
"""

from sqlmodel import Session, select

from app.models import Listing, Location, RawPayload
from app.scraping.parser import _extract_admin_names, parse_detail


def backfill_location_names(session: Session) -> dict[str, int]:
    """Fill NULL Location admin names for listings that already have a Location row."""
    updated = 0
    skipped = 0

    rows = session.exec(
        select(Listing, Location)
        .join(Location, Listing.location_id == Location.id)
        .where(Location.region == None)  # noqa: E711
    ).all()

    for listing, location in rows:
        names = _names_from_detail_payload(session, listing.id)
        if not names.get("region"):
            names = _merge_names(names, _names_from_list_payload(session, listing.hash_id))

        if any(names.get(field) for field in ("region", "district", "municipality", "quarter")):
            for field, value in names.items():
                if value:
                    setattr(location, field, value)
            session.add(location)
            updated += 1
        else:
            skipped += 1

    session.commit()
    return {"updated": updated, "skipped": skipped}


def _names_from_detail_payload(session: Session, listing_id: int) -> dict[str, str | None]:
    payload = session.exec(
        select(RawPayload)
        .where(RawPayload.listing_id == listing_id, RawPayload.payload_type == "detail")
        .order_by(RawPayload.fetched_at.desc())
    ).first()
    if payload is None:
        return {}
    location = parse_detail(payload.payload).get("location", {})
    return {k: location.get(k) for k in ("region", "district", "municipality", "quarter")}


def _names_from_list_payload(session: Session, hash_id: str) -> dict[str, str | None]:
    payload = session.exec(
        select(RawPayload)
        .where(RawPayload.hash_id == hash_id, RawPayload.payload_type == "list")
        .order_by(RawPayload.fetched_at.desc())
    ).first()
    if payload is None:
        return {}
    locality = payload.payload.get("locality")
    return _extract_admin_names(locality)


def _merge_names(primary: dict[str, str | None], fallback: dict[str, str | None]) -> dict[str, str | None]:
    merged = dict(primary)
    for key, value in fallback.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged
