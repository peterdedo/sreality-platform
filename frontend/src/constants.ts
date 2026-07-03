// Mirrors backend/app/scraping/constants.py so filter dropdowns show the same
// Czech labels the scraper uses to classify listings.

export const PROPERTY_TYPES: Record<number, string> = {
  1: "Byt",
  2: "Dům",
  3: "Pozemek",
  4: "Komerční nemovitost",
  5: "Ostatní",
};

export const DEAL_TYPES: Record<number, string> = {
  1: "Prodej",
  2: "Pronájem",
  3: "Dražba",
  4: "Prodej podílu",
};

export const ROOM_LAYOUTS: Record<number, string> = {
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
  16: "Atypické",
};

// Mirrors backend/app/domain/codebooks.py -- same source (Sreality's official
// import interface documentation, §3.1). Keys are the raw codebook values
// (as returned by the API filters, which match ListingDetail's stored strings).
export const OWNERSHIP_LABELS: Record<string, string> = {
  "1": "Osobní",
  "2": "Družstevní",
  "3": "Státní/obecní",
};

export const BUILDING_TYPE_LABELS: Record<string, string> = {
  "1": "Dřevostavba",
  "2": "Cihlová",
  "3": "Kamenná",
  "4": "Montovaná",
  "5": "Panelová",
  "6": "Skeletová",
  "7": "Smíšená",
  "8": "Modulární",
};

export const BUILDING_CONDITION_LABELS: Record<string, string> = {
  "1": "Velmi dobrý",
  "2": "Dobrý",
  "3": "Špatný",
  "4": "Ve výstavbě",
  "5": "Projekt",
  "6": "Novostavba",
  "7": "K demolici",
  "8": "Před rekonstrukcí",
  "9": "Po rekonstrukci",
  "10": "V rekonstrukci",
};

export const ENERGY_EFFICIENCY_RATING_LABELS: Record<string, string> = {
  "1": "A - Mimořádně úsporná",
  "2": "B - Velmi úsporná",
  "3": "C - Úsporná",
  "4": "D - Méně úsporná",
  "5": "E - Nehospodárná",
  "6": "F - Velmi nehospodárná",
  "7": "G - Mimořádně nehospodárná",
};

export const FURNISHED_LABELS: Record<string, string> = {
  "1": "Ano",
  "2": "Ne",
  "3": "Částečně",
};

export const ELEVATOR_LABELS: Record<string, string> = {
  "1": "Ano",
  "2": "Ne",
};

export const SELLER_TYPE_LABELS: Record<string, string> = {
  realitni_kancelar: "Realitní kancelář",
  soukroma_osoba: "Soukromá osoba",
};

export function formatCzk(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("cs-CZ", { style: "currency", currency: "CZK", maximumFractionDigits: 0 }).format(value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("cs-CZ", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

/** For signed values: a directional change/deviation (e.g. residual vs. expected price). */
export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: digits, signDisplay: "exceptZero" }).format(value) + " %";
}

/** For non-negative shares/proportions (e.g. "share of listings with a price drop") -- no +/- sign. */
export function formatPercentPlain(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: digits }).format(value) + " %";
}

// Mirrors backend/app/analytics/advanced/segments.py's ALLOWED_DIMENSIONS.
export const SEGMENT_DIMENSIONS: { value: string; label: string }[] = [
  { value: "category_main_cb", label: "Typ nemovitosti" },
  { value: "category_type_cb", label: "Typ nabídky" },
  { value: "category_sub_cb", label: "Dispozice" },
  { value: "building_condition", label: "Stav budovy" },
  { value: "ownership", label: "Vlastnictví" },
  { value: "energy_efficiency_rating", label: "Energetický štítek" },
  { value: "region", label: "Kraj" },
];

// Mirrors backend/app/models/listing_valuation.py's ValuationClassification/ValuationConfidence.
export const VALUATION_CLASSIFICATION_LABELS: Record<string, string> = {
  under_market: "Pod trhem",
  near_market: "Na úrovni trhu",
  over_market: "Nad trhem",
};

export const VALUATION_CONFIDENCE_LABELS: Record<string, string> = {
  high: "vysoká",
  medium: "střední",
  low: "nízká",
  unavailable: "model nedostupný",
};

// Mirrors backend/app/analytics/advanced/anomaly.py's FLAG_WEIGHTS keys.
export const ANOMALY_FLAG_LABELS: Record<string, string> = {
  extreme_price_per_m2: "Extrémní cena za m²",
  unusual_price_change: "Neobvyklá změna ceny",
  area_layout_mismatch: "Neobvyklý poměr plochy a dispozice",
  stale_listing: "Dlouho na trhu",
  possible_duplicate: "Možný duplicitní inzerát",
};
