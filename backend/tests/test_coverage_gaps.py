"""Unit tests for coverage_gap parsing and per-category delist eligibility."""

from app.scraping.coverage_gaps import (
    category_delist_plan,
    gap_allows_delist,
    parse_coverage_gap_message,
)


def test_parse_coverage_gap_message_byty():
    gap = parse_coverage_gap_message(
        "byt - prodej: probed_total=22540 recovered=22539 gap=1 (0.0%)"
    )
    assert gap is not None
    assert gap.category_name == "byt - prodej"
    assert gap.probed_total == 22540
    assert gap.recovered == 22539
    assert gap.gap == 1
    assert gap.gap_pct == 0.0
    assert gap.allows_delist is True


def test_parse_coverage_gap_message_domy_blocked():
    gap = parse_coverage_gap_message(
        "dům - prodej: probed_total=22119 recovered=21678 gap=441 (2.0%)"
    )
    assert gap is not None
    assert gap.allows_delist is False


def test_gap_allows_delist_thresholds():
    assert gap_allows_delist(0, 0.0) is True
    assert gap_allows_delist(5, 1.0) is True  # abs cap
    assert gap_allows_delist(6, 0.05) is True  # pct cap
    assert gap_allows_delist(6, 0.06) is False


def test_category_delist_plan_byty_ok_domy_blocked():
    messages = [
        "byt - prodej: probed_total=22540 recovered=22539 gap=1 (0.0%)",
        "dům - prodej: probed_total=22119 recovered=21678 gap=441 (2.0%)",
    ]
    categories = [
        {"name": "byt - prodej", "category_main_cb": 1, "category_type_cb": 1},
        {"name": "dům - prodej", "category_main_cb": 2, "category_type_cb": 1},
        {"name": "byt - pronájem", "category_main_cb": 1, "category_type_cb": 2},
    ]
    to_delist, skipped = category_delist_plan(messages, categories=categories)
    assert {c["name"] for c in to_delist} == {"byt - prodej", "byt - pronájem"}
    assert len(skipped) == 1
    assert skipped[0][0]["name"] == "dům - prodej"
