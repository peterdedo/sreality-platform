from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import get_session
from app.domain import codebooks
from app.models import Image, Listing, ListingDetail, Location, PriceHistory
from app.schemas.listing import ListingDetailRead, ListingRead, ListingsPage
from app.schemas.map import MapMarker, MapMarkersPage
from app.scraping.sreality_url import resolve_public_source_url

router = APIRouter(prefix="/listings", tags=["listings"])

# sort_by -> SQL ORDER BY expression. price_change_count/image_count/has_price_drop
# are exposed as response columns but are NOT sortable in v1 -- they'd need a
# further aggregate join; documented here rather than silently unsupported.
_SORTABLE_COLUMNS = {
    "price_czk": Listing.price_czk,
    "usable_area": ListingDetail.usable_area,
    "price_per_m2": Listing.price_czk / func.nullif(ListingDetail.usable_area, 0),
    "first_seen_at": Listing.first_seen_at,
    "last_seen_at": Listing.last_seen_at,
    "days_on_market": func.extract("epoch", func.coalesce(Listing.removed_at, func.now()) - Listing.first_seen_at),
}


def _days_on_market(listing: Listing) -> Optional[int]:
    if listing.first_seen_at is None:
        return None
    end = listing.removed_at or datetime.utcnow()
    return max(0, (end - listing.first_seen_at).days)


def _price_per_m2(price_czk: Optional[int], usable_area: Optional[int]) -> Optional[float]:
    if price_czk and usable_area:
        return round(price_czk / usable_area, 0)
    return None


def _build_listing_read(
    listing: Listing,
    detail: Optional[ListingDetail],
    location: Optional[Location],
    *,
    price_change_count: int = 0,
    has_price_drop: bool = False,
    image_count: int = 0,
) -> ListingRead:
    return ListingRead(
        id=listing.id,
        hash_id=listing.hash_id,
        title=listing.title,
        category_main_cb=listing.category_main_cb,
        category_type_cb=listing.category_type_cb,
        category_sub_cb=listing.category_sub_cb,
        price_czk=listing.price_czk,
        price_per_m2=_price_per_m2(listing.price_czk, detail.usable_area if detail else None),
        gps_lat=listing.gps_lat,
        gps_lon=listing.gps_lon,
        is_active=listing.is_active,
        first_seen_at=listing.first_seen_at,
        last_seen_at=listing.last_seen_at,
        last_updated_at=detail.last_updated_at if detail else None,
        removed_at=listing.removed_at,
        source_url=resolve_public_source_url(
            source_url=listing.source_url,
            hash_id=listing.hash_id,
            category_main_cb=listing.category_main_cb,
            category_type_cb=listing.category_type_cb,
            category_sub_cb=listing.category_sub_cb,
            title=listing.title,
        ),
        locality_text=listing.locality_text,
        seller_type=listing.seller_type,
        usable_area=detail.usable_area if detail else None,
        floor_area=detail.floor_area if detail else None,
        land_area=detail.land_area if detail else None,
        floor=detail.floor if detail else None,
        floor_number=detail.floor_number if detail else None,
        total_floors=detail.total_floors if detail else None,
        ownership=codebooks.ownership_label(detail.ownership) if detail else None,
        building_type=codebooks.building_type_label(detail.building_type) if detail else None,
        building_condition=codebooks.building_condition_label(detail.building_condition) if detail else None,
        energy_efficiency_rating=codebooks.energy_efficiency_rating_label(detail.energy_efficiency_rating) if detail else None,
        furnished=codebooks.furnished_label(detail.furnished) if detail else None,
        elevator=codebooks.elevator_label(detail.elevator) if detail else None,
        balcony=detail.balcony if detail else None,
        terrace=detail.terrace if detail else None,
        cellar=detail.cellar if detail else None,
        garage=detail.garage if detail else None,
        garden=detail.garden if detail else None,
        parking_lots=detail.parking_lots if detail else None,
        region=listing.resolved_region_name or (location.region if location else None),
        district=location.district if location else None,
        city=location.municipality if location else None,
        days_on_market=_days_on_market(listing),
        price_change_count=price_change_count,
        has_price_drop=has_price_drop,
        image_count=image_count,
        description_length=len(detail.description) if detail and detail.description else None,
    )


