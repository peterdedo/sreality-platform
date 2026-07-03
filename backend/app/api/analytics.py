from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.analytics import queries
from app.analytics.dataset_scope import FULL_LOCAL_DATASET, analytics_meta
from app.core.db import get_session
from app.scraping.count_reconciliation import count_reconciliation_report

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/price-per-m2", summary="Cena za m² podle lokality")
def get_price_per_m2(category_main_cb: int | None = None, session: Session = Depends(get_session)):
    return {**analytics_meta(), "items": queries.price_per_m2_by_location(session, category_main_cb)}


@router.get("/price-evolution", summary="Vývoj ceny v čase")
def get_price_evolution(listing_id: int | None = None, days: int = Query(365, ge=1, le=3650), session: Session = Depends(get_session)):
    return {**analytics_meta(), "items": queries.price_evolution(session, listing_id, days)}


@router.get("/inventory-by-region", summary="Nabídka podle kraje")
def get_inventory_by_region(session: Session = Depends(get_session)):
    items = queries.inventory_by_region(session)
    return {
        **analytics_meta(),
        "items": items,
        "listing_count_sum": sum(row["listing_count"] for row in items),
    }


@router.get("/dataset-summary", summary="Přehled pokrytí lokálního datasetu")
def get_dataset_summary(session: Session = Depends(get_session)):
    return {**analytics_meta(), **queries.dataset_summary(session)}


@router.get("/count-reconciliation", summary="Audit shody počtů: lokální DB vs Sreality API")
async def get_count_reconciliation(
    live: bool = Query(
        False,
        description="Pokud true, live-probe Sreality API totals (~20 dotazů, trvá několik sekund).",
    ),
    session: Session = Depends(get_session),
):
    report = await count_reconciliation_report(session, live_sreality=live)
    return {**analytics_meta(), **report.to_dict()}


@router.get("/new-vs-removed", summary="Nové vs. stažené nabídky")
def get_new_vs_removed(days: int = Query(30, ge=1, le=365), session: Session = Depends(get_session)):
    return {**analytics_meta(), **queries.new_vs_removed(session, days)}


@router.get("/price-drops", summary="Detekce snížení ceny")
def get_price_drops(
    min_drop_pct: float = Query(5.0, ge=0),
    limit: int | None = Query(
        None,
        ge=1,
        le=500_000,
        description="Volitelný strop řádků pro tabulku v UI. Bez limitu vrátí všechny shody z celého datasetu.",
    ),
    include_total: bool = Query(
        True,
        description="Při false a nastaveném limitu přeskočí drahý COUNT přes celý dataset (rychlejší náhled).",
    ),
    session: Session = Depends(get_session),
):
    return {**analytics_meta(), **queries.price_drops(session, min_drop_pct, limit, include_total)}
