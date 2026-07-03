"""Human-readable snapshot / freshness metadata for dataset counts."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, func, select

from app.models import Listing, ScrapingRun
from app.models.scraping_run import RunStatus, RunType

FRESHNESS_LABELS_CS: dict[str, str] = {
    "empty": "Prázdný dataset",
    "in_progress": "Průběžný snapshot — scraping běží",
    "final_complete": "Konečný snapshot — úplný dataset",
    "final_partial": "Konečný snapshot — neúplný dataset",
}

COMPARE_GUIDANCE_CS: dict[str, str] = {
    "empty": "Dataset je prázdný. Spusťte scraping ve Správě scrapingu.",
    "in_progress": (
        "Počty se průběžně mění. Nesrovnávejte celkový počet v aplikaci s ~106k na Sreality.cz. "
        "Porovnání je bezpečné až po dokončení běhu, a to po jednotlivých typech nemovitostí."
    ),
    "final_complete": (
        "Dataset je po úplném sweepu. Celkový počet lze porovnat se součtem Sreality API slice totals "
        "(±2 % strukturální tolerance). Pro filtrované UI Sreality porovnávejte stejný slice."
    ),
    "final_partial": (
        "Dataset je uzavřený, ale neúplný (přerušený běh nebo chybějící slice). "
        "Porovnávejte jen dokončené slice; globální součet s Sreality není spolehlivý."
    ),
}

SLICE_STATUS_LABELS_CS: dict[str, str] = {
    "aligned": "Shoda (±2 %)",
    "not_started": "Nezpracováno (běh probíhá)",
    "in_progress": "Doplňuje se (běh probíhá)",
    "coverage_gap": "Mezera po dokončení slice (>2 %)",
    "missing": "Chybí v DB (slice nebyla stažena)",
    "over": "V DB více než API (>2 %)",
    "empty": "Prázdné na Sreality i v DB",
    "unknown": "Neznámé (bez live API sondy)",
}


def is_count_final(freshness: str) -> bool:
    return freshness in ("final_complete", "final_partial")


def safe_to_compare_with_sreality_total(freshness: str) -> bool:
    """Global slice-sum comparison is meaningful only after a complete final sweep."""
    return freshness == "final_complete"


def safe_to_compare_per_slice(freshness: str) -> bool:
    return freshness in ("final_complete", "final_partial")


def get_last_dataset_update_at(session: Session, *, running_sweep: ScrapingRun | None = None) -> datetime | None:
    latest_listing = session.exec(select(func.max(Listing.last_seen_at))).one()
    if running_sweep is not None:
        if latest_listing is None:
            return running_sweep.started_at
        if running_sweep.started_at and latest_listing:
            return max(latest_listing, running_sweep.started_at)
    return latest_listing


def build_snapshot_metadata(
    *,
    freshness: str,
    running_sweep: ScrapingRun | None = None,
    last_full_sweep_at: datetime | None = None,
    last_successful_scrape_at: datetime | None = None,
    last_dataset_update_at: datetime | None = None,
) -> dict:
    return {
        "snapshot_state_label_cs": FRESHNESS_LABELS_CS.get(freshness, freshness),
        "is_count_final": is_count_final(freshness),
        "safe_to_compare_with_sreality_total": safe_to_compare_with_sreality_total(freshness),
        "safe_to_compare_per_slice": safe_to_compare_per_slice(freshness),
        "compare_guidance_cs": COMPARE_GUIDANCE_CS.get(freshness, ""),
        "last_dataset_update_at": (
            last_dataset_update_at.isoformat() if last_dataset_update_at else None
        ),
        "snapshot_reference_run_id": running_sweep.id if running_sweep else None,
        "last_full_sweep_at": last_full_sweep_at.isoformat() if last_full_sweep_at else None,
        "last_successful_scrape_at": (
            last_successful_scrape_at.isoformat() if last_successful_scrape_at else None
        ),
    }


def latest_finished_incremental_run(session: Session) -> ScrapingRun | None:
    return session.exec(
        select(ScrapingRun)
        .where(
            ScrapingRun.run_type == RunType.incremental,
            ScrapingRun.status.in_([RunStatus.success, RunStatus.partial, RunStatus.failed]),
            ScrapingRun.finished_at.is_not(None),
        )
        .order_by(ScrapingRun.finished_at.desc())
    ).first()
