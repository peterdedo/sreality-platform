"""Czech label mappings for sreality's numeric codebook (`_cb`) fields.

None of the four audited source repos (JirkaZelenka/Sreality, Anzywiz/sreality-scraper,
karlosmatos/sreality-scraper, eternalvision/Sreality.cz-Parser) contain a verified
mapping for building_type, building_condition, ownership, energy_efficiency_rating,
or object_kind -- only category_main_cb/category_type_cb/category_sub_cb were ever
translated (in JirkaZelenka/Sreality's config.py). Those three are already covered
in app/scraping/constants.py.

The mappings below come from Sreality's own official XML-RPC import interface
documentation ("Sreality - dokumentace k importnímu rozhraní", Seznam.cz, a.s.),
published at https://admin.sreality.cz/doc/import.pdf (version 4.0.0, platná od
15.6.2015, revised through 14.10.2025). Section 3.1 "Atributy a číselníky inzerátu"
defines these exact codebooks for the same field names (building_type,
building_condition, ownership, energy_efficiency_rating, object_kind) used
internally by sreality.cz -- this is the write-side (agency import) API, but it
describes the canonical Seznam-internal enumeration for these attributes, and the
field names match byte-for-byte what the read-side API returns in
`recommendations_data` (confirmed against JirkaZelenka/Sreality's
scrape_specific_estates(), which reads these same field names from the live API).

Where a code is not covered by this documented codebook, `.get()` on these dicts
returns None and callers should fall back to displaying the raw code rather than
guessing a label.
"""

# building_type_cb -- "Stavba" (§3.1, p.30)
BUILDING_TYPE: dict[int, str] = {
    1: "Dřevostavba",
    2: "Cihlová",
    3: "Kamenná",
    4: "Montovaná",
    5: "Panelová",
    6: "Skeletová",
    7: "Smíšená",
    8: "Modulární",
}

# building_condition_cb -- "Stav objektu" (§3.1, p.30-31)
BUILDING_CONDITION: dict[int, str] = {
    1: "Velmi dobrý",
    2: "Dobrý",
    3: "Špatný",
    4: "Ve výstavbě",
    5: "Projekt",
    6: "Novostavba",
    7: "K demolici",
    8: "Před rekonstrukcí",
    9: "Po rekonstrukci",
    10: "V rekonstrukci",
}

# ownership_cb -- "Vlastnictví" (§3.1, p.31)
OWNERSHIP: dict[int, str] = {
    1: "Osobní",
    2: "Družstevní",
    3: "Státní/obecní",
}

# energy_efficiency_rating_cb -- "Energetická náročnost budovy" (§3.1, p.32-33)
ENERGY_EFFICIENCY_RATING: dict[int, str] = {
    1: "A - Mimořádně úsporná",
    2: "B - Velmi úsporná",
    3: "C - Úsporná",
    4: "D - Méně úsporná",
    5: "E - Nehospodárná",
    6: "F - Velmi nehospodárná",
    7: "G - Mimořádně nehospodárná",
}

# object_kind_cb -- "Poloha domu" (§3.1, p.34)
OBJECT_KIND: dict[int, str] = {
    1: "Řadový",
    2: "Rohový",
    3: "V bloku",
    4: "Samostatný",
}

# furnished_cb -- "Vybavení" (§3.1, p.33)
FURNISHED: dict[int, str] = {
    1: "Ano",
    2: "Ne",
    3: "Částečně",
}

# elevator_cb -- "Výtah" (§3.1, p.32)
ELEVATOR: dict[int, str] = {
    1: "Ano",
    2: "Ne",
}

# energy_performance_certificate_cb is documented (§3.1, p.32: "podle vyhlášky" --
# 1 = č. 148/2007 Sb., 2 = č. 78/2013 Sb., 3 = č. 264/2020 Sb.) but is NOT mapped
# here: it identifies which legal decree an energy certificate was issued under,
# not a listing attribute this scraper currently extracts from the read API's
# recommendations_data payload. Left unmapped rather than guessing a field that
# may not exist in the data we actually scrape.


def _label(codebook: dict[int, str], raw_code: str | int | None) -> str | None:
    """Look up a Czech label for a raw numeric code stored as a string (as
    persisted in ListingDetail). Returns the original raw value unchanged if the
    code isn't in the documented codebook, so an unknown/new code is still visible
    rather than silently dropped."""
    if raw_code is None or raw_code == "":
        return None
    try:
        code_int = int(raw_code)
    except (ValueError, TypeError):
        return str(raw_code)
    return codebook.get(code_int, str(raw_code))


def building_type_label(raw_code: str | int | None) -> str | None:
    return _label(BUILDING_TYPE, raw_code)


def building_condition_label(raw_code: str | int | None) -> str | None:
    return _label(BUILDING_CONDITION, raw_code)


def ownership_label(raw_code: str | int | None) -> str | None:
    return _label(OWNERSHIP, raw_code)


def energy_efficiency_rating_label(raw_code: str | int | None) -> str | None:
    return _label(ENERGY_EFFICIENCY_RATING, raw_code)


def object_kind_label(raw_code: str | int | None) -> str | None:
    return _label(OBJECT_KIND, raw_code)


def furnished_label(raw_code: str | int | None) -> str | None:
    return _label(FURNISHED, raw_code)


def elevator_label(raw_code: str | int | None) -> str | None:
    return _label(ELEVATOR, raw_code)
