import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Listing, Location, RawPayload
from app.scraping.location_backfill import backfill_location_names


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_backfill_location_names_from_stored_detail_payload(session: Session):
    location = Location(
        locality_region_id=4,
        locality_district_id=2,
        gps_lat=50.08,
        gps_lon=14.43,
    )
    session.add(location)
    session.commit()
    session.refresh(location)

    listing = Listing(
        hash_id="123456",
        title="Test",
        category_main_cb=1,
        category_type_cb=1,
        location_id=location.id,
        is_active=True,
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)

    session.add(
        RawPayload(
            listing_id=listing.id,
            hash_id=listing.hash_id,
            payload_type="detail",
            payload={
                "result": {
                    "locality": {
                        "region": "Hlavní město Praha",
                        "district": "Praha 2",
                        "city": "Praha",
                        "citypart": "Vinohrady",
                        "region_id": 4,
                        "district_id": 2,
                        "gps_lat": 50.08,
                        "gps_lon": 14.43,
                    }
                }
            },
        )
    )
    session.commit()

    result = backfill_location_names(session)
    session.refresh(location)

    assert result == {"updated": 1, "skipped": 0}
    assert location.region == "Hlavní město Praha"
    assert location.district == "Praha 2"
    assert location.municipality == "Praha"
    assert location.quarter == "Vinohrady"


def test_backfill_location_names_falls_back_to_list_payload(session: Session):
    location = Location(locality_region_id=3, gps_lat=50.22, gps_lon=12.88)
    session.add(location)
    session.commit()
    session.refresh(location)

    listing = Listing(
        hash_id="999",
        title="Test",
        category_main_cb=1,
        category_type_cb=1,
        location_id=location.id,
        is_active=True,
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)

    session.add(
        RawPayload(
            hash_id=listing.hash_id,
            payload_type="list",
            payload={
                "locality": {
                    "region": "Karlovarský kraj",
                    "district": "Karlovy Vary",
                    "city": "Karlovy Vary",
                }
            },
        )
    )
    session.commit()

    result = backfill_location_names(session)
    session.refresh(location)

    assert result == {"updated": 1, "skipped": 0}
    assert location.region == "Karlovarský kraj"
    assert location.district == "Karlovy Vary"
    assert location.municipality == "Karlovy Vary"
