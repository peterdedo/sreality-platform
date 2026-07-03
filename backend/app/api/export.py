"""Export endpoints: listings (raw/cleaned, honoring the same filters as
GET /listings) and derived analytics (aggregated time-series, per-listing
valuation+anomaly). See docs/METHODOLOGY.md for how the underlying metrics
are computed; this module only serializes what already exists.
"""

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import require_api_key
from app.api.listings import _build_listing_read, _price_history_stats, build_listings_filter_query
from app.api.rate_limit import heavy_endpoint_limiter
from app.core.config import settings
from app.core.db import get_session
from app.domain.export import SUPPORTED_FORMATS, serialize_rows
from app.models import (
    Image,
    Listing,
    ListingAnomaly,
    ListingDetail,
    ListingValuation,
    Location,
    PriceHistory,
)
from app.models.analytic_snapshot import AnalyticSnapshot
from app.scraping.constants import DEAL_TYPES, PROPERTY_TYPES
from app.scraping.sreality_url import resolve_public_source_url

# require_api_key + rate limit apply to every export endpoint (all are heavy:
# they materialize and serialize potentially large result sets).
router = APIRouter(
    prefix="/export",
    tags=["export"],
    dependencies=[Depends(require_api_key), Depends(heavy_endpoint_limiter)],
)

# Hard safety cap so an unfiltered export can't try to stream an unbounded
# number of rows into memory. This is a serialization guard, not an analytics
# sample — responses include X-Export-* headers when truncated.
MAX_EXPORT_ROWS = settings.max_export_rows

SOURCE_NAME = "sreality.cz"
COLLECTION_METHOD = "sreality_api_scrape"


def _format_param(format: str = Query("csv", description=f"Jeden z: {', '.join(SUPPORTED_FORMATS)}")) -> str:
    # Note: this sub-dependency's own parameter name IS the query param name
    # FastAPI binds to (Depends() doesn't inherit the name from the endpoint's
    # `format: str = Depends(_format_param)` annotation) -- it must match
    # "format" exactly, or ?format=... is silently ignored and this always
    # falls back to the "csv" default. Caught by test_export_invalid_format_returns_400.
    if format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Nepodporovaný formát '{format}'. Podporované formáty: {', '.join(SUPPORTED_FORMATS)}")
    return format


def _respond(
    rows: list[dict],
    fmt: str,
    filename_stem: str,
    *,
    total_matched: int | None = None,
    truncated: bool = False,
) -> Response:
    content, media_type, filename = serialize_rows(rows, fmt, filename_stem)
    headers: dict[str, str] = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if total_matched is not None:
        headers["X-Export-Total-Matched"] = str(total_matched)
        headers["X-Export-Returned-Rows"] = str(len(rows))
        headers["X-Export-Truncated"] = "true" if truncated else "false"
    return Response(content=content, media_type=media_type, headers=headers)


def _raw_listing_row(listing: Listing, detail: Optional[ListingDetail], location: Optional[Location]) -> dict:
    row = {
        "id": listing.id,
        "hash_id": listing.hash_id,
        "title": listing.title,
        "category_main_cb": listing.category_main_cb,
        "category_type_cb": listing.category_type_cb,
        "category_sub_cb": listing.category_sub_cb,
        "price_czk": listing.price_czk,
        "price_czk_unit": listing.price_czk_unit,
        "currency": listing.currency,
        "gps_lat": listing.gps_lat,
        "gps_lon": listing.gps_lon,
        "locality_text": listing.locality_text,
        "seller_type": listing.seller_type,
        "is_active": listing.is_active,
        "first_seen_at": listing.first_seen_at,
        "last_seen_at": listing.last_seen_at,
        "removed_at": listing.removed_at,
        "source_url": resolve_public_source_url(
            source_url=listing.source_url,
            hash_id=listing.hash_id,
            category_main_cb=listing.category_main_cb,
            category_type_cb=listing.category_type_cb,
            category_sub_cb=listing.category_sub_cb,
            title=listing.title,
        ),
        "usable_area": detail.usable_area if detail else None,
        "floor_area": detail.floor_area if detail else None,
        "land_area": detail.land_area if detail else None,
        "built_up_area": detail.built_up_area if detail else None,
        "floor": detail.floor if detail else None,
        "floor_number": detail.floor_number if detail else None,
        "total_floors": detail.total_floors if detail else None,
        "ownership_cb": detail.ownership if detail else None,
        "building_type_cb": detail.building_type if detail else None,
        "building_condition_cb": detail.building_condition if detail else None,
        "material": detail.material if detail else None,
        "object_kind_cb": detail.object_kind if detail else None,
        "energy_efficiency_rating_cb": detail.energy_efficiency_rating if detail else None,
        "furnished_cb": detail.furnished if detail else None,
        "elevator_cb": detail.elevator if detail else None,
        "balcony": detail.balcony if detail else None,
        "terrace": detail.terrace if detail else None,
        "loggia": detail.loggia if detail else None,
        "cellar": detail.cellar if detail else None,
        "garage": detail.garage if detail else None,
        "garden": detail.garden if detail else None,
        "parking_lots": detail.parking_lots if detail else None,
        "broker_company": detail.broker_company if detail else None,
        "note_about_price": detail.note_about_price if detail else None,
        "last_updated_at": detail.last_updated_at if detail else None,
        "region": listing.resolved_region_name or (location.region if location else None),
        "resolved_region_name": listing.resolved_region_name,
        "resolved_region_id": listing.resolved_region_id,
        "region_source": listing.region_source,
        "region_unknown_reason": listing.region_unknown_reason,
        "district": location.district if location else None,
        "municipality": location.municipality if location else None,
        "metoda_sberu": COLLECTION_METHOD,
        "zdroj": SOURCE_NAME,
    }
    return row


