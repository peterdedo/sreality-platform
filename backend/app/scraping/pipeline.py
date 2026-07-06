"""Scraping orchestrator: validate -> deduplicate -> diff-against-db (incremental)
-> persist -> snapshot-price -> detail-backfill.

Stage shape is carried over from karlosmatos/sreality-scraper's Scrapy pipeline
chain (ValidationPipeline -> DeduplicationPipeline -> CountVerificationPipeline
-> export), reimplemented as plain async functions since this project doesn't
use Scrapy. Incremental diff logic (new vs existing vs removed) is carried over
from JirkaZelenka/Sreality's Runner.scrape_prices_and_details(), which was the
only source repo with real incremental-update behavior.
"""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Listing, ListingDetail, Location, PriceHistory, RawPayload, RunItemLog, ScrapingRun
from app.models.run_item_log import IngestStage
from app.models.scraping_run import RunStatus, RunType
from app.scraping.client import SrealityClient
from app.scraping.constants import CATEGORY_COMBINATIONS, CZECH_REGION_IDS, SUBCATEGORIES_BY_MAIN
from app.scraping.parser import parse_detail, parse_list_item
from app.scraping.region_backfill import resolve_listing_region
from app.scraping.sreality_url import build_public_listing_url
from app.scraping.locks import BACKFILL_LOCK_ID, SWEEP_LOCK_ID
from app.scraping.orphan_runs import register_active_run, unregister_active_run

logger = logging.getLogger(__name__)

# Postgres session-level advisory locks guarding against two concurrent
# sweeps/backfills corrupting ground truth (see the incident this fixes:
# a stale process's sweep marked 14 389 fresh listings as removed while a
# second sweep was mid-run against the same DB). Session-level locks are
# automatically released if the holding connection dies -- e.g. a crashed or
# killed backend -- so this also closes the "stale backend" risk without a
# manual staleness timeout heuristic. Arbitrary but fixed 64-bit ids, distinct
# per lock so a sweep and a backfill can still run concurrently (they don't
# race on the same invariant -- delisting only happens in the sweep).


def _try_acquire_lock(session: Session, lock_id: int) -> bool:
    return bool(session.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar())


def _release_lock(session: Session, lock_id: int) -> None:
    session.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})


async def _fetch_search_query(
    client: SrealityClient,
    query_params: str,
    session: Session,
    run: ScrapingRun,
    category_label: str,
) -> tuple[list[dict], int]:
    """Fetch all result pages for one search query using offset pagination."""
    per_page = min(settings.scrape_per_page, 100)
    base = f"{settings.sreality_api_base}?{query_params}"

    first_page = await client.get_json(f"{base}&per_page={per_page}&offset=0")
    pagination = first_page.get("pagination", {}) or {}
    total_results = int(pagination.get("total") or len(first_page.get("results", [])) or 0)
    if not total_results:
        return [], 0

    estates: list[dict] = list(first_page.get("results", []))
    pages_fetched = 1
    offset = len(estates)

    # The API rejects offset >= 10 000 with 422 (hard upstream ceiling, observed
    # live). Queries whose total exceeds the cap must be subdivided by the
    # caller (see _fetch_category_estates' recursive fan-out); stopping here
    # keeps an over-cap query from spamming 422s into RunItemLog.
    if total_results > settings.scrape_offset_cap:
        logger.warning(
            "Query %s has %d results, above the %d offset ceiling -- tail is unreachable at this granularity",
            category_label, total_results, settings.scrape_offset_cap,
        )
    while offset < min(total_results, settings.scrape_offset_cap):
        url = f"{base}&per_page={per_page}&offset={offset}"
        try:
            data = await client.get_json(url)
        except Exception as exc:
            logger.error("Giving up on %s offset %d after retries", category_label, offset)
            run.error_count += 1
            _log_item_failure(
                session, run.id, f"{category_label}:offset{offset}", IngestStage.page_fetch, str(exc)
            )
            break

        batch = data.get("results", [])
        if not batch:
            break
        estates.extend(batch)
        pages_fetched += 1
        offset += len(batch)

    return estates, pages_fetched


