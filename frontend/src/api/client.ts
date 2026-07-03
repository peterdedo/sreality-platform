import type {
  AnalyticsRunRow,
  ComparablesResult,
  DatasetSummary,
  InventoryByRegionResponse,
  ListingAnomalyRow,
  MapMarkersPage,
  MapMarker,
  Listing,
  ListingDetailData,
  ListingValuationRow,
  ListingsPage,
  MarketDynamicsSnapshot,
  NewVsRemoved,
  PagedRows,
  PriceDropsPage,
  PricePerM2Row,
  RunItemLog,
  ScrapingRun,
  SegmentBreakdownResponse,
  SegmentRow,
  SpatialGridCell,
  SpatialHeatmapResponse,
  ValuationSummary,
  AnomalySummary,
} from "./types";

const BASE = "/api";
const REQUEST_TIMEOUT_MS = 15_000;

// Shared API key for guarded (state-changing / heavy) endpoints: scrape
// trigger, analytics recompute, and exports. Read from a build-time Vite env
// var, never hardcoded to a real secret; falls back to the backend's dev
// default so local development needs no setup. Set VITE_API_KEY at build time
// for any non-local deployment.
const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined) ?? "dev-local-key";
const authHeaders: Record<string, string> = { "X-API-Key": API_KEY };

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`Backend neodpovídá do ${Math.round(timeoutMs / 1000)} s. Zkuste to prosím za chvíli znovu.`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetchWithTimeout(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`Požadavek selhal (${res.status}): ${path}`);
  }
  return res.json() as Promise<T>;
}

export interface ListingFilters {
  category_main_cb?: number;
  category_type_cb?: number;
  category_sub_cb?: number;
  price_min?: number;
  price_max?: number;
  price_per_m2_min?: number;
  price_per_m2_max?: number;
  usable_area_min?: number;
  usable_area_max?: number;
  floor_area_min?: number;
  floor_area_max?: number;
  land_area_min?: number;
  land_area_max?: number;
  floor_number_min?: number;
  floor_number_max?: number;
  ownership?: string;
  building_type?: string;
  building_condition?: string;
  energy_efficiency_rating?: string;
  furnished?: string;
  elevator?: string;
  balcony?: boolean;
  terrace?: boolean;
  cellar?: boolean;
  garage?: boolean;
  garden?: boolean;
  has_parking?: boolean;
  region?: string;
  district?: string;
  city?: string;
  seller_type?: string;
  days_on_market_min?: number;
  days_on_market_max?: number;
  has_price_drop?: boolean;
  search?: string;
  is_active?: boolean;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

function toQuery(params: object): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params as Record<string, unknown>)) {
    if (value !== undefined && value !== null && value !== "") {
      usp.set(key, String(value));
    }
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export type ExportFormat = "csv" | "xlsx" | "json" | "parquet";

/** Fetches an export endpoint as a blob and triggers a browser download,
 * using the server-provided filename (Content-Disposition) rather than
 * guessing one client-side. */
async function downloadExport(path: string, params: object): Promise<void> {
  const res = await fetchWithTimeout(`${BASE}${path}${toQuery(params)}`, { headers: authHeaders }, 120_000);
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error(
        "Export selhal (401): neplatný API klíč. Nastavte VITE_API_KEY ve frontend/.env tak, aby odpovídal backend API_KEY (výchozí dev-local-key).",
      );
    }
    throw new Error(`Export selhal (${res.status})`);
  }
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "export";

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Matches backend max_listings_page_size — legacy bulk helper (prefer mapMarkers). */
const LISTINGS_BULK_PAGE_SIZE = 1000;

