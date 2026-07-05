export type KpiDirection =
  | "healthy"
  | "stable"
  | "neutral"
  | "watch"
  | "concern"
  | "unavailable"
  | "partial";

/** How meaningfully a KPI can be interpreted right now (see kpi/model.ts). */
export type KpiState =
  | "trend"
  | "baseline"
  | "ingest_dominated"
  | "insufficient_history"
  | "informational";

/** Confidence in reading the value as a real-world signal. */
export type KpiConfidence = "high" | "medium" | "low";

export type KpiInterpretation = {
  /** Co číslo znamená — jedna krátká věta. */
  meaning: string;
  /** Srovnání s referencí, pokud je k dispozici. */
  benchmark?: string;
  direction: KpiDirection;
  directionLabel: string;
  /** Co sledovat dál / další krok. */
  nextStep?: string;
  nextStepLink?: { to: string; label: string };
  /** Omezený vzorek nebo neúplné pokrytí (odvozeno z confidence). */
  limited?: boolean;
  /** Interpretovatelnost KPI — explicitní stav modelu. */
  state?: KpiState;
  /** Míra důvěryhodnosti v hodnotu jako reálný signál. */
  confidence?: KpiConfidence;
};

export type InventoryRegionRow = {
  region: string | null;
  listing_count: number;
};

export type SnapshotDateAggregate = {
  snapshot_date: string;
  listing_count: number;
  new_count: number;
  removed_count: number;
  price_drop_shares: number[];
  median_days: number[];
};
