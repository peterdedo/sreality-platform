import type { MarketDynamicsSnapshot } from "../api/types";
import type { InventoryRegionRow, SnapshotDateAggregate } from "./types";

/** Aggregate market-dynamics rows by snapshot_date (sum across segments). */
export function aggregateSnapshotsByDate(snapshots: MarketDynamicsSnapshot[]): SnapshotDateAggregate[] {
  const byDate = new Map<string, SnapshotDateAggregate>();

  for (const s of snapshots) {
    const key = s.snapshot_date;
    const cur = byDate.get(key) ?? {
      snapshot_date: key,
      listing_count: 0,
      new_count: 0,
      removed_count: 0,
      price_drop_shares: [],
      median_days: [],
    };
    cur.listing_count += s.listing_count;
    cur.new_count += s.new_count;
    cur.removed_count += s.removed_count;
    if (s.price_drop_share != null) cur.price_drop_shares.push(s.price_drop_share);
    if (s.median_days_on_market != null) cur.median_days.push(s.median_days_on_market);
    byDate.set(key, cur);
  }

  return [...byDate.values()].sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
}

export function latestTwoSnapshotDates(
  aggregates: SnapshotDateAggregate[]
): { latest: SnapshotDateAggregate; previous: SnapshotDateAggregate | null } | null {
  if (aggregates.length === 0) return null;
  const latest = aggregates[aggregates.length - 1];
  const previous = aggregates.length >= 2 ? aggregates[aggregates.length - 2] : null;
  return { latest, previous };
}

export function avg(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export function pctChange(current: number, previous: number): number | null {
  if (previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

export function regionalSpread(rows: InventoryRegionRow[]): {
  total: number;
  topRegion: string | null;
  topSharePct: number | null;
  unknownSharePct: number | null;
  maxCount: number;
  minCount: number;
} | null {
  if (rows.length === 0) return null;
  const total = rows.reduce((s, r) => s + r.listing_count, 0);
  if (total === 0) return null;
  const sorted = [...rows].sort((a, b) => b.listing_count - a.listing_count);
  const top = sorted[0];
  const unknown = rows.find((r) => r.region === "Neznámý" || r.region == null);
  return {
    total,
    topRegion: top.region,
    topSharePct: (top.listing_count / total) * 100,
    unknownSharePct: unknown ? (unknown.listing_count / total) * 100 : null,
    maxCount: sorted[0].listing_count,
    minCount: sorted[sorted.length - 1].listing_count,
  };
}
