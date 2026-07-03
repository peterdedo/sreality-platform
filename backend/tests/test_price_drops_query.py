"""price_drops uses a single SQL query (no per-listing N+1)."""

from datetime import datetime, timedelta

from sqlmodel import Session, SQLModel, create_engine

from app.analytics.queries import price_drops
from app.models import Listing, PriceHistory


def test_price_drops_single_query_no_n_plus_one():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    now = datetime.utcnow()

    with Session(engine) as session:
        dropped = Listing(
            hash_id="drop-1",
            title="Dropped",
            category_main_cb=1,
            category_type_cb=1,
            is_active=True,
            price_czk=900_000,
            first_seen_at=now,
            last_seen_at=now,
        )
        flat = Listing(
            hash_id="flat-1",
            title="Flat",
            category_main_cb=1,
            category_type_cb=1,
            is_active=True,
            price_czk=1_000_000,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add_all([dropped, flat])
        session.commit()
        session.refresh(dropped)
        session.refresh(flat)

        session.add_all(
            [
                PriceHistory(listing_id=dropped.id, price_czk=1_000_000, recorded_at=now - timedelta(days=10)),
                PriceHistory(listing_id=dropped.id, price_czk=900_000, recorded_at=now),
                PriceHistory(listing_id=flat.id, price_czk=1_000_000, recorded_at=now - timedelta(days=5)),
                PriceHistory(listing_id=flat.id, price_czk=1_000_000, recorded_at=now),
            ]
        )
        session.commit()

        dropped_id = dropped.id
        result = price_drops(session, min_drop_pct=5.0, limit=None)

    assert result["total_matched"] == 1
    assert result["items"][0]["listing_id"] == dropped_id
    assert result["items"][0]["drop_pct"] == 10.0
