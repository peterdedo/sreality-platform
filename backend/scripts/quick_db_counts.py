import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.core.db import engine
from app.models import Listing, ScrapingRun
from app.scraping.constants import PROPERTY_TYPES, DEAL_TYPES

with Session(engine) as session:
    active = session.exec(select(func.count()).select_from(Listing).where(Listing.is_active == True)).one()
    total = session.exec(select(func.count()).select_from(Listing)).one()
    runs = session.exec(select(ScrapingRun).order_by(ScrapingRun.id.desc()).limit(8)).all()
    print("=== DB totals ===")
    print(f"active_listings: {active}")
    print(f"total_listings: {total}")
    print("\n=== Recent runs ===")
    for r in runs:
        st = r.status.value if hasattr(r.status, "value") else r.status
        print(f"  #{r.id} {st} seen={r.items_seen} new={r.items_new} removed={r.items_removed} pages={r.pages_fetched}")
    print("\n=== Active by category ===")
    rows = session.exec(
        select(Listing.category_main_cb, Listing.category_type_cb, func.count())
        .where(Listing.is_active == True)
        .group_by(Listing.category_main_cb, Listing.category_type_cb)
        .order_by(Listing.category_main_cb, Listing.category_type_cb)
    ).all()
    for main, deal, cnt in rows:
        print(f"  {PROPERTY_TYPES.get(main,'?')} / {DEAL_TYPES.get(deal,'?')}: {cnt}")
    dup = session.exec(text("SELECT COUNT(*) FROM (SELECT hash_id FROM listing GROUP BY hash_id HAVING COUNT(*)>1) t")).scalar()
    print(f"\nduplicate hash_ids: {dup}")