@router.get("/listings", summary="Export nabídek (raw / cleaned / filtered)")
def export_listings(
    session: Session = Depends(get_session),
    scope: str = Query("cleaned", description="raw | cleaned (filtered export = cleaned + any filter params below)"),
    format: str = Depends(_format_param),
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
    if scope not in ("raw", "cleaned"):
        raise HTTPException(status_code=400, detail="scope musí být 'raw' nebo 'cleaned'")

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

    from sqlalchemy import func as sa_func

    total_matched = session.exec(select(sa_func.count()).select_from(base.subquery())).one()
    truncated = total_matched > MAX_EXPORT_ROWS
    rows_result = session.exec(base.order_by(Listing.last_seen_at.desc()).limit(MAX_EXPORT_ROWS)).all()

    if scope == "raw":
        export_rows = [_raw_listing_row(listing, detail, location) for listing, detail, location in rows_result]
    else:
        listing_ids = [listing.id for listing, _, _ in rows_result]
        image_counts: dict[int, int] = {}
        if listing_ids:
            from sqlalchemy import func as sa_func

            image_rows = session.exec(
                select(Image.listing_id, sa_func.count(Image.id)).where(Image.listing_id.in_(listing_ids)).group_by(Image.listing_id)
            ).all()
            image_counts = dict(image_rows)
        price_stats = _price_history_stats(session, listing_ids)

        export_rows = []
        for listing, detail, location in rows_result:
            change_count, has_drop = price_stats.get(listing.id, (0, False))
            listing_read = _build_listing_read(
                listing,
                detail,
                location,
                price_change_count=change_count,
                has_price_drop=has_drop,
                image_count=image_counts.get(listing.id, 0),
            )
            row = listing_read.model_dump()
            row["metoda_sberu"] = COLLECTION_METHOD
            row["zdroj"] = SOURCE_NAME
            export_rows.append(row)

    filename_stem = f"nabidky_{scope}_{date.today().isoformat()}"
    return _respond(export_rows, format, filename_stem, total_matched=total_matched, truncated=truncated)


def _add_derived_timeseries_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Adds mom/yoy/rolling/price-index/volatility columns computed per
    segment (location_id, category_main_cb, category_type_cb), ordered by
    month. All derived from cena_za_m2 (avg price per m2), the only metric
    consistently comparable across segments and time."""

    df = df.sort_values(["segment", "rok_mesic"]).reset_index(drop=True)
    grouped = df.groupby("segment")["cena_za_m2"]

    df["mom_change_pct"] = grouped.pct_change(1) * 100
    df["yoy_change_pct"] = grouped.pct_change(12) * 100
    df["rolling_3m_avg"] = grouped.transform(lambda s: s.rolling(3, min_periods=1).mean())
    df["rolling_12m_avg"] = grouped.transform(lambda s: s.rolling(12, min_periods=1).mean())
    df["price_index_base_100"] = grouped.transform(lambda s: (s / s.iloc[0]) * 100 if pd.notna(s.iloc[0]) and s.iloc[0] != 0 else pd.NA)
    df["volatility_12m"] = grouped.transform(lambda s: s.pct_change().rolling(12, min_periods=2).std() * 100)

    # spread_sale_vs_rent: naive avg_price_per_m2 difference between category_type_cb
    # 1 (prodej) and 2 (pronájem) for the same (location, category_main_cb, month).
    # This is NOT a yield/cap-rate calculation -- sale price/m2 and monthly rent/m2
    # are different units -- it's an illustrative absolute spread only.
    pivot_key = df["location_id"].astype(str) + "|" + df["category_main_cb"].astype(str) + "|" + df["rok_mesic"]
    df["_pivot_key"] = pivot_key
    sale_prices = df.loc[df["category_type_cb"] == 1].set_index("_pivot_key")["cena_za_m2"]
    rent_prices = df.loc[df["category_type_cb"] == 2].set_index("_pivot_key")["cena_za_m2"]
    spread = (sale_prices - rent_prices).reindex(df["_pivot_key"]).reset_index(drop=True)
    df["spread_sale_vs_rent"] = spread
    df = df.drop(columns=["_pivot_key"])

    return df


@router.get("/analytics/timeseries", summary="Export časové řady (agregace podle měsíce a segmentu)")
def export_analytics_timeseries(
    session: Session = Depends(get_session),
    format: str = Depends(_format_param),
    days: int = Query(730, ge=31, le=3650, description="Kolik dní historie zahrnout"),
    category_main_cb: Optional[int] = None,
    category_type_cb: Optional[int] = None,
    location_id: Optional[int] = None,
):
    since = date.today() - timedelta(days=days)
    stmt = select(AnalyticSnapshot, Location).join(Location, Location.id == AnalyticSnapshot.location_id, isouter=True).where(
        AnalyticSnapshot.snapshot_date >= since
    )
    if category_main_cb is not None:
        stmt = stmt.where(AnalyticSnapshot.category_main_cb == category_main_cb)
    if category_type_cb is not None:
        stmt = stmt.where(AnalyticSnapshot.category_type_cb == category_type_cb)
    if location_id is not None:
        stmt = stmt.where(AnalyticSnapshot.location_id == location_id)

    rows = session.exec(stmt).all()
    if not rows:
        return _respond([], format, f"casova_rada_{date.today().isoformat()}")

    raw = pd.DataFrame(
        [
            {
                "snapshot_date": snap.snapshot_date,
                "location_id": snap.location_id if snap.location_id is not None else -1,
                "lokalita": (loc.municipality or loc.district or loc.region) if loc else None,
                "category_main_cb": snap.category_main_cb if snap.category_main_cb is not None else -1,
                "category_type_cb": snap.category_type_cb if snap.category_type_cb is not None else -1,
                "avg_price_czk": snap.avg_price_czk,
                "avg_price_per_m2": snap.avg_price_per_m2,
                "listing_count": snap.listing_count,
                "new_count": snap.new_count,
                "avg_days_on_market": snap.avg_days_on_market,
            }
            for snap, loc in rows
        ]
    )
    raw["rok_mesic"] = pd.to_datetime(raw["snapshot_date"]).dt.strftime("%Y-%m")
    raw["segment"] = (
        raw["location_id"].astype(str) + "_" + raw["category_main_cb"].astype(str) + "_" + raw["category_type_cb"].astype(str)
    )

    monthly = (
        raw.groupby(["segment", "location_id", "category_main_cb", "category_type_cb", "rok_mesic", "lokalita"], dropna=False)
        .agg(
            cena_za_m2=("avg_price_per_m2", "mean"),
            prumerna_cena=("avg_price_czk", "mean"),
            prumerna_doba_inzerce=("avg_days_on_market", "mean"),
            aktivnich_nabidek=("listing_count", "mean"),
            pocet_novych_nabidek=("new_count", "sum"),
        )
        .reset_index()
    )

    monthly = _add_derived_timeseries_columns(monthly)

    monthly["datum"] = monthly["rok_mesic"] + "-01"
    monthly["rok"] = monthly["rok_mesic"].str.slice(0, 4).astype(int)
    monthly["mesic"] = monthly["rok_mesic"].str.slice(5, 7).astype(int)
    monthly["typ"] = monthly["category_main_cb"].apply(lambda v: PROPERTY_TYPES.get(v) if v != -1 else None)
    monthly["kategorie"] = monthly["typ"]
    monthly["transakce"] = monthly["category_type_cb"].apply(lambda v: DEAL_TYPES.get(v) if v != -1 else None)
    monthly["stav"] = "aktivní"  # AnalyticSnapshot only ever counts currently-active listings
    monthly["metoda_sberu"] = COLLECTION_METHOD
    monthly["zdroj"] = SOURCE_NAME

    output_columns = [
        "datum",
        "rok",
        "mesic",
        "rok_mesic",
        "lokalita",
        "typ",
        "kategorie",
        "stav",
        "transakce",
        "cena_za_m2",
        "prumerna_cena",
        "prumerna_doba_inzerce",
        "aktivnich_nabidek",
        "pocet_novych_nabidek",
        "metoda_sberu",
        "zdroj",
        "segment",
        "mom_change_pct",
        "yoy_change_pct",
        "rolling_3m_avg",
        "rolling_12m_avg",
        "price_index_base_100",
        "spread_sale_vs_rent",
        "volatility_12m",
    ]
    monthly = monthly.sort_values(["segment", "rok_mesic"])
    # NaN -> None is handled centrally in serialize_rows() (pandas float columns
    # can't hold None, so a .where(..., None) here would just be re-coerced
    # back to NaN by pandas -- see app/domain/export.py's _clean_nan docstring).
    export_rows = monthly[output_columns].to_dict(orient="records")

    return _respond(export_rows, format, f"casova_rada_{date.today().isoformat()}")


@router.get("/analytics/valuation", summary="Analytický export (odhad ceny + anomálie)")
def export_analytics_valuation(
    session: Session = Depends(get_session),
    format: str = Depends(_format_param),
    classification: Optional[str] = None,
    min_score: float = Query(0, ge=0, le=100),
    limit: int | None = Query(
        None,
        ge=1,
        le=MAX_EXPORT_ROWS,
        description="Volitelný strop řádků. Bez limitu exportuje všechny shody (do max_export_rows).",
    ),
):
    stmt = (
        select(Listing, ListingValuation, ListingAnomaly)
        .join(ListingValuation, ListingValuation.listing_id == Listing.id, isouter=True)
        .join(ListingAnomaly, ListingAnomaly.listing_id == Listing.id, isouter=True)
        .where(Listing.is_active == True)  # noqa: E712
    )
    if classification is not None:
        stmt = stmt.where(ListingValuation.classification == classification)
    if min_score:
        stmt = stmt.where(ListingAnomaly.anomaly_score >= min_score)
    total_matched = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    effective_limit = limit if limit is not None else MAX_EXPORT_ROWS
    truncated = total_matched > effective_limit
    rows = session.exec(stmt.limit(effective_limit)).all()
    export_rows = [
        {
            "listing_id": listing.id,
            "hash_id": listing.hash_id,
            "title": listing.title,
            "price_czk": listing.price_czk,
            "expected_price_czk": valuation.expected_price_czk if valuation else None,
            "expected_price_per_m2": valuation.expected_price_per_m2 if valuation else None,
            "residual_absolute": valuation.residual_absolute if valuation else None,
            "residual_percent": valuation.residual_percent if valuation else None,
            # classification/confidence are plain strings (not Enum members) as
            # loaded from the DB -- ListingValuation declares them with
            # sa_column=Column(String) (see that model's docstring), so no
            # .value access here.
            "classification": valuation.classification if valuation else None,
            "valuation_confidence": valuation.confidence if valuation else None,
            "anomaly_score": anomaly.anomaly_score if anomaly else None,
            "anomaly_flags": ", ".join(anomaly.anomaly_flags) if anomaly and anomaly.anomaly_flags else None,
            "anomaly_confidence": anomaly.confidence_score if anomaly else None,
            "source_url": resolve_public_source_url(
                source_url=listing.source_url,
                hash_id=listing.hash_id,
                category_main_cb=listing.category_main_cb,
                category_type_cb=listing.category_type_cb,
                category_sub_cb=listing.category_sub_cb,
                title=listing.title,
            ),
            "metoda_sberu": COLLECTION_METHOD,
            "zdroj": SOURCE_NAME,
        }
        for listing, valuation, anomaly in rows
    ]

    return _respond(
        export_rows,
        format,
        f"analyticky_export_{date.today().isoformat()}",
        total_matched=total_matched,
        truncated=truncated,
    )
