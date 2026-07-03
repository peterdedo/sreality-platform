from app.scraping.parser import _extract_leading_int, parse_detail, parse_list_item


def test_parse_list_item_basic():
    raw = {
        "hash_id": 123456,
        "name": "Prodej bytu 2+kk",
        "seo": {"category_main_cb": 1, "category_type_cb": 1, "category_sub_cb": 4, "locality": "praha"},
        "price_czk": {"value_raw": 5000000, "unit": "Kč"},
        "gps": {"lat": 50.08, "lon": 14.43},
        "locality": "Praha 5",
    }

    parsed = parse_list_item(raw)

    assert parsed["hash_id"] == "123456"
    assert parsed["title"] == "Prodej bytu 2+kk"
    assert parsed["category_main_cb"] == 1
    assert parsed["category_type_cb"] == 1
    assert parsed["category_sub_cb"] == 4
    assert parsed["price_czk"] == 5000000
    assert parsed["gps_lat"] == 50.08
    assert parsed["gps_lon"] == 14.43


def test_parse_list_item_missing_fields_defaults():
    raw = {"hash_id": 1, "name": "x", "seo": {}}
    parsed = parse_list_item(raw)
    assert parsed["category_main_cb"] == 0
    assert parsed["category_sub_cb"] is None


def test_extract_leading_int_ignores_digits_in_unit_suffix():
    """Regression test: earlier implementation concatenated every digit found
    anywhere in the string (e.g. "65 m2" -> 652 instead of 65) because a
    trailing unit like "m2" contains a digit of its own."""
    assert _extract_leading_int("65 m2") == 65
    assert _extract_leading_int("65 m²") == 65
    assert _extract_leading_int("120") == 120
    assert _extract_leading_int(None) is None
    assert _extract_leading_int("bez údaje") is None


def test_parse_detail_usable_area_from_czech_item_label():
    payload = {
        "text": {"value": "popis"},
        "recommendations_data": {},
        "_embedded": {"seller": {}},
        "items": [{"name": "Užitná plocha", "value": "65 m2"}],
    }
    detail = parse_detail(payload)
    assert detail["usable_area"] == 65


def test_parse_list_item_current_api_shape():
    raw = {
        "hash_id": 792613708,
        "advert_name": "Prodej bytu 2+kk 53 m2",
        "category_main_cb": {"name": "Byty", "value": 1},
        "category_type_cb": {"name": "Prodej", "value": 1},
        "category_sub_cb": {"name": "2+kk", "value": 4},
        "price_czk": 13307330,
        "locality": {
            "city": "Praha",
            "citypart": "Smíchov",
            "district": "Praha 5",
            "gps_lat": 50.0672,
            "gps_lon": 14.4055,
        },
    }

    parsed = parse_list_item(raw)

    assert parsed["hash_id"] == "792613708"
    assert parsed["title"] == "Prodej bytu 2+kk 53 m2"
    assert parsed["category_main_cb"] == 1
    assert parsed["category_type_cb"] == 1
    assert parsed["category_sub_cb"] == 4
    assert parsed["price_czk"] == 13307330
    assert parsed["gps_lat"] == 50.0672
    assert parsed["gps_lon"] == 14.4055
    assert parsed["locality"] == "Praha 5 - Smíchov"
    assert parsed["source_url"] == "https://www.sreality.cz/detail/prodej/byt/2+kk/detail/792613708"


def test_parse_detail_current_api_shape():
    payload = {
        "result": {
            "advert_description": "popis",
            "meta_description": "meta",
            "furnished": {"name": "Ne", "value": 2},
            "elevator": {"name": "Ano", "value": 1},
            "garden": True,
            "object_kind": {"name": "Byt", "value": 1},
            "building_type": {"name": "Cihlová", "value": 2},
            "building_condition": {"name": "Novostavba", "value": 6},
            "ownership": {"name": "Osobní", "value": 1},
            "parking_lots": 1,
            "terrace": False,
            "balcony": True,
            "loggia": False,
            "basin": False,
            "cellar": True,
            "garage": False,
            "low_energy": False,
            "easy_access": False,
            "energy_efficiency_rating_cb": {"name": "B - Velmi úsporná", "value": 2},
            "premise": {"name": "Test Reality s.r.o."},
            "locality": {
                "district": "Praha 2",
                "district_id": 2,
                "ward_id": 3,
                "region": "Hlavní město Praha",
                "region_id": 4,
                "quarter_id": 5,
                "municipality_id": 6,
                "street_id": 1,
                "gps_lat": 50.08,
                "gps_lon": 14.43,
            },
            "usable_area": 65,
            "floor_area": 65,
            "land_area": 450,
            "floor_number": 3,
            "floors": 5,
            "edited": "2026-07-02",
            "advert_images": [{"url": "//d18-a.sdn.cz/test.jpeg"}],
        }
    }

    detail = parse_detail(payload)
    assert detail["description"] == "popis"
    assert detail["usable_area"] == 65
    assert detail["floor_number"] == 3
    assert detail["total_floors"] == 5
    assert detail["furnished"] == "2"
    assert detail["elevator"] == "1"
    assert detail["broker_company"] == "Test Reality s.r.o."
    assert detail["images"] == ["//d18-a.sdn.cz/test.jpeg"]
    assert detail["location"]["region"] == "Hlavní město Praha"
    assert detail["location"]["district"] == "Praha 2"