def build_listings_filter_query(
    *,
    category_main_cb: Optional[int] = None,
    category_type_cb: Optional[int] = None,
    category_sub_cb: Optional[int] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    price_per_m2_min: Optional[float] = None,
    price_per_m2_max: Optional[float] = None,
    usable_area_min: Optional[int] = None,
    usable_area_max: Optional[int] = None,
    floor_area_min: Optional[int] = None,
    floor_area_max: Optional[int] = None,
    land_area_min: Optional[int] = None,
    land_area_max: Optional[int] = None,
    floor_number_min: Optional[int] = None,
    floor_number_max: Optional[int] = None,
    ownership: Optional[str] = None,
    building_type: Optional[str] = None,
    building_condition: Optional[str] = None,
    energy_efficiency_rating: Optional[str] = None,
    furnished: Optional[str] = None,
    elevator: Optional[str] = None,
    balcony: Optional[bool] = None,
    terrace: Optional[bool] = None,
    cellar: Optional[bool] = None,
    garage: Optional[bool] = None,
    garden: Optional[bool] = None,
    has_parking: Optional[bool] = None,
    region: Optional[str] = None,
    district: Optional[str] = None,
    city: Optional[str] = None,
    seller_type: Optional[str] = None,
    days_on_market_min: Optional[int] = None,
    days_on_market_max: Optional[int] = None,
    has_price_drop: Optional[bool] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = True,
):
    """Builds the filtered/joined `select(Listing, ListingDetail, Location)`
    statement shared by GET /listings and the export endpoints (app/api/export.py),
    so filter semantics never drift between the two."""

    base = select(Listing, ListingDetail, Location).join(ListingDetail, ListingDetail.listing_id == Listing.id, isouter=True).join(
        Location, Location.id == Listing.location_id, isouter=True
    )
    if is_active is not None:
        base = base.where(Listing.is_active == is_active)

    if category_main_cb is not None:
        base = base.where(Listing.category_main_cb == category_main_cb)
    if category_type_cb is not None:
        base = base.where(Listing.category_type_cb == category_type_cb)
    if category_sub_cb is not None:
        base = base.where(Listing.category_sub_cb == category_sub_cb)
    if price_min is not None:
        base = base.where(Listing.price_czk >= price_min)
    if price_max is not None:
        base = base.where(Listing.price_czk <= price_max)

    price_per_m2_expr = Listing.price_czk / func.nullif(ListingDetail.usable_area, 0)
    if price_per_m2_min is not None:
        base = base.where(price_per_m2_expr >= price_per_m2_min)
    if price_per_m2_max is not None:
        base = base.where(price_per_m2_expr <= price_per_m2_max)

    if usable_area_min is not None:
        base = base.where(ListingDetail.usable_area >= usable_area_min)
    if usable_area_max is not None:
        base = base.where(ListingDetail.usable_area <= usable_area_max)
    if floor_area_min is not None:
        base = base.where(ListingDetail.floor_area >= floor_area_min)
    if floor_area_max is not None:
        base = base.where(ListingDetail.floor_area <= floor_area_max)
    if land_area_min is not None:
        base = base.where(ListingDetail.land_area >= land_area_min)
    if land_area_max is not None:
        base = base.where(ListingDetail.land_area <= land_area_max)
    if floor_number_min is not None:
        base = base.where(ListingDetail.floor_number >= floor_number_min)
    if floor_number_max is not None:
        base = base.where(ListingDetail.floor_number <= floor_number_max)

    if ownership is not None:
        base = base.where(ListingDetail.ownership == ownership)
    if building_type is not None:
        base = base.where(ListingDetail.building_type == building_type)
    if building_condition is not None:
        base = base.where(ListingDetail.building_condition == building_condition)
    if energy_efficiency_rating is not None:
        base = base.where(ListingDetail.energy_efficiency_rating == energy_efficiency_rating)
    if furnished is not None:
        base = base.where(ListingDetail.furnished == furnished)
    if elevator is not None:
        base = base.where(ListingDetail.elevator == elevator)
    if balcony is not None:
        base = base.where(ListingDetail.balcony == balcony)
    if terrace is not None:
        base = base.where(ListingDetail.terrace == terrace)
    if cellar is not None:
        base = base.where(ListingDetail.cellar == cellar)
    if garage is not None:
        base = base.where(ListingDetail.garage == garage)
    if garden is not None:
        base = base.where(ListingDetail.garden == garden)
    if has_parking is not None:
        base = base.where(ListingDetail.parking_lots > 0 if has_parking else or_(ListingDetail.parking_lots.is_(None), ListingDetail.parking_lots == 0))

    if region is not None:
        base = base.where(
            func.coalesce(Listing.resolved_region_name, Location.region).ilike(f"%{region}%")
        )
    if district is not None:
        base = base.where(Location.district.ilike(f"%{district}%"))
    if city is not None:
        base = base.where(Location.municipality.ilike(f"%{city}%"))
    if seller_type is not None:
        base = base.where(Listing.seller_type == seller_type)

    days_on_market_expr = func.extract("epoch", func.coalesce(Listing.removed_at, func.now()) - Listing.first_seen_at) / 86400
    if days_on_market_min is not None:
        base = base.where(days_on_market_expr >= days_on_market_min)
    if days_on_market_max is not None:
        base = base.where(days_on_market_expr <= days_on_market_max)

    if has_price_drop is not None:
        ranked = (
            select(
                PriceHistory.listing_id,
                PriceHistory.price_czk,
                func.row_number()
                .over(partition_by=PriceHistory.listing_id, order_by=PriceHistory.recorded_at.asc())
                .label("rn"),
                func.count(PriceHistory.id)
                .over(partition_by=PriceHistory.listing_id)
                .label("history_count"),
            )
        ).subquery()
        drop_ids = (
            select(ranked.c.listing_id)
            .join(Listing, Listing.id == ranked.c.listing_id)
            .where(
                ranked.c.rn == 1,
                ranked.c.history_count >= 2,
                Listing.price_czk.is_not(None),
                Listing.price_czk < ranked.c.price_czk,
            )
        )
        if has_price_drop:
            base = base.where(Listing.id.in_(drop_ids))
        else:
            base = base.where(Listing.id.not_in(drop_ids))

    if search:
        pattern = f"%{search}%"
        base = base.where(or_(Listing.title.ilike(pattern), Listing.locality_text.ilike(pattern)))

    return base


