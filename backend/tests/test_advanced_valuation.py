"""Floor-fraction parsing (app/domain/floor.py), shared by both the scraper
(to populate real ListingDetail.floor_number/total_floors columns) and the
valuation model's feature engineering (app/analytics/advanced/valuation.py)."""

from app.domain.floor import parse_floor_fraction, parse_floor_number


def test_parse_floor_fraction_normal():
    assert parse_floor_fraction("3/5") == (3, 5)


def test_parse_floor_fraction_ground_floor():
    assert parse_floor_fraction("0/4") == (0, 4)


def test_parse_floor_fraction_negative_basement():
    assert parse_floor_fraction("-1/4") == (-1, 4)


def test_parse_floor_fraction_no_total():
    assert parse_floor_fraction("2") == (2, None)


def test_parse_floor_fraction_none_or_empty():
    assert parse_floor_fraction(None) == (None, None)
    assert parse_floor_fraction("") == (None, None)


def test_parse_floor_fraction_unparseable():
    assert parse_floor_fraction("přízemí") == (None, None)


def test_parse_floor_number_convenience_wrapper():
    assert parse_floor_number("3/5") == 3
    assert parse_floor_number(None) is None
