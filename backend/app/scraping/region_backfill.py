"""Batch-compute resolved_region_* for active listings."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import func
from sqlmodel import Session, select

from app.domain.region_hints import hints_from_raw_payloads, latest_payloads_by_listing
from app.domain.region_resolver import RegionSource, apply_resolved_region
from app.models import Listing, ListingDetail, Location, RawPayload


def _listing_ids_needing_resolution(session: Session, *, active_only: bool) -> list[int]:
    stmt = select(Listing.id)
    if active_only:
        stmt = stmt.where(Listing.is_active == True)  # noqa: E712
    return list(session.exec(stmt).all())


def _prefetch_backfill_context(session: Session, listing_ids: list[int]) -> dict:
    if not listing_ids:
        return {
            "locations": {},
            "has_detail": set(),
            "list_payloads": {},
            "detail_payloads": {},
        }

    listings = session.exec(select(Listing).where(Listing.id.in_(listing_ids))).all()
    hash_ids = [listing.hash_id for listing in listings]
    location_ids = [listing.location_id for listing in listings if listing.location_id is not None]

    locations: dict[int, Location] = {}
    if location_ids:
        for location in session.exec(select(Location).where(Location.id.in_(location_ids))).all():
            locations[location.id] = location

    has_detail = set(
        session.exec(select(ListingDetail.listing_id).where(ListingDetail.listing_id.in_(listing_ids))).all()
    )

    list_rows = session.exec(
        select(RawPayload).where(RawPayload.payload_type == "list", RawPayload.hash_id.in_(hash_ids))
    ).all()
    detail_rows = session.exec(
        select(RawPayload).where(RawPayload.payload_type == "detail", RawPayload.listing_id.in_(listing_ids))
    ).all()
    list_payloads, detail_payloads = latest_payloads_by_listing(list_rows, detail_rows)

    return {
        "listings": {listing.id: listing for listing in listings},
        "locations": locations,
        "has_detail": has_detail,
        "list_payloads": list_payloads,
        "detail_payloads": detail_payloads,
    }


def resolve_listing_region(session: Session, listing: Listing, *, context: dict | None = None) -> str:
    ctx = context or _prefetch_backfill_context(session, [listing.id])
    location = ctx["locations"].get(listing.location_id) if listing.location_id else None
    hints = hints_from_raw_payloads(
        ctx["list_payloads"].get(listing.hash_id),
        ctx["detail_payloads"].get(listing.id),
        location=location,
        has_detail_row=listing.id in ctx["has_detail"],
    )
    apply_resolved_region(listing, location=location, hints=hints)
    session.add(listing)
    return listing.region_source or RegionSource.unknown.value


def region_resolution_stats(session: Session, *, active_only: bool = True) -> dict:
    active_filter = Listing.is_active == True if active_only else None  # noqa: E712

    by_source_stmt = select(Listing.region_source, func.count(Listing.id)).group_by(Listing.region_source)
    if active_filter is not None:
        by_source_stmt = by_source_stmt.where(active_filter)
    by_source = {row[0] or "unset": row[1] for row in session.exec(by_source_stmt).all()}

    by_reason_stmt = (
        select(Listing.region_unknown_reason, func.count(Listing.id))
        .where(Listing.region_source == RegionSource.unknown.value)
        .group_by(Listing.region_unknown_reason)
    )
    if active_filter is not None:
        by_reason_stmt = by_reason_stmt.where(active_filter)
    by_unknown_reason = {row[0] or "unset": row[1] for row in session.exec(by_reason_stmt).all()}

    with_region_stmt = select(func.count(Listing.id)).where(Listing.resolved_region_name.is_not(None))
    unknown_stmt = select(func.count(Listing.id)).where(Listing.region_source == RegionSource.unknown.value)
    unset_stmt = select(func.count(Listing.id)).where(Listing.region_source.is_(None))
    total_stmt = select(func.count(Listing.id))
    if active_filter is not None:
        with_region_stmt = with_region_stmt.where(active_filter)
        unknown_stmt = unknown_stmt.where(active_filter)
        unset_stmt = unset_stmt.where(active_filter)
        total_stmt = total_stmt.where(active_filter)

    return {
        "active_total": session.exec(total_stmt).one(),
        "with_region": session.exec(with_region_stmt).one(),
        "unknown_region": session.exec(unknown_stmt).one(),
        "unset_region": session.exec(unset_stmt).one(),
        "by_region_source": by_source,
        "by_unknown_reason": by_unknown_reason,
    }


def backfill_resolved_regions(
    session: Session,
    *,
    batch_size: int = 1000,
    active_only: bool = True,
) -> dict:
    """Recompute resolved region for listings. Commits per batch (resumable)."""
    before = region_resolution_stats(session, active_only=active_only)

    listing_ids = _listing_ids_needing_resolution(session, active_only=active_only)
    updated = 0
    source_counter: Counter[str] = Counter()

    for offset in range(0, len(listing_ids), batch_size):
        batch_ids = listing_ids[offset : offset + batch_size]
        context = _prefetch_backfill_context(session, batch_ids)
        for listing_id in batch_ids:
            listing = context["listings"].get(listing_id)
            if listing is None:
                continue
            source = resolve_listing_region(session, listing, context=context)
            source_counter[source] += 1
            updated += 1
        session.commit()

    after = region_resolution_stats(session, active_only=active_only)
    return {
        "updated": updated,
        "sources_assigned": dict(source_counter),
        "before": before,
        "after": after,
    }
