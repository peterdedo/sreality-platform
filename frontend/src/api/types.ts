export interface Listing {
  id: number;
  hash_id: string;
  title: string | null;
  category_main_cb: number;
  category_type_cb: number;
  category_sub_cb: number | null;
  price_czk: number | null;
  price_per_m2: number | null;
  gps_lat: number | null;
  gps_lon: number | null;
  is_active: boolean;
  first_seen_at: string;
  last_seen_at: string;
  last_updated_at: string | null;
  removed_at: string | null;
  source_url: string | null;
  locality_text: string | null;
  seller_type: string | null;

  // from ListingDetail (nullable: not every listing has a detail row yet)
  usable_area: number | null;
  floor_area: number | null;
  land_area: number | null;
  floor: string | null;
  floor_number: number | null;
  total_floors: number | null;
  ownership: string | null;
  building_type: string | null;
  building_condition: string | null;
  energy_efficiency_rating: string | null;
  furnished: string | null;
  elevator: string | null;
  balcony: boolean | null;
  terrace: boolean | null;
  cellar: boolean | null;
  garage: boolean | null;
  garden: boolean | null;
  parking_lots: number | null;

  // from Location (often null -- see docs/METHODOLOGY.md district/region gap)
  region: string | null;
  district: string | null;
  city: string | null;

  // computed at serve time
  days_on_market: number | null;
  price_change_count: number;
  has_price_drop: boolean;
  image_count: number;
  description_length: number | null;
}

export interface MapMarker {
  id: number;
  gps_lat: number;
  gps_lon: number;
  price_czk: number | null;
  title: string | null;
  category_main_cb: number;
  category_type_cb: number;
  source_url: string | null;
}

export interface MapMarkersPage {
  items: MapMarker[];
  total: number;
  truncated: boolean;
}

export interface ListingsPage {
  items: Listing[];
  total: number;
  page: number;
  page_size: number;
}

export interface PriceHistoryPoint {
  price_czk: number;
  recorded_at: string;
}

export interface ListingDetailData {
  listing: Listing;
  description: string | null;
  usable_area: number | null;
  floor_area: number | null;
  floor: string | null;
  ownership: string | null;
  building_type: string | null;
  building_condition: string | null;
  energy_efficiency_rating: string | null;
  furnished: string | null;
  elevator: string | null;
  balcony: boolean | null;
  terrace: boolean | null;
  loggia: boolean | null;
  cellar: boolean | null;
  garage: boolean | null;
  garden: boolean | null;
  parking_lots: number | null;
  broker_company: string | null;
  note_about_price: string | null;
  images: string[];
  price_history: PriceHistoryPoint[];
}

export interface RunItemLog {
  id: number;
  run_id: number;
  hash_id: string | null;
  stage: string;
  message: string;
  created_at: string;
}

export interface ScrapingRun {
  id: number;
  run_type: string;
  category: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  pages_fetched: number;
  items_seen: number;
  items_new: number;
  items_updated: number;
  items_removed: number;
  error_count: number;
  error_message: string | null;
}

export interface PricePerM2Row {
  region: string | null;
  district: string | null;
  municipality: string | null;
  avg_price_czk: number | null;
  avg_price_per_m2: number | null;
  listing_count: number;
}

export interface InventoryRow {
  region: string | null;
  listing_count: number;
}

export interface InventoryByRegionResponse {
  items: InventoryRow[];
  listing_count_sum: number;
  data_scope?: string;
}

export interface NewVsRemoved {
  new_count: number;
  removed_count: number;
  period_days: number;
}

export interface PriceDrop {
  listing_id: number;
  title: string | null;
  previous_price_czk: number;
  current_price_czk: number;
  drop_pct: number;
}

export interface PriceDropsPage {
  items: PriceDrop[];
  total_matched: number | null;
  limit: number | null;
}

