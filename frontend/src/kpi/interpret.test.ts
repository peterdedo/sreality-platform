import { describe, expect, it } from "vitest";
import type { DatasetSummary, MarketDynamicsSnapshot } from "../api/types";
import { cs } from "../locale/cs";
import type { InventoryRegionRow } from "./types";
import {
  interpretActiveListings,
  interpretAdvancedMetric,
  interpretDetailCoverage,
  interpretNewListings30,
  interpretRegionalInventory,
  interpretRemovedListings30,
} from "./interpret";

function snap(overrides: Partial<MarketDynamicsSnapshot>): MarketDynamicsSnapshot {
  return {
    id: 1,
    snapshot_date: "2026-01-01",
    location_id: null,
    category_main_cb: null,
    category_type_cb: null,
    listing_count: 0,
    avg_price_czk: null,
    median_price_czk: null,
    avg_price_per_m2: null,
    new_count: 0,
    removed_count: 0,
    median_days_on_market: null,
    avg_days_on_market: null,
    price_drop_share: null,
    median_first_to_last_price_change_pct: null,
    ...overrides,
  };
}

function summary(overrides: Partial<DatasetSummary>): DatasetSummary {
  return {
    active_listing_count: 0,
    total_listing_count: 0,
    active_with_gps_count: 0,
    active_with_region_count: 0,
    active_with_detail_count: 0,
    active_with_valuation_count: 0,
    active_with_anomaly_count: 0,
    active_without_gps_count: 0,
    active_without_region_count: 0,
    inventory_region_listing_sum: 0,
    last_successful_scrape_at: null,
    ...overrides,
  };
}

describe("interpretActiveListings", () => {
  it("reports ingest_dominated while a sweep is running", () => {
    const s = summary({ active_listing_count: 500, dataset_freshness: "in_progress" });
    const interp = interpretActiveListings(s, []);
    expect(interp.state).toBe("ingest_dominated");
    expect(interp.direction).toBe("partial");
    expect(interp.meaning).toBe(cs.kpiInterpret.aktivni.vyznamProbiha);
  });

  it("reports insufficient_history with no snapshots at all", () => {
    const s = summary({ active_listing_count: 105310, dataset_freshness: "final_complete" });
    const interp = interpretActiveListings(s, []);
    expect(interp.state).toBe("insufficient_history");
    expect(interp.benchmark).toBe(cs.kpiInterpret.bezHistorieSnapshotu);
  });

  it("reports insufficient_history with only one snapshot date", () => {
    const s = summary({ active_listing_count: 105310, dataset_freshness: "final_complete" });
    const interp = interpretActiveListings(s, [snap({ snapshot_date: "2026-07-03", listing_count: 105310 })]);
    expect(interp.state).toBe("insufficient_history");
    expect(interp.benchmark).toBe(cs.kpiInterpret.bezPredchozihoSnapshotu);
  });

  it("REGRESSION: does not present a dataset-rebuild delta (+5647 %) as a market trend", () => {
    // The exact shape of the original bug: previous snapshot ~1.8k (demo era),
    // latest 105 310 (post full-scrape).
    const s = summary({ active_listing_count: 105310, dataset_freshness: "final_complete" });
    const snapshots = [
      snap({ snapshot_date: "2026-07-02", listing_count: 1800 }),
      snap({ snapshot_date: "2026-07-04", listing_count: 105310 }),
    ];
    const interp = interpretActiveListings(s, snapshots);

    expect(interp.state).toBe("baseline");
    expect(interp.direction).toBe("unavailable");
    expect(interp.directionLabel).not.toMatch(/sledovat/i);
    expect(interp.benchmark).toContain("z doby budování datasetu");
    // The raw value itself must remain the truthful, ungroomed count.
    expect(s.active_listing_count).toBe(105310);
  });

  it("reports a genuine trend for a plausible period delta", () => {
    const s = summary({ active_listing_count: 105, dataset_freshness: "final_complete" });
    const snapshots = [
      snap({ snapshot_date: "2026-07-01", listing_count: 100 }),
      snap({ snapshot_date: "2026-07-02", listing_count: 105 }),
    ];
    const interp = interpretActiveListings(s, snapshots);

    expect(interp.state).toBe("trend");
    expect(interp.confidence).toBe("medium");
    expect(interp.benchmark).toContain("+5,0 %");
  });

  it("downgrades a plausible trend to informational when the dataset is marked partial", () => {
    const s = summary({ active_listing_count: 105, dataset_completeness: "partial" });
    const snapshots = [
      snap({ snapshot_date: "2026-07-01", listing_count: 100 }),
      snap({ snapshot_date: "2026-07-02", listing_count: 105 }),
    ];
    const interp = interpretActiveListings(s, snapshots);
    expect(interp.state).toBe("informational");
    expect(interp.direction).toBe("partial");
  });
});