async def _probe_search_total(client: SrealityClient, query_params: str) -> int:
    per_page = min(settings.scrape_per_page, 100)
    url = f"{settings.sreality_api_base}?{query_params}&per_page={per_page}&offset=0"
    data = await client.get_json(url)
    pagination = data.get("pagination", {}) or {}
    return int(pagination.get("total") or len(data.get("results", [])) or 0)


def _fanout_queries(category: dict) -> list[tuple[str, str]]:
    """Return (label, query_params) slices for one category combination."""
    base = f"category_main_cb={category['category_main_cb']}&category_type_cb={category['category_type_cb']}"
    return [(category["name"], base)]


async def _fetch_category_estates(
    client: SrealityClient, category: dict, session: Session, run: ScrapingRun
) -> tuple[list[dict], int]:
    """Fetch all listings for one category_main_cb x category_type_cb combination.

    Uses offset pagination (``page`` repeats the same rows on sreality.cz).
    The API hard-caps offsets at ~10 000 rows per query, so any query whose
    total exceeds ``scrape_offset_cap`` is subdivided along **both** region
    and subcategory and the results are unioned by hash_id. Neither dimension
    alone is reliably complete -- verified live against the real API:

    - region-only fan-out (14 Czech regions) undercounts byty/prodej by
      ~10.5% (20 013 probed vs 17 915 summed across regions): some listings
      have no resolvable locality_region_id and fall out of every region
      slice, and ``locality_region_id=0`` is not a "no region" bucket (the
      API just ignores it and returns the unfiltered total).
    - subcategory-only fan-out is complete for byty (13 known sub codes sum
      to exactly the probed total) but SUBCATEGORIES_BY_MAIN's curated lists
      are NOT exhaustive for domy/pozemky/komerční (e.g. domy: 19 501 of
      21 836 known -- 89%), and komerční has no documented sub codes at all.

    Combining both dimensions and unioning by hash_id closed domy/prodej's
    gap from 4 930 missing (region-only) down to 291 (98.7% coverage) in a
    live test.

    Third level: an individual subcategory slice can itself exceed the offset
    cap (rodinné domy / sub 37 alone: 16 143 results). Each sub-slice's own
    total is probed, and any over-cap sub is additionally split by region
    (same 14-region list, unioned by hash_id like the top level) instead of
    being fetched as a single truncated-at-the-cap query. This is applied
    per-sub, not as a blanket third fan-out level, so categories with no
    over-cap sub (e.g. byty) pay only the cost of 13 extra probe calls, not
    extra fetch queries.

    Verified live that sub×region has the same structural limit as
    region-only: sub 37 alone, summed across all 14 regions, recovers
    15 725/16 143 (97.4%) -- a ~2.6% residual of listings with no resolvable
    locality_region_id remains unreachable by *any* region-based split, at
    any fan-out depth. This is not a code bug to fix further; it's persisted
    via the same coverage_gap mechanism rather than hidden.
    """
    base_params = _fanout_queries(category)[0][1]
    probe_total = await _probe_search_total(client, base_params)

    if probe_total <= settings.scrape_offset_cap:
        queries = [(category["name"], base_params)]
    else:
        queries = [
            (f"{category['name']} / region {region_id}", f"{base_params}&locality_region_id={region_id}")
            for region_id in CZECH_REGION_IDS
        ]
        subs = SUBCATEGORIES_BY_MAIN.get(category["category_main_cb"]) or []
        for sub in subs:
            sub_params = f"{base_params}&category_sub_cb={sub}"
            sub_label = f"{category['name']} / sub {sub}"
            sub_total = await _probe_search_total(client, sub_params)
            if sub_total > settings.scrape_offset_cap:
                # Third-level fan-out: this specific sub-slice is itself over
                # the offset cap, so a single query for it would silently
                # truncate at scrape_offset_cap regardless of the top-level
                # region split (which doesn't filter by sub_cb).
                queries += [
                    (f"{sub_label} / region {region_id}", f"{sub_params}&locality_region_id={region_id}")
                    for region_id in CZECH_REGION_IDS
                ]
            else:
                queries.append((sub_label, sub_params))

    estates_by_hash: dict[str, dict] = {}
    pages_fetched = 0
    for label, query_params in queries:
        batch, pages = await _fetch_search_query(client, query_params, session, run, label)
        pages_fetched += pages
        for item in batch:
            hash_id = str(item.get("hash_id"))
            estates_by_hash.setdefault(hash_id, item)

    if probe_total > 0:
        gap = probe_total - len(estates_by_hash)
        if gap > 0:
            gap_pct = gap / probe_total * 100
            logger.warning(
                "%s: fan-out recovered %d/%d listings (%.1f%% missing)",
                category["name"], len(estates_by_hash), probe_total, gap_pct,
            )
            # Counted in error_count (not just logged) so it surfaces through
            # the same "N chyb / Zobrazit chyby" admin-panel affordance as
            # hard failures -- a coverage shortfall is a data-completeness
            # problem the operator needs to see, not only a code exception.
            run.error_count += 1
            _log_item_failure(
                session,
                run.id,
                None,
                IngestStage.coverage_gap,
                f"{category['name']}: probed_total={probe_total} recovered={len(estates_by_hash)} "
                f"gap={gap} ({gap_pct:.1f}%)",
            )

    return list(estates_by_hash.values()), pages_fetched