export interface DatasetSummary {
  data_scope?: string;
  active_listing_count: number;
  total_listing_count: number;
  active_with_gps_count: number;
  active_with_region_count: number;
  active_with_detail_count: number;
  active_with_valuation_count: number;
  active_with_anomaly_count: number;
  active_without_gps_count: number;
  active_without_region_count: number;
  region_source_counts?: Record<string, number>;
  region_unknown_reason_counts?: Record<string, number>;
  unset_region_source_count?: number;
  inventory_region_listing_sum: number;
  last_successful_scrape_at: string | null;
  last_full_sweep_at?: string | null;
  last_full_sweep_items_seen?: number | null;
  dataset_completeness?: "empty" | "partial" | "complete";
  dataset_freshness?: "empty" | "in_progress" | "final_complete" | "final_partial";
  active_category_slice_count?: number;
  expected_category_slice_count?: number;
  running_scrape?: {
    id: number;
    started_at: string;
    items_seen: number;
    pages_fetched: number;
    items_new: number;
  } | null;
  snapshot_state_label_cs?: string;
  is_count_final?: boolean;
  safe_to_compare_with_sreality_total?: boolean;
  safe_to_compare_per_slice?: boolean;
  compare_guidance_cs?: string;
  last_dataset_update_at?: string | null;
  snapshot_reference_run_id?: number | null;
  schema_revision?: string | null;
  needs_region_backfill?: boolean;
}

export interface PagedRows<T> {
  items: T[];
  total: number;
  limit: number | null;
  offset?: number;
  data_scope?: string;
}

export interface SegmentBreakdownResponse {
  items: SegmentRow[];
  listing_count_sum: number;
  data_scope?: string;
}

export interface ValuationSummary {
  data_scope?: string;
  total_valued_listings: number;
  by_classification: Record<string, number>;
}

export interface AnomalySummary {
  data_scope?: string;
  total_scored_listings: number;
  matching_min_score: number;
  min_score: number;
  flag_counts: Record<string, number>;
}

// --- Pokročilé analýzy (advanced analytics) ---

export interface MarketDynamicsSnapshot {
  id: number;
  snapshot_date: string;
  location_id: number | null;
  category_main_cb: number | null;
  category_type_cb: number | null;
  listing_count: number;
  avg_price_czk: number | null;
  median_price_czk: number | null;
  avg_price_per_m2: number | null;
  new_count: number;
  removed_count: number;
  median_days_on_market: number | null;
  avg_days_on_market: number | null;
  price_drop_share: number | null;
  median_first_to_last_price_change_pct: number | null;
}

export interface SegmentRow {
  value: number | string;
  label: string;
  listing_count: number;
  avg_price_czk: number | null;
  avg_price_per_m2: number | null;
}

export type ValuationClassification = "under_market" | "near_market" | "over_market";
export type ValuationConfidence = "high" | "medium" | "low" | "unavailable";

export interface ListingValuationRow {
  id: number;
  listing_id: number;
  model_id: number | null;
  expected_price_czk: number | null;
  expected_price_per_m2: number | null;
  residual_absolute: number | null;
  residual_percent: number | null;
  classification: ValuationClassification | null;
  confidence: ValuationConfidence;
  computed_at: string;
}

export interface ListingAnomalyRow {
  id: number;
  listing_id: number;
  anomaly_score: number;
  anomaly_flags: string[];
  confidence_score: number;
  computed_at: string;
}

export interface ComparableListing {
  listing_id: number;
  title: string | null;
  price_czk: number | null;
  price_per_m2: number | null;
  distance_km: number;
}

export interface ComparablesResult {
  listing_id: number;
  comparables: ComparableListing[];
  median_comparable_price_czk: number | null;
  median_comparable_price_per_m2: number | null;
  deviation_from_comparables_pct: number | null;
  note: string | null;
}

export interface SpatialGridCell {
  grid_id: string;
  lat_center: number;
  lon_center: number;
  listing_count: number;
  avg_price_per_m2: number | null;
  price_drop_intensity: number | null;
  turnover_rate: number;
}

export interface SpatialHeatmapResponse {
  items: SpatialGridCell[];
  grid_step_degrees: number;
  bbox_applied: boolean;
  cell_count: number;
  aggregated: boolean;
  source: "cache" | "live";
}

export interface AnalyticsRunRow {
  id: number;
  run_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  items_processed: number;
  error_count: number;
  error_message: string | null;
}
