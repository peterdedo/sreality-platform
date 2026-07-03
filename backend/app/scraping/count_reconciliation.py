"""Compare Sreality search API totals with the local scraped dataset."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Listing, ScrapingRun
from app.models.scraping_run import RunStatus, RunType
from app.scraping.client import SrealityClient
from app.scraping.constants import CATEGORY_COMBINATIONS
from app.scraping.pipeline import _fetch_category_estates, _probe_search_total

EXPECTED_CATEGORY_SLICES = len(CATEGORY_COMBINATIONS)
# A completed full sweep over all 20 category×deal slices typically yields ~100k+ rows.
FULL_SWEEP_MIN_ITEMS_SEEN = 50_000


@dataclass
class CategorySliceComparison:
    name: str
    category_main_cb: int
    category_type_cb: int
    sreality_api_total: int
    db_active_count: int
    db_total_count: int
    delta: int
    delta_pct: float | None
    reconciliation_status: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category_main_cb": self.category_main_cb,
            "category_type_cb": self.category_type_cb,
            "sreality_api_total": self.sreality_api_total,
            "db_active_count": self.db_active_count,
            "db_total_count": self.db_total_count,
            "delta": self.delta,
            "delta_pct": self.delta_pct,
            "reconciliation_status": self.reconciliation_status,
        }


@dataclass
class CountReconciliationReport:
    generated_at: datetime
    db_active_total: int
    db_all_total: int
    sreality_api_slice_sum: int | None
    active_category_slice_count: int
    expected_category_slice_count: int
    dataset_completeness: str
    dataset_freshness: str
    duplicate_hash_ids: int
    inventory_sum_matches_active: bool
    last_full_sweep_run_id: int | None
    last_full_sweep_items_seen: int | None
    last_full_sweep_finished_at: datetime | None
    running_scrape: dict | None = None
    run_items_seen: int | None = None
    db_vs_run_items_seen_delta: int | None = None
    partial_or_running_runs: list[dict] = field(default_factory=list)
    categories: list[CategorySliceComparison] = field(default_factory=list)
    structural_notes: list[str] = field(default_factory=list)
    report_extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "db_active_total": self.db_active_total,
            "db_all_total": self.db_all_total,
            "sreality_api_slice_sum": self.sreality_api_slice_sum,
            "db_vs_sreality_slice_delta": (
                (self.db_active_total - self.sreality_api_slice_sum)
                if self.sreality_api_slice_sum is not None
                else None
            ),
            "active_category_slice_count": self.active_category_slice_count,
            "expected_category_slice_count": self.expected_category_slice_count,
            "dataset_completeness": self.dataset_completeness,
            "dataset_freshness": self.dataset_freshness,
            "duplicate_hash_ids": self.duplicate_hash_ids,
            "inventory_sum_matches_active": self.inventory_sum_matches_active,
            "running_scrape": self.running_scrape,
            "run_items_seen": self.run_items_seen,
            "db_vs_run_items_seen_delta": self.db_vs_run_items_seen_delta,
            "last_full_sweep_run_id": self.last_full_sweep_run_id,
            "last_full_sweep_items_seen": self.last_full_sweep_items_seen,
            "last_full_sweep_finished_at": (
                self.last_full_sweep_finished_at.isoformat() if self.last_full_sweep_finished_at else None
            ),
            "partial_or_running_runs": self.partial_or_running_runs,
            "categories": [c.to_dict() for c in self.categories],
            "structural_notes": self.structural_notes,
            "count_semantics": COUNT_SEMANTICS,
            **self.report_extras,
        }


COUNT_SEMANTICS = {
    "db_active_total": "Počet řádků v PostgreSQL s is_active=true (lokální dataset).",
    "run_items_seen": "Unikátní hash_id zpracované v aktuálním/probíhajícím sweepu (dedup napříč slice).",
    "sreality_api_slice_sum": "Součet pagination.total ze 20 dotazů category_main_cb×category_type_cb na GET /api/v1/estates/search (stejný filtr jako scraper, bez kraje/dispozice).",
    "db_vs_sreality_slice_delta": "Rozdíl DB vs součet API totals. Záporný během běhu = nezpracované slice, ne chyba scraperu.",
    "dataset_freshness": "in_progress = sweep běží, počty nejsou konečné; final_complete/final_partial = po dokončení běhu.",
    "reconciliation_status_per_slice": "aligned | in_progress | not_started | coverage_gap | over | empty | missing",
}


def _db_category_counts(session: Session) -> dict[tuple[int, int], tuple[int, int]]:
    rows = session.exec(
        select(
            Listing.category_main_cb,
            Listing.category_type_cb,
            func.count().filter(Listing.is_active == True),  # noqa: E712
            func.count(),
        )
        .group_by(Listing.category_main_cb, Listing.category_type_cb)
    ).all()
    return {(main, deal): (int(active or 0), int(total or 0)) for main, deal, active, total in rows}


def _active_category_slice_count(session: Session) -> int:
    return session.exec(
        select(func.count())
        .select_from(
            select(Listing.category_main_cb, Listing.category_type_cb)
            .where(Listing.is_active == True)  # noqa: E712
            .group_by(Listing.category_main_cb, Listing.category_type_cb)
            .subquery()
        )
    ).one()


def _last_full_sweep(session: Session) -> ScrapingRun | None:
    return session.exec(
        select(ScrapingRun)
        .where(
            ScrapingRun.run_type == RunType.incremental,
            ScrapingRun.status == RunStatus.success,
            ScrapingRun.category == "all",
            ScrapingRun.items_seen >= FULL_SWEEP_MIN_ITEMS_SEEN,
        )
        .order_by(ScrapingRun.finished_at.desc())
    ).first()


def _running_sweep(session: Session) -> ScrapingRun | None:
    return session.exec(
        select(ScrapingRun)
        .where(
            ScrapingRun.run_type == RunType.incremental,
            ScrapingRun.status == RunStatus.running,
        )
        .order_by(ScrapingRun.id.desc())
    ).first()


def assess_dataset_freshness(
    session: Session,
    *,
    running_sweep: ScrapingRun | None = None,
    completeness: str | None = None,
) -> str:
    """``empty`` | ``in_progress`` | ``final_complete`` | ``final_partial``."""
    running_sweep = running_sweep if running_sweep is not None else _running_sweep(session)
    if running_sweep is not None:
        return "in_progress"
    if completeness is None:
        completeness = assess_dataset_completeness(session)
    if completeness == "empty":
        return "empty"
    if completeness == "complete":
        return "final_complete"
    return "final_partial"


def classify_slice_reconciliation(
    sreality_api_total: int,
    db_active_count: int,
    *,
    scrape_in_progress: bool,
) -> str:
    """Per category×deal slice status for the same API query (main_cb + type_cb only)."""
    if sreality_api_total == 0 and db_active_count == 0:
        return "empty"
    if db_active_count == 0 and sreality_api_total > 0:
        return "not_started" if scrape_in_progress else "missing"
    delta = db_active_count - sreality_api_total
    tolerance = max(2, int(sreality_api_total * 0.025))
    if abs(delta) <= tolerance:
        return "aligned"
    if db_active_count < sreality_api_total:
        if scrape_in_progress:
            return "in_progress"
        # Slice was processed (db > 0) but remains below API beyond tolerance.
        return "coverage_gap"
    return "over"


def assess_dataset_completeness(
    session: Session,
    *,
    active_total: int | None = None,
    active_slice_count: int | None = None,
    last_full_sweep: ScrapingRun | None = None,
) -> str:
    """Return ``empty`` | ``partial`` | ``complete`` for the local dataset."""
    active_total = (
        active_total
        if active_total is not None
        else session.exec(
            select(func.count()).select_from(Listing).where(Listing.is_active == True)  # noqa: E712
        ).one()
    )
    if active_total == 0:
        return "empty"

    active_slice_count = (
        active_slice_count if active_slice_count is not None else _active_category_slice_count(session)
    )
    last_full_sweep = last_full_sweep if last_full_sweep is not None else _last_full_sweep(session)

    if last_full_sweep is not None and active_slice_count >= EXPECTED_CATEGORY_SLICES:
        return "complete"
    if last_full_sweep is not None and active_slice_count >= EXPECTED_CATEGORY_SLICES - 2:
        # Allow tiny category slices with zero listings on Sreality side.
        return "complete"
    return "partial"


async def probe_sreality_category_totals() -> dict[tuple[int, int], int]:
    client = SrealityClient()
    totals: dict[tuple[int, int], int] = {}
    try:
        for cat in CATEGORY_COMBINATIONS:
            params = f"category_main_cb={cat['category_main_cb']}&category_type_cb={cat['category_type_cb']}"
            totals[(cat["category_main_cb"], cat["category_type_cb"])] = await _probe_search_total(client, params)
    finally:
        await client.aclose()
    return totals


STRUCTURAL_NOTES = [
    "Sreality UI zobrazuje počty pro konkrétní filtr (kraj, dispozice, cena); náš scrape používá 20 globálních category×deal slice bez dalších filtrů.",
    "Součet 20 API pagination.total je odhad celého trhu na Sreality; není to stejné číslo jako homepage banner bez filtrů, pokud UI aplikuje skryté filtry.",
    "Region/sub fan-out nechytí ~0,3–2 % inzerátů bez locality_region_id (coverage_gap v logu běhu).",
    "DB active count odpovídá poslednímu úplnému sweepu + delisting; přerušený běh neaktualizuje celý trh.",
    "Nabídky tabulka zobrazuje total dle aktivních filtrů, ne globální active_listing_count.",
]


def build_count_reconciliation_report(session: Session, *, sreality_totals: dict[tuple[int, int], int] | None) -> CountReconciliationReport:
    from sqlalchemy import text

    from app.analytics.queries import inventory_by_region

    db_active = session.exec(
        select(func.count()).select_from(Listing).where(Listing.is_active == True)  # noqa: E712
    ).one()
    db_all = session.exec(select(func.count()).select_from(Listing)).one()
    dup = session.exec(
        text("SELECT COUNT(*) FROM (SELECT hash_id FROM listing GROUP BY hash_id HAVING COUNT(*)>1) t")
    ).scalar()
    db_by_cat = _db_category_counts(session)
    slice_count = _active_category_slice_count(session)
    inv_sum = sum(row["listing_count"] for row in inventory_by_region(session))
    last_full = _last_full_sweep(session)
    running = _running_sweep(session)

    partial_runs = session.exec(
        select(ScrapingRun)
        .where(ScrapingRun.status.in_([RunStatus.partial, RunStatus.running]))
        .order_by(ScrapingRun.id.desc())
    ).all()

    scrape_in_progress = running is not None
    categories: list[CategorySliceComparison] = []
    for cat in CATEGORY_COMBINATIONS:
        key = (cat["category_main_cb"], cat["category_type_cb"])
        active, total = db_by_cat.get(key, (0, 0))
        api_total = (sreality_totals or {}).get(key, 0) if sreality_totals else 0
        delta = (active - api_total) if sreality_totals else 0
        delta_pct = (delta / api_total * 100) if sreality_totals and api_total else None
        status = (
            classify_slice_reconciliation(api_total, active, scrape_in_progress=scrape_in_progress)
            if sreality_totals
            else "unknown"
        )
        categories.append(
            CategorySliceComparison(
                name=cat["name"],
                category_main_cb=cat["category_main_cb"],
                category_type_cb=cat["category_type_cb"],
                sreality_api_total=api_total,
                db_active_count=active,
                db_total_count=total,
                delta=delta,
                delta_pct=delta_pct,
                reconciliation_status=status,
            )
        )

    completeness = assess_dataset_completeness(
        session,
        active_total=int(db_active),
        active_slice_count=int(slice_count),
        last_full_sweep=last_full,
    )
    freshness = assess_dataset_freshness(session, running_sweep=running, completeness=completeness)

    run_items_seen = running.items_seen if running else None
    db_vs_run = (int(db_active) - run_items_seen) if run_items_seen is not None else None

    from app.scraping.snapshot_metadata import (
        SLICE_STATUS_LABELS_CS,
        build_snapshot_metadata,
        get_last_dataset_update_at,
        safe_to_compare_with_sreality_total,
    )

    last_update = get_last_dataset_update_at(session, running_sweep=running)
    snapshot_meta = build_snapshot_metadata(
        freshness=freshness,
        running_sweep=running,
        last_full_sweep_at=last_full.finished_at if last_full else None,
        last_dataset_update_at=last_update,
    )

    not_started_count = sum(1 for c in categories if c.reconciliation_status == "not_started")
    coverage_gap_count = sum(1 for c in categories if c.reconciliation_status == "coverage_gap")

    return CountReconciliationReport(
        generated_at=datetime.utcnow(),
        db_active_total=int(db_active),
        db_all_total=int(db_all),
        sreality_api_slice_sum=sum(sreality_totals.values()) if sreality_totals else None,
        active_category_slice_count=int(slice_count),
        expected_category_slice_count=EXPECTED_CATEGORY_SLICES,
        dataset_completeness=completeness,
        dataset_freshness=freshness,
        duplicate_hash_ids=int(dup or 0),
        inventory_sum_matches_active=inv_sum == int(db_active),
        running_scrape=(
            {
                "id": running.id,
                "started_at": running.started_at.isoformat() if running.started_at else None,
                "items_seen": running.items_seen,
                "pages_fetched": running.pages_fetched,
                "items_new": running.items_new,
                "items_removed": running.items_removed,
            }
            if running
            else None
        ),
        run_items_seen=run_items_seen,
        db_vs_run_items_seen_delta=db_vs_run,
        last_full_sweep_run_id=last_full.id if last_full else None,
        last_full_sweep_items_seen=last_full.items_seen if last_full else None,
        last_full_sweep_finished_at=last_full.finished_at if last_full else None,
        partial_or_running_runs=[
            {
                "id": r.id,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
                "items_seen": r.items_seen,
                "pages_fetched": r.pages_fetched,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in partial_runs
        ],
        categories=categories,
        structural_notes=STRUCTURAL_NOTES,
        report_extras={
            "slice_status_labels_cs": SLICE_STATUS_LABELS_CS,
            "not_started_slice_count": not_started_count,
            "coverage_gap_slice_count": coverage_gap_count,
            "global_comparison_safe": safe_to_compare_with_sreality_total(freshness),
            "global_delta_explainable_by_not_started": (
                freshness == "in_progress" and not_started_count > 0 and sreality_totals is not None
            ),
            **snapshot_meta,
        },
    )


async def count_reconciliation_report(session: Session, *, live_sreality: bool = False) -> CountReconciliationReport:
    sreality_totals = await probe_sreality_category_totals() if live_sreality else None
    return build_count_reconciliation_report(session, sreality_totals=sreality_totals)


def count_reconciliation_report_sync(session: Session, *, live_sreality: bool = False) -> CountReconciliationReport:
    return asyncio.run(count_reconciliation_report(session, live_sreality=live_sreality))
