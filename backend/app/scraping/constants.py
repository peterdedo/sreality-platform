"""Czech category/type code tables, carried over from JirkaZelenka/Sreality's config.py
and extended with karlosmatos' 15-way category x type fan-out list used to bypass
sreality's ~60-page-per-query pagination ceiling."""

# category_type_cb -> Czech label
DEAL_TYPES: dict[int, str] = {
    1: "prodej",
    2: "pronájem",
    3: "dražba",
    4: "prodej podílu",
}

# category_main_cb -> Czech label
PROPERTY_TYPES: dict[int, str] = {
    1: "byt",
    2: "dům",
    3: "pozemek",
    4: "komerční nemovitost a nebytový prostor",
    5: "ostatní",
}

# category_sub_cb -> Czech label (dispozice)
ROOM_LAYOUTS: dict[int, str] = {
    1: "N/A",
    2: "1+kk",
    3: "1+1",
    4: "2+kk",
    5: "2+1",
    6: "3+kk",
    7: "3+1",
    8: "4+kk",
    9: "4+1",
    10: "5+kk",
    11: "5+1",
    12: "6 pokojů a více",
    16: "atypické",
    19: "stavební parcela",
    23: "zahrada",
    33: "chata",
    37: "rodinný",
    39: "vila",
    47: "pronájem pokoje",
}

# category_sub_cb values used to subdivide queries that exceed the API offset
# ceiling (~10 000 results per query). See docs/DATASET_SCOPE.md.
SUBCATEGORIES_BY_MAIN: dict[int, list[int]] = {
    1: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 47],  # byty
    2: [33, 37, 39],  # domy: chata, rodinný, vila
    3: [19, 23],  # pozemky: stavební parcela, zahrada
}

# Czech region ids for locality_region_id fan-out when a category has no
# sub-types but still exceeds the offset ceiling.
CZECH_REGION_IDS: list[int] = list(range(1, 15))

# Full fan-out of category_main_cb x category_type_cb combinations.
# Reused directly from karlosmatos/sreality-scraper's spider CATEGORIES list --
# scraping each combination separately keeps each query's result_size low enough
# to stay under sreality's undocumented page-count ceiling.
# Deal type 4 ("prodej podílu" / share sales) was originally omitted; verified
# live 2026-07-03 it holds ~6.5k listings (6.3k of them pozemky), which was
# exactly the remaining gap between our totals and sreality's homepage counts.
CATEGORY_COMBINATIONS: list[dict] = [
    {"name": f"{PROPERTY_TYPES[main]} - {DEAL_TYPES[deal]}", "category_main_cb": main, "category_type_cb": deal}
    for main in (1, 2, 3, 4, 5)
    for deal in (1, 2, 3, 4)
]

# Czech "items" table label -> ListingDetail field name, from
# JirkaZelenka/Sreality's scrape_specific_estates() item-name matching.
DETAIL_ITEM_FIELD_MAP: dict[str, str] = {
    "Poznámka k ceně": "note_about_price",
    "ID zakázky": "id_of_order",
    "Aktualizace": "last_update",
    "Stavba": "material",
    "Stav objektu": "building_condition",
    "Vlastnictví": "ownership",
    "Podlaží": "floor",
    "Užitná plocha": "usable_area",
    "Plocha podlahová": "floor_area",
    "Plocha pozemku": "land_area",
    "Bezbariérový": "no_barriers",
    "Datum zahájení prodeje": "start_of_offer",
}
