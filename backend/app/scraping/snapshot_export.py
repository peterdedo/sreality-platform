"""Immutable CSV snapshot + SHA-256 manifest for index-4 handoff."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlmodel import Session, select

from app.api.export import MAX_EXPORT_ROWS, _raw_listing_row
from app.domain.export import serialize_rows
from app.models import Listing, ListingDetail, Location


def build_byty_prodej_snapshot(
    session: Session,
    *,
    is_active: bool = True,
    scrape_run_id: int | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Return (csv_bytes, manifest) for active byty/prodej (category 1/1).

    Rows are sorted by hash_id for stable checksums. Raises ValueError if the
    result would hit the export row cap (refuse truncated snapshots).
    """
    stmt = (
        select(Listing)
        .where(
            Listing.category_main_cb == 1,
            Listing.category_type_cb == 1,
            Listing.is_active == is_active,  # noqa: E712
        )
        .order_by(Listing.hash_id)
    )
    listings = list(session.exec(stmt).all())
    if len(listings) > MAX_EXPORT_ROWS:
        raise ValueError(
            f"Snapshot has {len(listings)} rows which exceeds max_export_rows={MAX_EXPORT_ROWS}"
        )

    detail_ids = [listing.id for listing in listings]
    details: dict[int, ListingDetail] = {}
    if detail_ids:
        for detail in session.exec(
            select(ListingDetail).where(ListingDetail.listing_id.in_(detail_ids))
        ).all():
            details[detail.listing_id] = detail

    location_ids = [listing.location_id for listing in listings if listing.location_id]
    locations: dict[int, Location] = {}
    if location_ids:
        for location in session.exec(select(Location).where(Location.id.in_(location_ids))).all():
            locations[location.id] = location

    rows = [
        _raw_listing_row(
            listing,
            details.get(listing.id),
            locations.get(listing.location_id) if listing.location_id else None,
        )
        for listing in listings
    ]

    csv_bytes, _media, _name = serialize_rows(rows, "csv", "byty_prodej_snapshot")
    digest = hashlib.sha256(csv_bytes).hexdigest()

    last_seen_values = [listing.last_seen_at for listing in listings if listing.last_seen_at]
    first_seen_values = [listing.first_seen_at for listing in listings if listing.first_seen_at]
    period_start = min(first_seen_values).isoformat() if first_seen_values else None
    period_end = max(last_seen_values).isoformat() if last_seen_values else None

    schema_revision: str | None
    try:
        schema_revision = session.exec(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).scalar_one_or_none()
    except Exception:
        schema_revision = None

    with_unit = sum(1 for listing in listings if listing.price_czk_unit)
    manifest = {
        "artifact": "byty_prodej_active_raw_csv",
        "filters": {
            "category_main_cb": 1,
            "category_type_cb": 1,
            "is_active": is_active,
            "scope": "raw",
        },
        "period_start": period_start,
        "period_end": period_end,
        "row_count": len(rows),
        "sha256": digest,
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "source": "sreality_api_scrape",
        "schema_revision": schema_revision,
        "scrape_run_id": scrape_run_id,
        "price_czk_unit_populated": with_unit,
        "price_czk_unit_missing": len(listings) - with_unit,
    }
    return csv_bytes, manifest


def write_byty_prodej_snapshot(
    session: Session,
    output_dir: str,
    *,
    scrape_run_id: int | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Write versioned CSV + manifest.json under output_dir. Returns paths + manifest."""
    import os

    csv_bytes, manifest = build_byty_prodej_snapshot(session, scrape_run_id=scrape_run_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, f"byty_prodej_active_{stamp}.csv")
    manifest_path = os.path.join(output_dir, f"byty_prodej_active_{stamp}.manifest.json")
    with open(csv_path, "wb") as fh:
        fh.write(csv_bytes)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return csv_path, manifest_path, manifest