describe("interpretNewListings30", () => {
  it("REGRESSION: flags ingest_dominated instead of a watch-worthy market surge", () => {
    // The exact shape of the original bug: 106 359 "new" against 105 310 active.
    const s = summary({ active_listing_count: 105310, dataset_freshness: "final_complete" });
    const interp = interpretNewListings30(106359, 1049, s);

    expect(interp.state).toBe("ingest_dominated");
    expect(interp.direction).not.toBe("watch");
    expect(interp.benchmark).toBe(cs.kpiInterpret.nove.ingestDominuje);
  });

  it("reports ingest_dominated while a sweep is running, regardless of counts", () => {
    const s = summary({ active_listing_count: 1000, dataset_freshness: "in_progress" });
    const interp = interpretNewListings30(5, 2, s);
    expect(interp.state).toBe("ingest_dominated");
    expect(interp.direction).toBe("partial");
  });

  it("reports a genuine trend with watch sentiment for a real net inflow", () => {
    const s = summary({ active_listing_count: 1000, dataset_freshness: "final_complete" });
    const interp = interpretNewListings30(50, 10, s);
    expect(interp.state).toBe("trend");
    expect(interp.direction).toBe("watch");
    expect(interp.benchmark).toContain("+40");
  });

  it("reports stable when new and removed roughly balance", () => {
    const s = summary({ active_listing_count: 1000, dataset_freshness: "final_complete" });
    const interp = interpretNewListings30(10, 10, s);
    expect(interp.state).toBe("trend");
    expect(interp.direction).toBe("stable");
  });

  it("reports concern for a large net outflow", () => {
    const s = summary({ active_listing_count: 1000, dataset_freshness: "final_complete" });
    const interp = interpretNewListings30(5, 50, s);
    expect(interp.direction).toBe("concern");
  });
});

describe("interpretRemovedListings30", () => {
  it("reports ingest_dominated while a sweep is running", () => {
    const s = summary({ dataset_freshness: "in_progress" });
    const interp = interpretRemovedListings30(10, 50, s);
    expect(interp.state).toBe("ingest_dominated");
    expect(interp.direction).toBe("partial");
  });

  it("reports high confidence and watch when removals dominate flow", () => {
    const s = summary({ dataset_freshness: "final_complete" });
    const interp = interpretRemovedListings30(70, 30, s);
    expect(interp.confidence).toBe("high");
    expect(interp.direction).toBe("watch");
  });

  it("reports stable when removals are a small share of flow", () => {
    const s = summary({ dataset_freshness: "final_complete" });
    const interp = interpretRemovedListings30(10, 90, s);
    expect(interp.direction).toBe("stable");
  });

  it("reports low confidence when there is no flow to compare at all", () => {
    const interp = interpretRemovedListings30(0, 0, summary({}));
    expect(interp.confidence).toBe("low");
    expect(interp.benchmark).toBe(cs.kpiInterpret.bezSrovnani);
  });
});

