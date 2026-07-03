from app.scraping.sreality_url import (
    build_public_listing_url,
    build_public_listing_url_from_fields,
    is_api_source_url,
    resolve_public_source_url,
)


def test_build_public_listing_url_v2_seo_locality():
    estate = {
        "hash_id": 822296156,
        "category_main_cb": 1,
        "category_type_cb": 1,
        "category_sub_cb": 4,
        "seo": {"locality": "praha-praha-4-milevska"},
    }
    assert (
        build_public_listing_url(estate)
        == "https://www.sreality.cz/detail/prodej/byt/2+kk/praha-praha-4-milevska/822296156"
    )


def test_build_public_listing_url_v1_locality_seo_names():
    estate = {
        "hash_id": 2472509516,
        "category_main_cb": {"value": 1},
        "category_type_cb": {"value": 1},
        "category_sub_cb": {"value": 6},
        "advert_name": "Prodej bytu 3+kk 75 m2",
        "locality": {
            "city_seo_name": "praha",
            "citypart_seo_name": "liben",
            "street_seo_name": "v-mezihori",
        },
    }
    assert (
        build_public_listing_url(estate)
        == "https://www.sreality.cz/detail/prodej/byt/3+kk/praha-liben-v-mezihori/2472509516"
    )


def test_build_public_listing_url_fallback_locality_slug():
    estate = {
        "hash_id": 1,
        "category_main_cb": 1,
        "category_type_cb": 2,
        "category_sub_cb": 6,
        "advert_name": "Pronájem bytu 3+kk",
    }
    assert (
        build_public_listing_url(estate)
        == "https://www.sreality.cz/detail/pronajem/byt/3+kk/detail/1"
    )


def test_resolve_public_source_url_upgrades_api_endpoint():
    api_url = "https://www.sreality.cz/api/v1/estates/123456"
    resolved = resolve_public_source_url(
        source_url=api_url,
        hash_id="123456",
        category_main_cb=1,
        category_type_cb=1,
        category_sub_cb=4,
        title="Prodej bytu 2+kk",
    )
    assert resolved is not None
    assert resolved.startswith("https://www.sreality.cz/detail/")
    assert resolved.endswith("/123456")
    assert is_api_source_url(api_url)


def test_resolve_public_source_url_keeps_existing_public_url():
    public = "https://www.sreality.cz/detail/prodej/byt/2+kk/praha/999"
    assert (
        resolve_public_source_url(
            source_url=public,
            hash_id="999",
            category_main_cb=1,
            category_type_cb=1,
        )
        == public
    )


def test_build_public_listing_url_from_fields():
    url = build_public_listing_url_from_fields(
        hash_id="42",
        category_main_cb=2,
        category_type_cb=1,
        category_sub_cb=37,
    )
    assert url == "https://www.sreality.cz/detail/prodej/dum/rodinny/detail/42"
