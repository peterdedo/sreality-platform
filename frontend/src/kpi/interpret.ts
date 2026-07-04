import type { DatasetSummary, MarketDynamicsSnapshot, ValuationSummary } from "../api/types";
import { cs } from "../locale/cs";
import {
  aggregateSnapshotsByDate,
  avg,
  latestTwoSnapshotDates,
  pctChange,
  regionalSpread,
} from "./benchmarks";
import type { InventoryRegionRow, KpiDirection, KpiInterpretation } from "./types";

function directionLabel(direction: KpiDirection): string {
  return cs.kpiInterpret.smery[direction];
}

function fmt(n: number): string {
  return n.toLocaleString("cs-CZ");
}

function fmtPct(n: number, digits = 1): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits).replace(".", ",")} %`;
}

export function interpretActiveListings(
  summary: DatasetSummary | null | undefined,
  snapshots?: MarketDynamicsSnapshot[] | null
): KpiInterpretation {
  const active = summary?.active_listing_count ?? 0;
  const inProgress = summary?.dataset_freshness === "in_progress";
  const partial = summary?.dataset_completeness === "partial";

  if (inProgress) {
    return {
      meaning: cs.kpiInterpret.aktivni.vyznamProbiha,
      direction: "partial",
      directionLabel: directionLabel("partial"),
      nextStep: cs.kpiInterpret.aktivni.dalsiScraping,
      nextStepLink: { to: "/sprava-scrapingu", label: cs.nav.spravaScrapingu },
      limited: true,
    };
  }

  let benchmark: string | undefined;
  let direction: KpiDirection = "neutral";

  if (snapshots && snapshots.length > 0) {
    const agg = aggregateSnapshotsByDate(snapshots);
    const pair = latestTwoSnapshotDates(agg);
    if (pair?.previous) {
      const delta = pctChange(pair.latest.listing_count, pair.previous.listing_count);
      if (delta != null) {
        benchmark = cs.kpiInterpret.aktivni.srovnaniSnapshot
          .replace("{delta}", fmtPct(delta))
          .replace("{date}", pair.previous.snapshot_date);
        if (Math.abs(delta) < 2) direction = "stable";
        else if (delta > 5) direction = "watch";
        else if (delta < -5) direction = "concern";
        else direction = "neutral";
      }
    } else if (pair) {
      benchmark = cs.kpiInterpret.bezPredchozihoSnapshotu;
      direction = "unavailable";
    }
  } else {
    benchmark = cs.kpiInterpret.bezHistorieSnapshotu;
    direction = "unavailable";
  }

  if (partial) {
    return {
      meaning: cs.kpiInterpret.aktivni.vyznamPartial.replace("{active}", fmt(active)),
      benchmark,
      direction: "watch",
      directionLabel: directionLabel("watch"),
      nextStep: cs.kpiInterpret.aktivni.dalsiScraping,
      nextStepLink: { to: "/sprava-scrapingu", label: cs.nav.spravaScrapingu },
      limited: true,
    };
  }

  return {
    meaning: cs.kpiInterpret.aktivni.vyznam.replace("{active}", fmt(active)),
    benchmark,
    direction,
    directionLabel: directionLabel(direction),
    nextStep: cs.kpiInterpret.aktivni.dalsiNabidky,
    nextStepLink: { to: "/nabidky", label: cs.nav.nabidky },
  };
}

export function interpretNewListings30(
  newCount: number,
  removedCount: number,
  summary?: DatasetSummary | null
): KpiInterpretation {
  const net = newCount - removedCount;
  const inProgress = summary?.dataset_freshness === "in_progress";

  let direction: KpiDirection = "stable";
  if (net > removedCount * 0.2 && net > 0) direction = "watch";
  else if (net < 0 && Math.abs(net) > newCount * 0.2) direction = "concern";
  else if (newCount === 0 && removedCount === 0) direction = "neutral";

  const benchmark = cs.kpiInterpret.nove.benchmark
    .replace("{net}", net >= 0 ? `+${fmt(net)}` : fmt(net))
    .replace("{new}", fmt(newCount))
    .replace("{removed}", fmt(removedCount));

  return {
    meaning: cs.kpiInterpret.nove.vyznam,
    benchmark,
    direction: inProgress ? "partial" : direction,
    directionLabel: directionLabel(inProgress ? "partial" : direction),
    nextStep: cs.kpiInterpret.nove.dalsi,
    nextStepLink: { to: "/analytika", label: cs.nav.analytika },
    limited: inProgress,
  };
}

export function interpretRemovedListings30(
  removedCount: number,
  newCount: number,
  summary?: DatasetSummary | null
): KpiInterpretation {
  const inProgress = summary?.dataset_freshness === "in_progress";
  const shareOfFlow =
    newCount + removedCount > 0 ? (removedCount / (newCount + removedCount)) * 100 : null;

  let direction: KpiDirection = "neutral";
  if (shareOfFlow != null) {
    if (shareOfFlow > 55) direction = "watch";
    else if (shareOfFlow < 35) direction = "stable";
  }

  const benchmark =
    shareOfFlow != null
      ? cs.kpiInterpret.stazene.benchmark.replace("{pct}", shareOfFlow.toFixed(0))
      : cs.kpiInterpret.bezSrovnani;

  return {
    meaning: cs.kpiInterpret.stazene.vyznam,
    benchmark,
    direction: inProgress ? "partial" : direction,
    directionLabel: directionLabel(inProgress ? "partial" : direction),
    nextStep: cs.kpiInterpret.stazene.dalsi,
    nextStepLink: { to: "/analytika", label: cs.nav.analytika },
    limited: inProgress,
  };
}

export function interpretPriceDrops(
  totalMatched: number | null,
  activeCount: number,
  previewCount: number,
  avgDropShareFromSnapshots?: number | null
): KpiInterpretation {
  if (totalMatched == null) {
    return {
      meaning: cs.kpiInterpret.poklesy.vyznam,
      benchmark: cs.kpiInterpret.poklesy.bezCelkovehoPoctu.replace("{shown}", String(previewCount)),
      direction: "unavailable",
      directionLabel: directionLabel("unavailable"),
      nextStep: cs.kpiInterpret.poklesy.dalsi,
      nextStepLink: { to: "/analytika", label: cs.nav.analytika },
      limited: true,
    };
  }

  const sharePct = activeCount > 0 ? (totalMatched / activeCount) * 100 : null;
  let direction: KpiDirection = "neutral";
  if (sharePct != null) {
    if (sharePct >= 8) direction = "watch";
    else if (sharePct <= 2) direction = "stable";
  }

  let benchmark = cs.kpiInterpret.poklesy.benchmark
    .replace("{total}", fmt(totalMatched))
    .replace("{active}", fmt(activeCount));
  if (sharePct != null) {
    benchmark += ` ${cs.kpiInterpret.poklesy.podil.replace("{pct}", sharePct.toFixed(1).replace(".", ","))}`;
  }
  if (avgDropShareFromSnapshots != null) {
    benchmark += ` ${cs.kpiInterpret.poklesy.vsSegment.replace(
      "{seg}",
      (avgDropShareFromSnapshots * 100).toFixed(0)
    )}`;
  }

  return {
    meaning: cs.kpiInterpret.poklesy.vyznam,
    benchmark,
    direction,
    directionLabel: directionLabel(direction),
    nextStep: cs.kpiInterpret.poklesy.dalsi,
    nextStepLink: { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy },
  };
}

export function interpretUnderMarketShare(
  valuation: ValuationSummary | null | undefined,
  activeCount: number,
  valuedCount: number
): KpiInterpretation | null {
  if (!valuation || valuedCount === 0) {
    return {
      meaning: cs.kpiInterpret.podTrhem.vyznam,
      benchmark: cs.kpiInterpret.podTrhem.bezPrepoctu,
      direction: "unavailable",
      directionLabel: directionLabel("unavailable"),
      nextStep: cs.kpiInterpret.podTrhem.dalsiPrepocet,
      nextStepLink: { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy },
      limited: true,
    };
  }

  const total = valuation.total_valued_listings;
  const under = valuation.by_classification.under_market ?? 0;
  const coveragePct = activeCount > 0 ? (total / activeCount) * 100 : 0;
  const underPct = total > 0 ? (under / total) * 100 : 0;

  let direction: KpiDirection = "neutral";
  if (underPct >= 25) direction = "watch";
  else if (underPct <= 10) direction = "stable";

  const limited = coveragePct < 80;

  return {
    meaning: cs.kpiInterpret.podTrhem.vyznam,
    benchmark: cs.kpiInterpret.podTrhem.benchmark
      .replace("{under}", fmt(under))
      .replace("{pct}", underPct.toFixed(1).replace(".", ","))
      .replace("{coverage}", coveragePct.toFixed(0)),
    direction: limited ? "partial" : direction,
    directionLabel: directionLabel(limited ? "partial" : direction),
    nextStep: cs.kpiInterpret.podTrhem.dalsi,
    nextStepLink: { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy },
    limited,
  };
}

export function interpretRegionalInventory(rows: InventoryRegionRow[]): KpiInterpretation {
  const spread = regionalSpread(rows);
  if (!spread) {
    return {
      meaning: cs.kpiInterpret.region.vyznam,
      direction: "unavailable",
      directionLabel: directionLabel("unavailable"),
      nextStep: cs.kpiInterpret.region.dalsi,
      nextStepLink: { to: "/mapa", label: cs.nav.mapa },
    };
  }

  let direction: KpiDirection = "neutral";
  if (spread.unknownSharePct != null && spread.unknownSharePct > 5) direction = "watch";
  else if (spread.topSharePct != null && spread.topSharePct > 45) direction = "neutral";

  const benchmark = cs.kpiInterpret.region.benchmark
    .replace("{region}", spread.topRegion ?? "—")
    .replace("{pct}", spread.topSharePct?.toFixed(0) ?? "—");

  const unknownNote =
    spread.unknownSharePct != null && spread.unknownSharePct > 0
      ? ` ${cs.kpiInterpret.region.neznamy.replace("{pct}", spread.unknownSharePct.toFixed(1).replace(".", ","))}`
      : "";

  return {
    meaning: cs.kpiInterpret.region.vyznam,
    benchmark: benchmark + unknownNote,
    direction,
    directionLabel: directionLabel(direction),
    nextStep: cs.kpiInterpret.region.dalsi,
    nextStepLink: { to: "/analytika", label: cs.nav.analytika },
    limited: spread.unknownSharePct != null && spread.unknownSharePct > 0,
  };
}

export function interpretDetailCoverage(
  withDetail: number,
  active: number,
  missing: number
): KpiInterpretation {
  const pct = active > 0 ? (withDetail / active) * 100 : 0;
  let direction: KpiDirection = "healthy";
  if (pct < 90) direction = "watch";
  if (pct < 70) direction = "concern";
  if (missing === 0 && active > 0) direction = "healthy";

  return {
    meaning: cs.kpiInterpret.detaily.vyznam,
    benchmark: cs.kpiInterpret.detaily.benchmark
      .replace("{pct}", pct.toFixed(0))
      .replace("{missing}", fmt(missing)),
    direction,
    directionLabel: directionLabel(direction),
    nextStep:
      missing > 0 ? cs.kpiInterpret.detaily.dalsiDoplnit : cs.kpiInterpret.detaily.dalsiAnalyzy,
    nextStepLink:
      missing > 0
        ? { to: "/sprava-scrapingu", label: cs.nav.spravaScrapingu }
        : { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy },
  };
}

export function interpretAdvancedMetric(
  metric: "median_dom" | "drop_share" | "price_change",
  current: number | null,
  previous: number | null,
  labelKey: "medianDom" | "dropShare" | "priceChange"
): KpiInterpretation | null {
  if (current == null) {
    return {
      meaning: cs.kpiInterpret.advanced[labelKey].vyznam,
      benchmark: cs.kpiInterpret.bezHistorieSnapshotu,
      direction: "unavailable",
      directionLabel: directionLabel("unavailable"),
      limited: true,
    };
  }

  if (previous == null) {
    return {
      meaning: cs.kpiInterpret.advanced[labelKey].vyznam,
      benchmark: cs.kpiInterpret.bezPredchozihoSnapshotu,
      direction: "neutral",
      directionLabel: directionLabel("neutral"),
      nextStep: cs.kpiInterpret.advanced.dalsi,
      nextStepLink: { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy },
      limited: true,
    };
  }

  const delta = pctChange(current, previous);
  let direction: KpiDirection = "stable";
  if (metric === "drop_share" && delta != null) {
    if (delta > 15) direction = "watch";
    else if (delta < -15) direction = "healthy";
  } else if (metric === "median_dom" && delta != null) {
    if (delta > 10) direction = "watch";
    else if (delta < -10) direction = "healthy";
  } else if (metric === "price_change" && delta != null) {
    if (delta > 5) direction = "watch";
    else if (delta < -5) direction = "concern";
  }

  const benchmark =
    delta != null
      ? cs.kpiInterpret.advanced.srovnaniSnapshot.replace("{delta}", fmtPct(delta))
      : cs.kpiInterpret.bezSrovnani;

  return {
    meaning: cs.kpiInterpret.advanced[labelKey].vyznam,
    benchmark,
    direction,
    directionLabel: directionLabel(direction),
    nextStep: cs.kpiInterpret.advanced.dalsi,
    nextStepLink: { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy },
  };
}

/** Average price_drop_share from latest snapshot date aggregates. */
export function latestAvgDropShare(snapshots: MarketDynamicsSnapshot[]): number | null {
  const agg = aggregateSnapshotsByDate(snapshots);
  const pair = latestTwoSnapshotDates(agg);
  if (!pair) return null;
  return avg(pair.latest.price_drop_shares);
}