def _price_history_stats(session: Session, listing_ids: list[int]) -> dict[int, tuple[int, bool]]:
    """Return listing_id -> (price_change_count, has_price_drop) without loading full history."""
    if not listing_ids:
        return {}

    counts = dict(
        session.exec(
            select(PriceHistory.listing_id, func.count(PriceHistory.id))
            .where(PriceHistory.listing_id.in_(listing_ids))
            .group_by(PriceHistory.listing_id)
        ).all()
    )

    ranked = (
        select(
            PriceHistory.listing_id,
            PriceHistory.price_czk,
            func.row_number()
            .over(partition_by=PriceHistory.listing_id, order_by=PriceHistory.recorded_at.asc())
            .label("rn"),
        )
        .where(PriceHistory.listing_id.in_(listing_ids))
    ).subquery()
    first_prices = {
        row[0]: row[1]
        for row in session.exec(
            select(ranked.c.listing_id, ranked.c.price_czk).where(ranked.c.rn == 1)
        ).all()
    }
    current_prices = {
        row[0]: row[1]
        for row in session.exec(select(Listing.id, Listing.price_czk).where(Listing.id.in_(listing_ids))).all()
    }

    stats: dict[int, tuple[int, bool]] = {}
    for listing_id in listing_ids:
        count = int(counts.get(listing_id, 0))
        first_price = first_prices.get(listing_id)
        current_price = current_prices.get(listing_id)
        has_drop = (
            count >= 2
            and first_price is not None
            and current_price is not None
            and current_price < first_price
        )
        stats[listing_id] = (max(0, count - 1), has_drop)
    return stats