describe("interpretAdvancedMetric", () => {
  it("reports insufficient_history when there is no value at all yet", () => {
    const interp = interpretAdvancedMetric("median_dom", null, null, "medianDom");
    expect(interp?.state).toBe("insufficient_history");
    expect(interp?.direction).toBe("unavailable");
    expect(interp?.nextStep).toBeUndefined();
  });

  it("reports insufficient_history (not unavailable) when a value exists but no prior snapshot", () => {
    const interp = interpretAdvancedMetric("median_dom", 12, null, "medianDom");
    expect(interp?.state).toBe("insufficient_history");
    expect(interp?.direction).toBe("neutral");
    expect(interp?.benchmark).toBe(cs.kpiInterpret.bezPredchozihoSnapshotu);
  });

  it("REGRESSION: treats a dataset-rebuild-scale swing as baseline, not a trend", () => {
    // e.g. median days-on-market jumping from a tiny demo dataset's ~1 to 50
    // once the full scrape lands -- not a real market slowdown.
    const interp = interpretAdvancedMetric("median_dom", 50, 1, "medianDom");
    expect(interp?.state).toBe("baseline");
    expect(interp?.direction).toBe("unavailable");
    expect(interp?.benchmark).toBe(cs.kpiInterpret.advanced.baselineNesrovnatelny);
  });

  it("classifies plausible drop_share increases using the same period-change guard", () => {
    const interp = interpretAdvancedMetric("drop_share", 0.12, 0.1, "dropShare");
    expect(interp?.state).toBe("trend");
    expect(interp?.direction).toBe("watch");
  });

  it("classifies a favorable drop_share decrease as healthy", () => {
    const interp = interpretAdvancedMetric("drop_share", 0.08, 0.1, "dropShare");
    expect(interp?.state).toBe("trend");
    expect(interp?.direction).toBe("healthy");
  });

  it("classifies price_change increases as watch and decreases as concern", () => {
    const up = interpretAdvancedMetric("price_change", 10, 9, "priceChange");
    expect(up?.direction).toBe("watch");
    const down = interpretAdvancedMetric("price_change", 8, 10, "priceChange");
    expect(down?.direction).toBe("concern");
  });
});

describe("interpretRegionalInventory", () => {
  it("reports unavailable for an empty breakdown", () => {
    const interp = interpretRegionalInventory([]);
    expect(interp.state).toBe("informational");
    expect(interp.confidence).toBe("low");
    expect(interp.direction).toBe("unavailable");
  });

  it("keeps high confidence for a full breakdown with a small unresolved-region share", () => {
    const rows: InventoryRegionRow[] = [
      { region: "Hlavní město Praha", listing_count: 15310 },
      { region: "Středočeský kraj", listing_count: 15092 },
      { region: "Neznámý", listing_count: 500 },
    ];
    const interp = interpretRegionalInventory(rows);
    // 500 / 30902 ≈ 1.6 % -- well under the 15 % distortion threshold.
    expect(interp.confidence).toBe("high");
    expect(interp.direction).toBe("neutral");
  });

  it("downgrades confidence when the unresolved-region share is large", () => {
    const rows: InventoryRegionRow[] = [
      { region: "Hlavní město Praha", listing_count: 100 },
      { region: "Neznámý", listing_count: 50 },
    ];
    const interp = interpretRegionalInventory(rows);
    // 50 / 150 ≈ 33 % -- above the 15 % threshold.
    expect(interp.confidence).toBe("low");
    expect(interp.direction).toBe("watch");
  });
});

describe("interpretDetailCoverage", () => {
  it("reports healthy + high confidence at full coverage", () => {
    const interp = interpretDetailCoverage(100, 100, 0);
    expect(interp.direction).toBe("healthy");
    expect(interp.confidence).toBe("high");
  });

  it("reports watch + medium confidence at moderate coverage", () => {
    const interp = interpretDetailCoverage(75, 100, 25);
    expect(interp.direction).toBe("watch");
    expect(interp.confidence).toBe("medium");
  });

  it("reports concern + low confidence at poor coverage", () => {
    const interp = interpretDetailCoverage(50, 100, 50);
    expect(interp.direction).toBe("concern");
    expect(interp.confidence).toBe("low");
  });
});

describe("cross-KPI: advanced metrics use the same classification rules as active listings", () => {
  it("both interpretActiveListings and interpretAdvancedMetric classify the same delta as baseline", () => {
    const s = summary({ active_listing_count: 105310, dataset_freshness: "final_complete" });
    const activeInterp = interpretActiveListings(s, [
      snap({ snapshot_date: "2026-07-02", listing_count: 1800 }),
      snap({ snapshot_date: "2026-07-04", listing_count: 105310 }),
    ]);
    const advancedInterp = interpretAdvancedMetric("median_dom", 105310, 1800, "medianDom");

    expect(activeInterp.state).toBe("baseline");
    expect(advancedInterp?.state).toBe("baseline");
  });
});
