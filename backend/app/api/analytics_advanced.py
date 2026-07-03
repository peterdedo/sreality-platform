"""Pokročilé analýzy (advanced analytics) endpoints. See docs/METHODOLOGY.md
for the full methodology behind every metric exposed here, and
architecture.md §9 for the module layout."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.analytics.advanced import comparables as comparables_module
from app.analytics.advanced import segments as segments_module
from app.analytics.advanced import spatial as spatial_module
from app.analytics.advanced.pipeline import run_full_recompute
from app.analytics.advanced.summaries import anomaly_summary, valuation_summary
from app.analytics.dataset_scope import FULL_LOCAL_DATASET, analytics_meta
from app.api.deps import require_api_key
from app.api.rate_limit import heavy_endpoint_limiter
from app.core.db import engine, get_session
from app.models import AnalyticsRun, AnalyticSnapshot, Listing, ListingAnomaly, ListingValuation
from app.schemas.analytics_advanced import AnalyticsRunRead, TriggerRecomputeResponse

router = APIRouter(prefix="/analytics/advanced", tags=["analytics-advanced"])


@router.get("/market-dynamics", summary="Vývoj trhu v čase")
def get_market_dynamics(
    days: int = Query(180, ge=1, le=3650),
    category_main_cb: Optional[int] = None,
    category_type_cb: Optional[int] = None,
    session: Session = Depends(get_session),
):
    since = date.today() - timedelta(days=days)
    stmt = select(AnalyticSnapshot).where(AnalyticSnapshot.snapshot_date >= since)
    if category_main_cb is not None:
        stmt = stmt.where(AnalyticSnapshot.category_main_cb == category_main_cb)
    if category_type_cb is not None:
        stmt = stmt.where(AnalyticSnapshot.category_type_cb == category_type_cb)
    stmt = stmt.order_by(AnalyticSnapshot.snapshot_date)
    return {**analytics_meta(), "items": session.exec(stmt).all()}


@router.get("/segments", summary="Segmentace trhu")
def get_segments(
    dimension: str = Query(..., description=f"Jedna z: {', '.join(segments_module.ALLOWED_DIMENSIONS)}"),
    category_main_cb: Optional[int] = None,
    session: Session = Depends(get_session),
):
    try:
        items = segments_module.segment_breakdown(session, dimension, category_main_cb)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    listing_sum = sum(row["listing_count"] for row in items)
    return {**analytics_meta(), "items": items, "listing_count_sum": listing_sum}


@router.get("/valuation/summary", summary="Agregace odhadů ceny (celý dataset)")
def get_valuation_summary(session: Session = Depends(get_session)):
    return {**analytics_meta(), **valuation_summary(session)}


@router.get("/valuation/{listing_id}", summary="Odhad ceny nabídky")
def get_valuation(listing_id: int, session: Session = Depends(get_session)):
    valuation = session.exec(select(ListingValuation).where(ListingValuation.listing_id == listing_id)).first()
    if valuation is None:
        raise HTTPException(status_code=404, detail="Odhad ceny pro tuto nabídku ještě nebyl spočítán")
    return valuation


@router.get("/valuation", summary="Nabídky pod/nad tržní cenou")
def list_valuations(
    classification: Optional[str] = Query(None, description="under_market | near_market | over_market"),
    min_confidence: Optional[str] = Query(None, description="low | medium | high"),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=500_000,
        description="Volitelný strop řádků pro tabulku v UI. Bez limitu vrátí všechny záznamy.",
    ),
    offset: int = Query(0, ge=0, description="Posun pro stránkování tabulky v UI."),
    session: Session = Depends(get_session),
):
    # Same entity set as valuation_summary(): valuations of ACTIVE listings
    # only. Without this join the table showed stale valuations of delisted
    # listings while the summary above it counted only active ones.
    stmt = select(ListingValuation).join(Listing, Listing.id == ListingValuation.listing_id).where(
        Listing.is_active == True  # noqa: E712
    )
    if classification:
        stmt = stmt.where(ListingValuation.classification == classification)
    if min_confidence:
        allowed_order = {"low": 0, "medium": 1, "high": 2}
        min_rank = allowed_order.get(min_confidence, 0)
        allowed = [k for k, v in allowed_order.items() if v >= min_rank]
        stmt = stmt.where(ListingValuation.confidence.in_(allowed))
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    ordered = stmt.order_by(ListingValuation.residual_percent)
    paged = ordered.offset(offset)
    rows = session.exec(paged.limit(limit) if limit is not None else paged).all()
    return {
        **analytics_meta(scope=FULL_LOCAL_DATASET if limit is None else "ui_presentation"),
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/anomalies/summary", summary="Agregace anomálií (celý dataset)")
def get_anomaly_summary(
    min_score: float = Query(0, ge=0, le=100),
    session: Session = Depends(get_session),
):
    return {**analytics_meta(), **anomaly_summary(session, min_score)}


@router.get("/anomalies", summary="Podezřelé / anomální nabídky")
def list_anomalies(
    min_score: float = Query(0, ge=0, le=100),
    flag: Optional[str] = None,
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=500_000,
        description="Volitelný strop řádků pro tabulku v UI. Bez limitu vrátí všechny záznamy.",
    ),
    offset: int = Query(0, ge=0, description="Posun pro stránkování tabulky v UI."),
    session: Session = Depends(get_session),
):
    stmt = (
        select(ListingAnomaly)
        .join(Listing, Listing.id == ListingAnomaly.listing_id)
        .where(Listing.is_active == True, ListingAnomaly.anomaly_score >= min_score)  # noqa: E712
    )
    ordered = stmt.order_by(ListingAnomaly.anomaly_score.desc())
    if flag:
        # anomaly_flags is a JSON list, filtered in Python -- but bounded: rows
        # are streamed in score order and we stop once the limit is satisfied,
        # instead of materializing the whole table per request.
        rows = []
        total = 0
        skipped = 0
        for row in session.exec(ordered):
            if flag in (row.anomaly_flags or []):
                total += 1
                if skipped < offset:
                    skipped += 1
                    continue
                if limit is None or len(rows) < limit:
                    rows.append(row)
    else:
        total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
        paged = ordered.offset(offset)
        rows = session.exec(paged.limit(limit) if limit is not None else paged).all()
    return {
        **analytics_meta(scope=FULL_LOCAL_DATASET if limit is None else "ui_presentation"),
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/comparables/{listing_id}", summary="Srovnatelné nabídky")
def get_comparables(listing_id: int, limit: int = Query(8, ge=1, le=20), session: Session = Depends(get_session)):
    result = comparables_module.find_comparables(session, listing_id, limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Nabídka nebyla nalezena")
    return result


@router.get("/spatial/heatmap", summary="Prostorová heatmapa")
def get_spatial_heatmap(
    category_main_cb: Optional[int] = None,
    category_type_cb: Optional[int] = None,
    live: bool = Query(False, description="Vynutit živý přepočet místo posledního snapshotu"),
    south: Optional[float] = Query(None, description="Jižní hranice výřezu mapy"),
    west: Optional[float] = Query(None, description="Západní hranice výřezu mapy"),
    north: Optional[float] = Query(None, description="Severní hranice výřezu mapy"),
    east: Optional[float] = Query(None, description="Východní hranice výřezu mapy"),
    zoom: Optional[int] = Query(None, ge=1, le=18, description="Úroveň přiblížení mapy pro agregaci mřížky"),
    session: Session = Depends(get_session),
):
    return {
        **analytics_meta(),
        **spatial_module.get_heatmap(
            session,
            category_main_cb=category_main_cb,
            category_type_cb=category_type_cb,
            live=live,
            south=south,
            west=west,
            north=north,
            east=east,
            zoom=zoom,
        ),
    }


@router.get("/runs", response_model=list[AnalyticsRunRead], summary="Historie výpočtů pokročilých analýz")
def list_runs(limit: int = 50, session: Session = Depends(get_session)):
    from app.analytics.advanced.pipeline import reconcile_orphaned_analytics_runs

    reconcile_orphaned_analytics_runs(session)
    stmt = select(AnalyticsRun).order_by(AnalyticsRun.started_at.desc()).limit(limit)
    return session.exec(stmt).all()


def _run_recompute_in_background():
    with Session(engine) as session:
        run_full_recompute(session)


@router.post(
    "/recompute",
    response_model=TriggerRecomputeResponse,
    summary="Přepočítat pokročilé analýzy",
    dependencies=[Depends(require_api_key), Depends(heavy_endpoint_limiter)],
)
def trigger_recompute(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_recompute_in_background)
    return TriggerRecomputeResponse(message="Přepočet pokročilých analýz byl spuštěn na pozadí.")
