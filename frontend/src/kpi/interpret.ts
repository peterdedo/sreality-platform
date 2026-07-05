import type { DatasetSummary, MarketDynamicsSnapshot, ValuationSummary } from "../api/types";
import { cs } from "../locale/cs";
import {
  aggregateSnapshotsByDate,
  avg,
  latestTwoSnapshotDates,
  pctChange,
  regionalSpread,
} from "./benchmarks";
import { buildInterpretation, classifyPeriodChange, fmtSnapshotDate } from "./model";
import type { InventoryRegionRow, KpiDirection, KpiInterpretation } from "./types";

function fmt(n: number): string {
  return n.toLocaleString("cs-CZ");
}

function fmtPct(n: number, digits = 1): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits).replace(".", ",")} %`;
}

/** Map a plausible period delta to sentiment using per-metric thresholds.
 *  Only ever called for a "trend" classification, so it never sees the
 *  implausible-rebuild deltas the model already filtered out. */
function sentimentFromDelta(
  delta: number,
  opts: { stableWithin?: number; watchAbove: number; concernBelow?: number; healthyBelow?: number }
): KpiDirection {
  const { stableWithin = 2, watchAbove, concernBelow, healthyBelow } = opts;
  if (Math.abs(delta) < stableWithin) return "stable";
  if (delta >= watchAbove) return "watch";
  if (healthyBelow != null && delta <= healthyBelow) return "healthy";
  if (concernBelow != null && delta <= concernBelow) return "concern";
  return "neutral";
}

export function interpretActiveListings(
  summary: DatasetSummary | null | undefined,
  snapshots?: MarketDynamicsSnapshot[] | null
): KpiInterpretation {
  const active = summary?.active_listing_count ?? 0;
  const inProgress = summary?.dataset_freshness === "in_progress";
  const partial = summary?.dataset_completeness === "partial";

  // Dataset is being scraped right now: the number is provisional ingestion,
  // not a market figure.
  if (inProgress) {
    return buildInterpretation({
      state: "ingest_dominated",
      confidence: "low",
      sentiment: "partial",
      comparison: { kind: "none" },
      meaning: cs.kpiInterpret.aktivni.vyznamProbiha,
      nextStep: cs.kpiInterpret.aktivni.dalsiScraping,
      nextStepLink: { to: "/sprava-scrapingu", label: cs.nav.spravaScrapingu },
    });
  }

  const meaning = partial
    ? cs.kpiInterpret.aktivni.vyznamPartial.replace("{active}", fmt(active))
    : cs.kpiInterpret.aktivni.vyznam;
  const nextStep = partial ? cs.kpiInterpret.aktivni.dalsiScraping : cs.kpiInterpret.aktivni.dalsiNabidky;
  const nextStepLink = partial
    ? { to: "/sprava-scrapingu", label: cs.nav.spravaScrapingu }
    : { to: "/nabidky", label: cs.nav.nabidky };

  const agg = snapshots && snapshots.length > 0 ? aggregateSnapshotsByDate(snapshots) : [];
  const pair = latestTwoSnapshotDates(agg);

  // No history at all → nothing to compare against.
  if (!pair) {
    return buildInterpretation({
      state: "insufficient_history",
      confidence: "low",
      sentiment: partial ? "partial" : "unavailable",
      comparison: { kind: "none" },
      meaning,
      detail: cs.kpiInterpret.bezHistorieSnapshotu,
      nextStep,
      nextStepLink,
    });
  }

  const cls = classifyPeriodChange(pair.latest.listing_count, pair.previous?.listing_count);
  const prevDate = pair.previous ? fmtSnapshotDate(pair.previous.snapshot_date) : "";

  if (cls.state === "insufficient_history") {
    return buildInterpretation({
      state: "insufficient_history",
      confidence: "low",
      sentiment: partial ? "partial" : "unavailable",
      comparison: { kind: "none" },
      meaning,
      detail: cs.kpiInterpret.bezPredchozihoSnapshotu,
      nextStep,
      nextStepLink,
    });
  }

  if (cls.state === "baseline") {
    // Comparison straddles a dataset rebuild — not a market trend.
    return buildInterpretation({
      state: "baseline",
      confidence: "low",
      sentiment: "unavailable",
      comparison: { kind: "previous_snapshot", label: prevDate },
      meaning,
      detail: cs.kpiInterpret.aktivni.baselineNesrovnatelny.replace("{date}", prevDate),
      nextStep,
      nextStepLink,
    });
  }

  // Genuine trend.
  const delta = cls.deltaPct ?? 0;
  const sentiment = partial
    ? "partial"
    : sentimentFromDelta(delta, { watchAbove: 5, concernBelow: -5 });
  return buildInterpretation({
    state: partial ? "informational" : "trend",
    confidence: partial ? "low" : "medium",
    sentiment,
    comparison: { kind: "previous_snapshot", label: prevDate },
    meaning,
    detail: cs.kpiInterpret.aktivni.srovnaniSnapshot
      .replace("{delta}", fmtPct(delta))
      .replace("{date}", prevDate),
    nextStep,
    nextStepLink,
  });
}

export function interpretNewListings30(
  newCount: number,
  removedCount: number,
  summary?: DatasetSummary | null
): KpiInterpretation {
  const net = newCount - removedCount;
  const inProgress = summary?.dataset_freshness === "in_progress";
  const active = summary?.active_listing_count ?? 0;
  // ~The whole active dataset was first seen in this window → the "new" count
  // reflects the initial full scrape, not market churn.
  const ingestDominated = active > 0 && newCount >= active * 0.8;

  const nextStep = cs.kpiInterpret.nove.dalsi;
  const nextStepLink = { to: "/analytika", label: cs.nav.analytika };

  if (inProgress || ingestDominated) {
    return buildInterpretation({
      state: "ingest_dominated",
      confidence: "low",
      sentiment: inProgress ? "partial" : "neutral",
      comparison: { kind: "none" },
      meaning: cs.kpiInterpret.nove.vyznam,
      detail: cs.kpiInterpret.nove.ingestDominuje,
      nextStep,
      nextStepLink,
    });
  }

  let sentiment: KpiDirection = "stable";
  if (net > removedCount * 0.2 && net > 0) sentiment = "watch";
  else if (net < 0 && Math.abs(net) > newCount * 0.2) sentiment = "concern";
  else if (newCount === 0 && removedCount === 0) sentiment = "neutral";

  return buildInterpretation({
    state: "trend",
    confidence: "medium",
    sentiment,
    comparison: { kind: "period_flow" },
    meaning: cs.kpiInterpret.nove.vyznam,
    detail: cs.kpiInterpret.nove.benchmark
      .replace("{net}", net >= 0 ? `+${fmt(net)}` : fmt(net))
      .replace("{new}", fmt(newCount))
      .replace("{removed}", fmt(removedCount)),
    nextStep,
    nextStepLink,
  });
}

export function interpretRemovedListings30(
  removedCount: number,
  newCount: number,
  summary?: DatasetSummary | null
): KpiInterpretation {
  const inProgress = summary?.dataset_freshness === "in_progress";
  const shareOfFlow =
    newCount + removedCount > 0 ? (removedCount / (newCount + removedCount)) * 100 : null;

  const nextStep = cs.kpiInterpret.stazene.dalsi;
  const nextStepLink = { to: "/analytika", label: cs.nav.analytika };

  if (inProgress) {
    return buildInterpretation({
      state: "ingest_dominated",
      confidence: "low",
      sentiment: "partial",
      comparison: { kind: "none" },
      meaning: cs.kpiInterpret.stazene.vyznam,
      detail:
        shareOfFlow != null
          ? cs.kpiInterpret.stazene.benchmark.replace("{pct}", shareOfFlow.toFixed(0))
          : cs.kpiInterpret.bezSrovnani,
      nextStep,
      nextStepLink,
    });
  }

  let sentiment: KpiDirection = "neutral";
  if (shareOfFlow != null) {
    if (shareOfFlow > 55) sentiment = "watch";
    else if (shareOfFlow < 35) sentiment = "stable";
  }

  return buildInterpretation({
    state: "informational",
    confidence: shareOfFlow != null ? "high" : "low",
    sentiment,
    comparison:
      shareOfFlow != null
        ? { kind: "share_of_total" }
        : { kind: "none" },
    meaning: cs.kpiInterpret.stazene.vyznam,
    detail:
      shareOfFlow != null
        ? cs.kpiInterpret.stazene.benchmark.replace("{pct}", shareOfFlow.toFixed(0))
        : cs.kpiInterpret.bezSrovnani,
    nextStep,
    nextStepLink,
  });
}

export function interpretPriceDrops(
  totalMatched: number | null,
  activeCount: number,
  previewCount: number,
  avgDropShareFromSnapshots?: number | null
): KpiInterpretation {
  const nextStep = cs.kpiInterpret.poklesy.dalsi;
  const nextStepLink = { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy };

  if (totalMatched == null) {
    return buildInterpretation({
      state: "informational",
      confidence: "low",
      sentiment: "unavailable",
      comparison: { kind: "none" },
      meaning: cs.kpiInterpret.poklesy.vyznam,
      detail: cs.kpiInterpret.poklesy.bezCelkovehoPoctu.replace("{shown}", String(previewCount)),
      nextStep,
      nextStepLink,
    });
  }

  const sharePct = activeCount > 0 ? (totalMatched / activeCount) * 100 : null;
  let sentiment: KpiDirection = "neutral";
  if (sharePct != null) {
    if (sharePct >= 8) sentiment = "watch";
    else if (sharePct <= 2) sentiment = "stable";
  }

  let detail = cs.kpiInterpret.poklesy.benchmark
    .replace("{total}", fmt(totalMatched))
    .replace("{active}", fmt(activeCount));
  if (sharePct != null) {
    detail += ` ${cs.kpiInterpret.poklesy.podil.replace("{pct}", sharePct.toFixed(1).replace(".", ","))}`;
  }
  if (avgDropShareFromSnapshots != null) {
    detail += ` ${cs.kpiInterpret.poklesy.vsSegment.replace(
      "{seg}",
      (avgDropShareFromSnapshots * 100).toFixed(0)
    )}`;
  }

  return buildInterpretation({
    state: "informational",
    confidence: "high",
    sentiment,
    comparison: { kind: "share_of_total" },
    meaning: cs.kpiInterpret.poklesy.vyznam,
    detail,
    nextStep,
    nextStepLink,
  });
}

export function interpretUnderMarketShare(
  valuation: ValuationSummary | null | undefined,
  activeCount: number,
  valuedCount: number
): KpiInterpretation | null {
  const nextStepLink = { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy };

  if (!valuation || valuedCount === 0) {
    return buildInterpretation({
      state: "informational",
      confidence: "low",
      sentiment: "unavailable",
      comparison: { kind: "none" },
      meaning: cs.kpiInterpret.podTrhem.vyznam,
      detail: cs.kpiInterpret.podTrhem.bezPrepoctu,
      nextStep: cs.kpiInterpret.podTrhem.dalsiPrepocet,
      nextStepLink,
    });
  }

  const total = valuation.total_valued_listings;
  const under = valuation.by_classification.under_market ?? 0;
  const coveragePct = activeCount > 0 ? (total / activeCount) * 100 : 0;
  const underPct = total > 0 ? (under / total) * 100 : 0;
  // A model fitted on a small fraction of active listings can't be read as a
  // market-wide share.
  const limited = coveragePct < 80;

  let sentiment: KpiDirection;
  if (limited) sentiment = "partial";
  else if (underPct >= 25) sentiment = "watch";
  else if (underPct <= 10) sentiment = "stable";
  else sentiment = "neutral";

  return buildInterpretation({
    state: "informational",
    confidence: limited ? "low" : "high",
    sentiment,
    comparison: { kind: "share_of_total" },
    meaning: cs.kpiInterpret.podTrhem.vyznam,
    detail: cs.kpiInterpret.podTrhem.benchmark
      .replace("{under}", fmt(under))
      .replace("{pct}", underPct.toFixed(1).replace(".", ","))
      .replace("{coverage}", coveragePct.toFixed(0)),
    nextStep: cs.kpiInterpret.podTrhem.dalsi,
    nextStepLink,
  });
}

export function interpretRegionalInventory(rows: InventoryRegionRow[]): KpiInterpretation {
  const spread = regionalSpread(rows);
  if (!spread) {
    return buildInterpretation({
      state: "informational",
      confidence: "low",
      sentiment: "unavailable",
      comparison: { kind: "none" },
      meaning: cs.kpiInterpret.region.vyznam,
      nextStep: cs.kpiInterpret.region.dalsi,
      nextStepLink: { to: "/mapa", label: cs.nav.mapa },
    });
  }

  // The breakdown covers the full dataset; only a large unresolved-region share
  // (already stated in the detail) actually distorts the distribution.
  const unknownHigh = spread.unknownSharePct != null && spread.unknownSharePct > 15;
  const sentiment: KpiDirection =
    spread.unknownSharePct != null && spread.unknownSharePct > 5 ? "watch" : "neutral";

  const unknownNote =
    spread.unknownSharePct != null && spread.unknownSharePct > 0
      ? ` ${cs.kpiInterpret.region.neznamy.replace("{pct}", spread.unknownSharePct.toFixed(1).replace(".", ","))}`
      : "";

  return buildInterpretation({
    state: "informational",
    confidence: unknownHigh ? "low" : "high",
    sentiment,
    comparison: { kind: "share_of_total" },
    meaning: cs.kpiInterpret.region.vyznam,
    detail:
      cs.kpiInterpret.region.benchmark
        .replace("{region}", spread.topRegion ?? "—")
        .replace("{pct}", spread.topSharePct?.toFixed(0) ?? "—") + unknownNote,
    nextStep: cs.kpiInterpret.region.dalsi,
    nextStepLink: { to: "/analytika", label: cs.nav.analytika },
  });
}

export function interpretDetailCoverage(
  withDetail: number,
  active: number,
  missing: number
): KpiInterpretation {
  const pct = active > 0 ? (withDetail / active) * 100 : 0;
  let sentiment: KpiDirection = "healthy";
  if (pct < 90) sentiment = "watch";
  if (pct < 70) sentiment = "concern";
  if (missing === 0 && active > 0) sentiment = "healthy";

  const confidence = pct >= 90 ? "high" : pct >= 70 ? "medium" : "low";

  return buildInterpretation({
    state: "informational",
    confidence,
    sentiment,
    comparison: { kind: "share_of_total" },
    meaning: cs.kpiInterpret.detaily.vyznam,
    detail: cs.kpiInterpret.detaily.benchmark
      .replace("{pct}", pct.toFixed(0))
      .replace("{missing}", fmt(missing)),
    nextStep: missing > 0 ? cs.kpiInterpret.detaily.dalsiDoplnit : cs.kpiInterpret.detaily.dalsiAnalyzy,
    nextStepLink:
      missing > 0
        ? { to: "/sprava-scrapingu", label: cs.nav.spravaScrapingu }
        : { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy },
  });
}

export function interpretAdvancedMetric(
  metric: "median_dom" | "drop_share" | "price_change",
  current: number | null,
  previous: number | null,
  labelKey: "medianDom" | "dropShare" | "priceChange"
): KpiInterpretation | null {
  const meaning = cs.kpiInterpret.advanced[labelKey].vyznam;
  const nextStep = cs.kpiInterpret.advanced.dalsi;
  const nextStepLink = { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy };

  const cls = classifyPeriodChange(current, previous);

  if (cls.state === "insufficient_history") {
    // Distinguish "no value yet" from "value but no prior snapshot".
    const noValue = current == null;
    return buildInterpretation({
      state: "insufficient_history",
      confidence: "low",
      sentiment: noValue ? "unavailable" : "neutral",
      comparison: { kind: "none" },
      meaning,
      detail: noValue
        ? cs.kpiInterpret.bezHistorieSnapshotu
        : cs.kpiInterpret.bezPredchozihoSnapshotu,
      nextStep: noValue ? undefined : nextStep,
      nextStepLink: noValue ? undefined : nextStepLink,
    });
  }

  if (cls.state === "baseline") {
    return buildInterpretation({
      state: "baseline",
      confidence: "low",
      sentiment: "unavailable",
      comparison: { kind: "previous_snapshot" },
      meaning,
      detail: cs.kpiInterpret.advanced.baselineNesrovnatelny,
      nextStep,
      nextStepLink,
    });
  }

  const delta = cls.deltaPct ?? 0;
  let sentiment: KpiDirection = "stable";
  if (metric === "drop_share") sentiment = sentimentFromDelta(delta, { watchAbove: 15, healthyBelow: -15 });
  else if (metric === "median_dom") sentiment = sentimentFromDelta(delta, { watchAbove: 10, healthyBelow: -10 });
  else sentiment = sentimentFromDelta(delta, { watchAbove: 5, concernBelow: -5 });

  return buildInterpretation({
    state: "trend",
    confidence: "medium",
    sentiment,
    comparison: { kind: "previous_snapshot" },
    meaning,
    detail: cs.kpiInterpret.advanced.srovnaniSnapshot.replace("{delta}", fmtPct(delta)),
    nextStep,
    nextStepLink,
  });
}

/** Average price_drop_share from latest snapshot date aggregates. */
export function latestAvgDropShare(snapshots: MarketDynamicsSnapshot[]): number | null {
  const agg = aggregateSnapshotsByDate(snapshots);
  const pair = latestTwoSnapshotDates(agg);
  if (!pair) return null;
  return avg(pair.latest.price_drop_shares);
}