export const api = {
  listings: (filters: ListingFilters = {}) =>
    getJson<ListingsPage>(`/listings${toQuery(filters)}`),
  mapMarkers: (params: {
    is_active?: boolean;
    south?: number;
    west?: number;
    north?: number;
    east?: number;
    limit?: number;
  } = {}) => getJson<MapMarkersPage>(`/listings/map-markers${toQuery(params)}`),
  listingsAll: async (filters: ListingFilters = {}): Promise<Listing[]> => {
    const pageSize = LISTINGS_BULK_PAGE_SIZE;
    const firstPage = await getJson<ListingsPage>(`/listings${toQuery({ ...filters, page: 1, page_size: pageSize })}`);
    const totalPages = Math.max(1, Math.ceil(firstPage.total / pageSize));
    const all = [...firstPage.items];

    for (let page = 2; page <= totalPages; page += 1) {
      const nextPage = await getJson<ListingsPage>(`/listings${toQuery({ ...filters, page, page_size: pageSize })}`);
      all.push(...nextPage.items);
    }

    return all;
  },
  listingDetail: (id: number) => getJson<ListingDetailData>(`/listings/${id}`),

  pricePerM2: async (categoryMainCb?: number) => {
    const res = await getJson<{ items: PricePerM2Row[] }>(
      `/analytics/price-per-m2${toQuery({ category_main_cb: categoryMainCb })}`
    );
    return res.items;
  },
  priceEvolution: async (listingId?: number, days = 365) => {
    const res = await getJson<{ items: { listing_id: number; price_czk: number; recorded_at: string }[] }>(
      `/analytics/price-evolution${toQuery({ listing_id: listingId, days })}`
    );
    return res.items;
  },
  inventoryByRegion: async () => {
    const res = await getJson<InventoryByRegionResponse>("/analytics/inventory-by-region");
    return res.items;
  },
  datasetSummary: () => getJson<DatasetSummary>("/analytics/dataset-summary"),
  countReconciliation: (live = false) =>
    getJson<Record<string, unknown>>(`/analytics/count-reconciliation${toQuery({ live })}`),
  newVsRemoved: async (days = 30) => {
    const res = await getJson<NewVsRemoved & { data_scope?: string }>(`/analytics/new-vs-removed${toQuery({ days })}`);
    return res;
  },
  priceDrops: (minDropPct = 5, limit?: number, includeTotal = true) =>
    getJson<PriceDropsPage>(
      `/analytics/price-drops${toQuery({ min_drop_pct: minDropPct, limit, include_total: includeTotal })}`
    ),

  scrapingRuns: (limit = 50) => getJson<ScrapingRun[]>(`/scraping/runs${toQuery({ limit })}`),
  reconcileOrphanedRuns: async (): Promise<{ reconciled_count: number; run_ids: number[] }> => {
    const res = await fetchWithTimeout(`${BASE}/scraping/reconcile-orphaned-runs`, { method: "POST", headers: authHeaders });
    if (!res.ok) throw new Error("Uzavření osiřelých běhů selhalo");
    return res.json();
  },
  scrapingRunItems: (runId: number, limit = 200) =>
    getJson<RunItemLog[]>(`/scraping/runs/${runId}/items${toQuery({ limit })}`),
  triggerScraping: async (): Promise<{ message: string }> => {
    const res = await fetchWithTimeout(`${BASE}/scraping/trigger`, { method: "POST", headers: authHeaders });
    if (!res.ok) throw new Error("Spuštění scrapingu selhalo");
    return res.json();
  },
  triggerMissingDetailBackfill: async (): Promise<{ message: string }> => {
    const res = await fetchWithTimeout(`${BASE}/scraping/backfill-missing-details`, { method: "POST", headers: authHeaders });
    if (!res.ok) throw new Error("Spuštění doplnění detailů selhalo");
    return res.json();
  },

  advanced: {
    marketDynamics: async (days = 180, categoryMainCb?: number, categoryTypeCb?: number) => {
      const res = await getJson<{ items: MarketDynamicsSnapshot[] }>(
        `/analytics/advanced/market-dynamics${toQuery({ days, category_main_cb: categoryMainCb, category_type_cb: categoryTypeCb })}`
      );
      return res.items;
    },
    segments: async (dimension: string, categoryMainCb?: number) => {
      const res = await getJson<SegmentBreakdownResponse>(
        `/analytics/advanced/segments${toQuery({ dimension, category_main_cb: categoryMainCb })}`
      );
      return res.items;
    },
    valuationSummary: () => getJson<ValuationSummary>("/analytics/advanced/valuation/summary"),
    valuationList: (classification?: string, minConfidence?: string, limit?: number, offset?: number) =>
      getJson<PagedRows<ListingValuationRow>>(
        `/analytics/advanced/valuation${toQuery({ classification, min_confidence: minConfidence, limit, offset })}`
      ),
    valuationDetail: (listingId: number) => getJson<ListingValuationRow>(`/analytics/advanced/valuation/${listingId}`),
    anomalySummary: (minScore = 0) =>
      getJson<AnomalySummary>(`/analytics/advanced/anomalies/summary${toQuery({ min_score: minScore })}`),
    anomalies: (minScore = 0, flag?: string, limit?: number, offset?: number) =>
      getJson<PagedRows<ListingAnomalyRow>>(
        `/analytics/advanced/anomalies${toQuery({ min_score: minScore, flag, limit, offset })}`
      ),
    comparables: (listingId: number, limit = 8) =>
      getJson<ComparablesResult>(`/analytics/advanced/comparables/${listingId}${toQuery({ limit })}`),
    spatialHeatmap: async (params: {
      categoryMainCb?: number;
      categoryTypeCb?: number;
      south?: number;
      west?: number;
      north?: number;
      east?: number;
      zoom?: number;
    } = {}) => {
      const { categoryMainCb, categoryTypeCb, south, west, north, east, zoom } = params;
      const res = await getJson<SpatialHeatmapResponse & { items: SpatialGridCell[] }>(
        `/analytics/advanced/spatial/heatmap${toQuery({
          category_main_cb: categoryMainCb,
          category_type_cb: categoryTypeCb,
          south,
          west,
          north,
          east,
          zoom,
        })}`
      );
      const hasBbox = south != null && west != null && north != null && east != null;
      return {
        items: res.items,
        grid_step_degrees: res.grid_step_degrees ?? 0.01,
        bbox_applied: res.bbox_applied ?? hasBbox,
        cell_count: res.cell_count ?? res.items.length,
        aggregated: res.aggregated ?? false,
        source: res.source ?? "live",
      } satisfies SpatialHeatmapResponse;
    },
    runs: (limit = 50) => getJson<AnalyticsRunRow[]>(`/analytics/advanced/runs${toQuery({ limit })}`),
    triggerRecompute: async (): Promise<{ message: string }> => {
      const res = await fetchWithTimeout(`${BASE}/analytics/advanced/recompute`, { method: "POST", headers: authHeaders });
      if (!res.ok) throw new Error("Spuštění přepočtu selhalo");
      return res.json();
    },
  },

  export: {
    listings: (scope: "raw" | "cleaned", format: ExportFormat, filters: ListingFilters = {}) =>
      downloadExport("/export/listings", { ...filters, scope, format }),
    timeseries: (
      format: ExportFormat,
      params: { days?: number; category_main_cb?: number; category_type_cb?: number; location_id?: number } = {}
    ) => downloadExport("/export/analytics/timeseries", { ...params, format }),
    valuation: (format: ExportFormat, params: { classification?: string; min_score?: number; limit?: number } = {}) =>
      downloadExport("/export/analytics/valuation", { ...params, format }),
  },
};