def _validate(raw_item: dict) -> bool:
    return bool(raw_item.get("hash_id")) and bool(raw_item.get("name") or raw_item.get("advert_name"))


def _log_item_failure(session: Session, run_id: int, hash_id: str | None, stage: IngestStage, message: str) -> None:
    """Persists the specific hash_id/reason for a per-item failure, so it survives
    past the run (previously only ScrapingRun.error_count was incremented and the
    detail was discarded -- see RunItemLog's docstring)."""
    session.add(RunItemLog(run_id=run_id, hash_id=hash_id, stage=stage, message=message[:2000]))


async def run_incremental_scrape(session: Session, categories: list[dict] | None = None) -> ScrapingRun:
    """Fetch current listings for the given categories (default: all 15 combinations),
    diff against the DB, persist new/changed listings, snapshot price changes, and
    mark listings absent from this sweep as removed (delisting detection -- a
    capability absent from all four audited repos)."""

    categories = categories or CATEGORY_COMBINATIONS
    run = ScrapingRun(run_type=RunType.incremental, category="all" if categories == CATEGORY_COMBINATIONS else categories[0]["name"])
    session.add(run)
    session.commit()
    session.refresh(run)

    if not _try_acquire_lock(session, SWEEP_LOCK_ID):
        # Another sweep already holds the lock (same process re-triggered, or
        # -- the original incident this guards against -- a second backend
        # process). Refuse rather than run two sweeps' delisting logic
        # against the same DB concurrently.
        logger.warning("Sweep lock held by another run; skipping this trigger")
        run.status = RunStatus.failed
        run.error_message = "Jiný scraping sweep již běží (advisory lock); tento pokus byl přeskočen."
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    register_active_run(run.id)
    client = SrealityClient()
    seen_hash_ids: set[str] = set()
    new_listing_ids: list[int] = []

    try:
        for category in categories:
            raw_estates, pages = await _fetch_category_estates(client, category, session, run)
            run.pages_fetched += pages

            for raw in raw_estates:
                if not _validate(raw):
                    run.error_count += 1
                    _log_item_failure(
                        session,
                        run.id,
                        raw.get("hash_id"),
                        IngestStage.validate,
                        f"Missing required field(s) (hash_id={raw.get('hash_id')!r}, name={raw.get('name')!r})",
                    )
                    continue

                parsed = parse_list_item(raw)
                hash_id = parsed["hash_id"]
                if hash_id in seen_hash_ids:
                    continue
                seen_hash_ids.add(hash_id)
                run.items_seen += 1

                existing = session.exec(select(Listing).where(Listing.hash_id == hash_id)).first()
                if existing is None:
                    session.add(RawPayload(hash_id=hash_id, payload_type="list", payload=raw))
                now = datetime.utcnow()

                if existing is None:
                    listing = Listing(
                        hash_id=hash_id,
                        title=parsed["title"],
                        category_main_cb=parsed["category_main_cb"],
                        category_type_cb=parsed["category_type_cb"],
                        category_sub_cb=parsed["category_sub_cb"],
                        price_czk=parsed["price_czk"],
                        price_czk_unit=parsed["price_czk_unit"],
                        gps_lat=parsed["gps_lat"],
                        gps_lon=parsed["gps_lon"],
                        locality_text=parsed["locality"],
                        source_url=parsed["source_url"],
                        first_seen_at=now,
                        last_seen_at=now,
                        is_active=True,
                    )
                    session.add(listing)
                    session.commit()
                    session.refresh(listing)
                    resolve_listing_region(session, listing)
                    session.commit()

                    if parsed["price_czk"]:
                        session.add(PriceHistory(listing_id=listing.id, price_czk=parsed["price_czk"], recorded_at=now))

                    run.items_new += 1
                    new_listing_ids.append(listing.id)
                else:
                    existing.last_seen_at = now
                    existing.is_active = True
                    existing.removed_at = None
                    if parsed.get("source_url"):
                        existing.source_url = parsed["source_url"]
                    if parsed["price_czk"] and parsed["price_czk"] != existing.price_czk:
                        session.add(PriceHistory(listing_id=existing.id, price_czk=parsed["price_czk"], recorded_at=now))
                        existing.price_czk = parsed["price_czk"]
                        run.items_updated += 1
                    if parsed.get("gps_lat") is not None:
                        existing.gps_lat = parsed["gps_lat"]
                    if parsed.get("gps_lon") is not None:
                        existing.gps_lon = parsed["gps_lon"]
                    resolve_listing_region(session, existing)
                    session.add(existing)

                session.commit()

        # Delisting detection: any active listing in these categories not seen in
        # this sweep is marked removed. Only safe to run when scraping *all*
        # categories in one pass (partial category runs would falsely flag others).
        if categories == CATEGORY_COMBINATIONS:
            active_listings = session.exec(select(Listing).where(Listing.is_active == True)).all()  # noqa: E712
            for listing in active_listings:
                if listing.hash_id not in seen_hash_ids:
                    listing.is_active = False
                    listing.removed_at = datetime.utcnow()
                    session.add(listing)
                    run.items_removed += 1
            session.commit()

        run.status = RunStatus.success
    except Exception as exc:
        logger.exception("Scraping run failed")
        run.status = RunStatus.failed
        run.error_message = str(exc)
    finally:
        unregister_active_run(run.id)
        await client.aclose()
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        _release_lock(session, SWEEP_LOCK_ID)

    if new_listing_ids:
        await run_detail_backfill(session, new_listing_ids)

    return run


