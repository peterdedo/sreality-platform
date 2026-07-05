"""Unit tests for listing location filter helpers."""

from app.api.listing_filters import (
    listing_city_condition,
    listing_district_condition,
    listing_region_condition,
    listing_text_search_condition,
)


def test_listing_text_search_condition_includes_location_fields():
    cond = listing_text_search_condition("Praha")
    sql = str(cond.compile(compile_kwargs={"literal_binds": True}))
    assert "locality_text" in sql
    assert "resolved_region_name" in sql
    assert "region" in sql
    assert "district" in sql
    assert "municipality" in sql
    assert "quarter" in sql


def test_region_condition_matches_locality_text():
    cond = listing_region_condition("Praha")
    sql = str(cond.compile(compile_kwargs={"literal_binds": True}))
    assert "locality_text" in sql


def test_district_condition_matches_quarter_and_locality():
    cond = listing_district_condition("Praha 5")
    sql = str(cond.compile(compile_kwargs={"literal_binds": True}))
    assert "quarter" in sql
    assert "locality_text" in sql


def test_city_condition_matches_district_fallback():
    cond = listing_city_condition("Brno")
    sql = str(cond.compile(compile_kwargs={"literal_binds": True}))
    assert "district" in sql
    assert "locality_text" in sql
