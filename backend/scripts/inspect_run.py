from datetime import datetime, timezone

from sqlmodel import Session, create_engine, select, func

from app.models import ScrapingRun, Listing

engine = create_engine("postgresql+psycopg2://postgres@/sreality?host=/home/peterdeo/verify2/pgdata")
with Session(engine) as session:
    run = session.get(ScrapingRun, 3)
    active = session.exec(select(func.count(Listing.id)).where(Listing.is_active == True)).one()  # noqa: E712
    total = session.exec(select(func.count(Listing.id))).one()
    now = datetime.now(timezone.utc)
    started = run.started_at.replace(tzinfo=timezone.utc) if run.started_at else None
    elapsed = (now - started).total_seconds() if started else None
    print(
        {
            "status": run.status,
            "pages_fetched": run.pages_fetched,
            "items_seen": run.items_seen,
            "items_new": run.items_new,
            "items_updated": run.items_updated,
            "items_removed": run.items_removed,
            "error_count": run.error_count,
            "error_message": run.error_message,
            "started_at": str(run.started_at),
            "finished_at": str(run.finished_at),
            "elapsed_seconds": elapsed,
            "active_listings": active,
            "total_listings": total,
        }
    )
