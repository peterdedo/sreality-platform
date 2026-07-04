export type KpiDirection =
  | "healthy"
  | "stable"
  | "neutral"
  | "watch"
  | "concern"
  | "unavailable"
  | "partial";

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
  /** Omezený vzorek nebo neúplné pokrytí. */
  limited?: boolean;
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
