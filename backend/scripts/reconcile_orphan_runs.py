"""Close scrape runs left in ``running`` after a worker died."""

from sqlmodel import Session

from app.core.db import engine
from app.scraping.orphan_runs import reconcile_orphaned_scrape_runs


def main() -> None:
    with Session(engine) as session:
        closed = reconcile_orphaned_scrape_runs(session)
    if not closed:
        print("No orphaned scrape runs found.")
        return
    print(f"Reconciled {len(closed)} orphaned run(s): {[run.id for run in closed]}")
    for run in closed:
        print(
            f"  run #{run.id}: status={run.status.value}, "
            f"items_seen={run.items_seen}, pages_fetched={run.pages_fetched}"
        )


if __name__ == "__main__":
    main()