async def run_detail_backfill(session: Session, listing_ids: list[int]) -> ScrapingRun:
    """Fetch full detail payloads for listings that don't have a ListingDetail yet
    (new listings from an incremental run, or any previously-missed ids)."""

    run = ScrapingRun(run_type=RunType.detail_backfill)
    session.add(run)
    session.commit()
    session.refresh(run)

    if not _try_acquire_lock(session, BACKFILL_LOCK_ID):
        logger.warning("Backfill lock held by another run; skipping this trigger")
        run.status = RunStatus.failed
        run.error_message = "Jiné doplnění detailů již běží (advisory lock); tento pokus byl přeskočen."
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    register_active_run(run.id)
    client = SrealityClient()
    try:
        for listing_id in listing_ids:
            listing = session.get(Listing, listing_id)
            if listing is None:
                continue

            url = f"{settings.sreality_detail_base}/{listing.hash_id}"
            try:
                payload = await client.get_json(url)
            except Exception as exc:
                run.error_count += 1
                _log_item_failure(session, run.id, listing.hash_id, IngestStage.detail_fetch, str(exc))
                continue

            # Everything touching this one listing's payload is isolated in
            # its own try/except: previously a single malformed payload (e.g.
            # an unexpected field shape from parse_detail, or a URL-build
            # failure) would raise past this loop and abort the ENTIRE
            # backfill run for every remaining listing_id, not just this one
            # -- see RunItemLog's docstring.
            try:
                session.add(RawPayload(listing_id=listing.id, hash_id=listing.hash_id, payload_type="detail", payload=payload))

                detail_raw = payload.get("result", payload) or {}
                public_url = build_public_listing_url(detail_raw)
                if public_url:
                    listing.source_url = public_url
                    session.add(listing)

                parsed = parse_detail(payload)
                location_fields = parsed.pop("location", {})
                images = parsed.pop("images", [])

                if any(location_fields.values()):
                    location = Location(**location_fields)
                    session.add(location)
                    session.commit()
                    session.refresh(location)
                    listing.location_id = location.id
                    session.add(listing)

                # seller_type is a heuristic, not a confirmed API field: sreality's
                # read API doesn't expose an explicit private-seller/agency flag we've
                # found, so this is inferred from whether a broker_company was
                # returned. See app/models/listing.py's docstring.
                listing.seller_type = "realitni_kancelar" if parsed.get("broker_company") else "soukroma_osoba"
                session.add(listing)

                detail = ListingDetail(listing_id=listing.id, **parsed)
                session.add(detail)

                from app.models import Image
                for position, image_url in enumerate(images):
                    session.add(Image(listing_id=listing.id, url=image_url, position=position))

                resolve_listing_region(session, listing)

                session.commit()
                run.items_seen += 1
            except Exception as exc:
                session.rollback()
                run.error_count += 1
                _log_item_failure(session, run.id, listing.hash_id, IngestStage.parse, str(exc))

        # Every per-item failure is caught above and continues the loop, so
        # reaching here only means "no top-level exception" -- it does NOT
        # mean every item succeeded. Classify honestly instead of always
        # reporting success: if nothing failed it's a clean success; if some
        # items succeeded and some failed it's partial (the operator needs to
        # know some details are still missing); if everything failed (e.g. the
        # upstream API was down for the whole run) it's failed, not success.
        if run.error_count == 0:
            run.status = RunStatus.success
        elif run.items_seen > 0:
            run.status = RunStatus.partial
            run.error_message = (
                f"{run.error_count} z {run.items_seen + run.error_count} položek selhalo; "
                "opětovné spuštění doplní jen ty, které ještě nemají detail."
            )
        else:
            run.status = RunStatus.failed
            run.error_message = f"Všech {run.error_count} položek selhalo."
    except Exception as exc:
        logger.exception("Detail backfill failed")
        run.status = RunStatus.failed
        run.error_message = str(exc)
    finally:
        unregister_active_run(run.id)
        await client.aclose()
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        _release_lock(session, BACKFILL_LOCK_ID)

    return run


async def run_missing_detail_backfill(session: Session) -> ScrapingRun:
    """Backfill ListingDetail for every currently-active listing that doesn't
    have one yet, regardless of when it was first seen. This is the same
    operation an operator previously had to run as an ad hoc script outside
    the deployed app; promoted into the codebase so it's resumable (re-running
    just re-selects whatever's still missing -- naturally idempotent, no
    special-cased dedup needed) and safe to trigger from an endpoint or a
    schedule instead of only by hand. Reuses run_detail_backfill, so it's
    covered by the same advisory lock against concurrent backfills.
    """
    listing_ids = session.exec(
        select(Listing.id)
        .join(ListingDetail, ListingDetail.listing_id == Listing.id, isouter=True)
        .where(ListingDetail.id.is_(None), Listing.is_active == True)  # noqa: E712
    ).all()
    logger.info("Missing-detail backfill: %d active listings without a detail row", len(listing_ids))
    return await run_detail_backfill(session, list(listing_ids))
