"""Tests for the sreality codebook translations (app/domain/codebooks.py).

Values are cross-checked against Sreality's own official XML-RPC import
interface documentation (docs/sreality_import_specification.pdf, section 3.1),
not invented.
"""

from app.domain import codebooks


def test_building_type_known_codes():
    assert codebooks.building_type_label(1) == "Dřevostavba"
    assert codebooks.building_type_label("2") == "Cihlová"
    assert codebooks.building_type_label(5) == "Panelová"
    assert codebooks.building_type_label(8) == "Modulární"


def test_building_condition_known_codes():
    assert codebooks.building_condition_label(1) == "Velmi dobrý"
    assert codebooks.building_condition_label("6") == "Novostavba"
    assert codebooks.building_condition_label(10) == "V rekonstrukci"


def test_ownership_known_codes():
    assert codebooks.ownership_label(1) == "Osobní"
    assert codebooks.ownership_label("2") == "Družstevní"
    assert codebooks.ownership_label(3) == "Státní/obecní"


def test_energy_efficiency_rating_known_codes():
    assert codebooks.energy_efficiency_rating_label(1) == "A - Mimořádně úsporná"
    assert codebooks.energy_efficiency_rating_label("7") == "G - Mimořádně nehospodárná"


def test_object_kind_known_codes():
    assert codebooks.object_kind_label(1) == "Řadový"
    assert codebooks.object_kind_label(4) == "Samostatný"


def test_furnished_known_codes():
    assert codebooks.furnished_label(1) == "Ano"
    assert codebooks.furnished_label("2") == "Ne"
    assert codebooks.furnished_label(3) == "Částečně"


def test_elevator_known_codes():
    assert codebooks.elevator_label(1) == "Ano"
    assert codebooks.elevator_label("2") == "Ne"


def test_unknown_code_falls_back_to_raw_value_not_none():
    """An undocumented/new code should stay visible as its raw value rather
    than silently disappear or raise."""
    assert codebooks.building_type_label(999) == "999"
    assert codebooks.ownership_label("42") == "42"


def test_empty_or_none_code_returns_none():
    assert codebooks.building_type_label(None) is None
    assert codebooks.ownership_label("") is None


def test_non_numeric_code_returns_raw_string():
    assert codebooks.building_condition_label("neznámý") == "neznámý"