@router.get("/map-markers", response_model=MapMarkersPage, summary="Lehké body pro mapu")
def map_markers(
    session: Session = Depends(get_session),
    is_active: bool = True,
    south: Optional[float] = Query(None, description="Jižní hranice viewportu"),
    west: Optional[float] = Query(None, description="Západní hranice viewportu"),
    north: Optional[float] = Query(None, description="Severní hranice viewportu"),
    east: Optional[float] = Query(None, description="Východní hranice viewportu"),
    limit: int = Query(settings.max_map_markers, ge=1, le=settings.max_map_markers),
):
    """Minimal payload for map clustering — no detail/location joins."""
    stmt = select(Listing).where(
        Listing.is_active == is_active,  # noqa: E712
        Listing.gps_lat.is_not(None),
        Listing.gps_lon.is_not(None),
    )
    if south is not None:
        stmt = stmt.where(Listing.gps_lat >= south)
    if north is not None:
        stmt = stmt.where(Listing.gps_lat <= north)
    if west is not None:
        stmt = stmt.where(Listing.gps_lon >= west)
    if east is not None:
        stmt = stmt.where(Listing.gps_lon <= east)

    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(stmt.limit(limit)).all()
    items = [
        MapMarker(
            id=listing.id,
            gps_lat=listing.gps_lat,
            gps_lon=listing.gps_lon,
            price_czk=listing.price_czk,
            title=listing.title,
            category_main_cb=listing.category_main_cb,
            category_type_cb=listing.category_type_cb,
            source_url=resolve_public_source_url(
                source_url=listing.source_url,
                hash_id=listing.hash_id,
                category_main_cb=listing.category_main_cb,
                category_type_cb=listing.category_type_cb,
                category_sub_cb=listing.category_sub_cb,
                title=listing.title,
            ),
        )
        for listing in rows
        if listing.gps_lat is not None and listing.gps_lon is not None
    ]
    return MapMarkersPage(items=items, total=total, truncated=total > len(rows))


@router.get("", response_model=ListingsPage, summary="List nabídek s filtry")
def list_listings(
    session: Session = Depends(get_session),
    category_main_cb: Optional[int] = Query(None, description="Typ nemovitosti"),
    category_type_cb: Optional[int] = Query(None, description="Typ nabídky (prodej/pronájem)"),
    category_sub_cb: Optional[int] = Query(None, description="Dispozice"),
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    price_per_m2_min: Optional[float] = None,
    price_per_m2_max: Optional[float] = None,
    usable_area_min: Optional[int] = None,
    usable_area_max: Optional[int] = None,
    floor_area_min: Optional[int] = None,
    floor_area_max: Optional[int] = None,
    land_area_min: Optional[int] = None,
    land_area_max: Optional[int] = None,
    floor_number_min: Optional[int] = None,
    floor_number_max: Optional[int] = None,
    ownership: Optional[str] = Query(None, description="Raw ownership_cb code"),
    building_type: Optional[str] = Query(None, description="Raw building_type_cb code"),
    building_condition: Optional[str] = Query(None, description="Raw building_condition_cb code"),
    energy_efficiency_rating: Optional[str] = Query(None, description="Raw energy_efficiency_rating_cb code"),
    furnished: Optional[str] = Query(None, description="Raw furnished_cb code"),
    elevator: Optional[str] = Query(None, description="Raw elevator_cb code"),
    balcony: Optional[bool] = None,
    terrace: Optional[bool] = None,
    cellar: Optional[bool] = None,
    garage: Optional[bool] = None,
    garden: Optional[bool] = None,
    has_parking: Optional[bool] = None,
    region: Optional[str] = None,
    district: Optional[str] = None,
    city: Optional[str] = None,
    seller_type: Optional[str] = None,
    days_on_market_min: Optional[int] = None,
    days_on_market_max: Optional[int] = None,
    has_price_drop: Optional[bool] = None,
    search: Optional[str] = Query(None, description="Fulltext search over title and locality_text"),
    is_active: bool = True,
    sort_by: Optional[str] = Query(None, description=f"Jedna z: {', '.join(_SORTABLE_COLUMNS)}"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=settings.max_listings_page_size),
):
    if sort_by is not None and sort_by not in _SORTABLE_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Neplatné řazení '{sort_by}'. Povolené hodnoty: {', '.join(_SORTABLE_COLUMNS)}")

    base = build_listings_filter_query(
        category_main_cb=category_main_cb,
        category_type_cb=category_type_cb,
        category_sub_cb=category_sub_cb,
        price_min=price_min,
        price_max=price_max,
        price_per_m2_min=price_per_m2_min,
        price_per_m2_max=price_per_m2_max,
        usable_area_min=usable_area_min,
        usable_area_max=usable_area_max,
        floor_area_min=floor_area_min,
        floor_area_max=floor_area_max,
        land_area_min=land_area_min,
        land_area_max=land_area_max,
        floor_number_min=floor_number_min,
        floor_number_max=floor_number_max,
        ownership=ownership,
        building_type=building_type,
        building_condition=building_condition,
        energy_efficiency_rating=energy_efficiency_rating,
        furnished=furnished,
        elevator=elevator,
        balcony=balcony,
        terrace=terrace,
        cellar=cellar,
        garage=garage,
        garden=garden,
        has_parking=has_parking,
        region=region,
        district=district,
        city=city,
        seller_type=seller_type,
        days_on_market_min=days_on_market_min,
        days_on_market_max=days_on_market_max,
        has_price_drop=has_price_drop,
        search=search,
        is_active=is_active,
    )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = session.exec(count_stmt).one()

    order_expr = _SORTABLE_COLUMNS[sort_by] if sort_by else Listing.last_seen_at
    order_expr = order_expr.asc() if sort_dir == "asc" else order_expr.desc()
    stmt = base.order_by(order_expr).offset((page - 1) * page_size).limit(page_size)
    rows = session.exec(stmt).all()

    listing_ids = [row[0].id for row in rows]

    image_counts: dict[int, int] = {}
    price_stats: dict[int, tuple[int, bool]] = {}
    if listing_ids:
        image_rows = session.exec(
            select(Image.listing_id, func.count(Image.id)).where(Image.listing_id.in_(listing_ids)).group_by(Image.listing_id)
        ).all()
        image_counts = dict(image_rows)
        price_stats = _price_history_stats(session, listing_ids)

    items = [
        _build_listing_read(
            listing,
            detail,
            location,
            price_change_count=price_stats.get(listing.id, (0, False))[0],
            has_price_drop=price_stats.get(listing.id, (0, False))[1],
            image_count=image_counts.get(listing.id, 0),
        )
        for listing, detail, location in rows
    ]

    return ListingsPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{listing_id}", response_model=ListingDetailRead, summary="Detail nabídky")
