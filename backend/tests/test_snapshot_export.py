"""Tests for immutable byty/prodej snapshot CSV + manifest."""

from datetime import datetime

from sqlmodel import Session, SQLModel, create_engine

from app.models import Listing
from app.scraping.snapshot_export import build_byty_prodej_snapshot


def test_byty_prodej_snapshot_checksum_stable_for_same_rows():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    now = datetime.utcnow()
    with Session(engine) as session:
        session.add(
            Listing(
                hash_id="100",
                title="A",
                category_main_cb=1,
                category_type_cb=1,
                price_czk=1_000_000,
                price_czk_unit="Kč",
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
        )
        session.add(
            Listing(
                hash_id="200",
                title="B",
                category_main_cb=1,
                category_type_cb=1,
                price_czk=2_000_000,
                price_czk_unit=None,
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
        )
        # Different category — must be excluded.
        session.add(
            Listing(
                hash_id="300",
                title="C",
                category_main_cb=2,
                category_type_cb=1,
                price_czk=3_000_000,
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
        )
        session.commit()

        csv1, manifest1 = build_byty_prodej_snapshot(session)
        csv2, manifest2 = build_byty_prodej_snapshot(session)

    assert manifest1["row_count"] == 2
    assert manifest1["price_czk_unit_populated"] == 1
    assert manifest1["price_czk_unit_missing"] == 1
    assert manifest1["price_czk_unit_counts"]["Kč"] == 1
    assert manifest1["price_czk_unit_counts"]["(missing)"] == 1
    assert manifest1["sha256"] == manifest2["sha256"]
    assert csv1 == csv2
    assert len(manifest1["sha256"]) == 64


def test_snapshot_keeps_foreign_currency_distinct_from_czk():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    now = datetime.utcnow()
    with Session(engine) as session:
        session.add(
            Listing(
                hash_id="eur1",
                title="EUR listing",
                category_main_cb=1,
                category_type_cb=1,
                price_czk=250_000,
                price_czk_unit="EUR",
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
        )
        session.add(
            Listing(
                hash_id="czk1",
                title="CZK listing",
                category_main_cb=1,
                category_type_cb=1,
                price_czk=5_000_000,
                price_czk_unit="Kč",
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
        )
        session.commit()
        _csv, manifest = build_byty_prodej_snapshot(session)

    assert manifest["price_czk_unit_counts"]["EUR"] == 1
    assert manifest["price_czk_unit_counts"]["Kč"] == 1
    assert manifest["price_czk_unit_non_czk_counts"] == {"EUR": 1}