def get_listing_detail(listing_id: int, session: Session = Depends(get_session)):
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Nabídka nebyla nalezena")

    detail = session.exec(select(ListingDetail).where(ListingDetail.listing_id == listing_id)).first()
    location = session.get(Location, listing.location_id) if listing.location_id else None
    images = session.exec(select(Image).where(Image.listing_id == listing_id).order_by(Image.position)).all()
    history = session.exec(
        select(PriceHistory).where(PriceHistory.listing_id == listing_id).order_by(PriceHistory.recorded_at)
    ).all()
    price_stats = _price_history_stats(session, [listing_id])
    change_count, has_drop = price_stats.get(listing_id, (0, False))

    listing_read = _build_listing_read(
        listing,
        detail,
        location,
        price_change_count=change_count,
        has_price_drop=has_drop,
        image_count=len(images),
    )

    return ListingDetailRead(
        listing=listing_read,
        description=detail.description if detail else None,
        usable_area=detail.usable_area if detail else None,
        floor_area=detail.floor_area if detail else None,
        floor=detail.floor if detail else None,
        ownership=codebooks.ownership_label(detail.ownership) if detail else None,
        building_type=codebooks.building_type_label(detail.building_type) if detail else None,
        building_condition=codebooks.building_condition_label(detail.building_condition) if detail else None,
        energy_efficiency_rating=codebooks.energy_efficiency_rating_label(detail.energy_efficiency_rating) if detail else None,
        furnished=codebooks.furnished_label(detail.furnished) if detail else None,
        elevator=codebooks.elevator_label(detail.elevator) if detail else None,
        balcony=detail.balcony if detail else None,
        terrace=detail.terrace if detail else None,
        loggia=detail.loggia if detail else None,
        cellar=detail.cellar if detail else None,
        garage=detail.garage if detail else None,
        garden=detail.garden if detail else None,
        parking_lots=detail.parking_lots if detail else None,
        broker_company=detail.broker_company if detail else None,
        note_about_price=detail.note_about_price if detail else None,
        images=[img.url for img in images],
        price_history=[{"price_czk": h.price_czk, "recorded_at": h.recorded_at} for h in history],
    )
