import { cs } from "../locale/cs";
import { pctChange } from "./benchmarks";
import type { KpiConfidence, KpiDirection, KpiInterpretation, KpiState } from "./types";

export type { KpiConfidence, KpiState } from "./types";

/**
 * Formal KPI interpretation model.
 *
 * The problem this solves: a raw value plus a period-over-period delta is not
 * automatically a market signal. When the local dataset is being (re)built, a
 * delta of "+5647 %" is an ingestion artifact, not the market. This model makes
 * the *interpretability* of each KPI explicit and separate from its raw value,
 * so a KPI can never silently present an artifact as a trend.
 *
 * Every KPI reading separates four concerns:
 *   1. raw value          — owned by the KPI card, always truthful, never hidden
 *   2. comparison basis    — what (if anything) the value is compared against
 *   3. interpretability    — {@link KpiState} + {@link KpiConfidence}
 *   4. Czech explanation   — meaning + a state-aware detail sentence
 */

/** What kind of reference the value is compared against, if anything. */
export type KpiComparisonKind = "none" | "previous_snapshot" | "share_of_total" | "period_flow";

/** What the value is compared against. `label` is an optional Czech descriptor
 *  of the reference (e.g. the previous snapshot's date). */
export interface KpiComparisonBasis {
  kind: KpiComparisonKind;
  label?: string;
}

/** The full, state-explicit reading a KPI produces. Rendered compactly by
 *  {@link ../components/kpi/KpiInterpretationLine}. */
export interface KpiReading {
  state: KpiState;
  confidence: KpiConfidence;
  /** Directional sentiment — drives only the badge tone/label. Constrained by
   *  state: non-"trend" states must not carry an alarming sentiment. */
  sentiment: KpiDirection;
  comparison: KpiComparisonBasis;
  /** Czech: what the metric means (one short sentence). */
  meaning: string;
  /** Czech: the state-aware comparison/benchmark sentence. */
  detail?: string;
  nextStep?: string;
  nextStepLink?: { to: string; label: string };
}

// Period-over-period swings above this magnitude are not real market movement —
// they're the dataset being (re)built (demo sample -> full scrape). Such a
// comparison is downgraded to a baseline instead of a trend. Single source of
// truth for every KPI that compares two snapshots.
export const IMPLAUSIBLE_MARKET_DELTA_PCT = 40;

/** Result of classifying a two-snapshot comparison for interpretability. */
export interface PeriodClassification {
  state: Extract<KpiState, "trend" | "baseline" | "insufficient_history">;
  confidence: KpiConfidence;
  /** Signed % change, or null when it can't be computed. */
  deltaPct: number | null;
}

/**
 * The reusable guard (requirement: never present implausible period-over-period
 * changes as market movement without sufficient baseline quality).
 *
 * - missing current/previous / previous == 0  -> insufficient_history
 * - |delta| over the plausibility ceiling      -> baseline (dataset rebuild)
 * - otherwise                                  -> trend
 */
export function classifyPeriodChange(
  current: number | null | undefined,
  previous: number | null | undefined,
  opts: { implausibleAbovePct?: number } = {}
): PeriodClassification {
  const ceiling = opts.implausibleAbovePct ?? IMPLAUSIBLE_MARKET_DELTA_PCT;
  if (current == null || previous == null) {
    return { state: "insufficient_history", confidence: "low", deltaPct: null };
  }
  const delta = pctChange(current, previous);
  if (delta == null) {
    return { state: "insufficient_history", confidence: "low", deltaPct: null };
  }
  if (Math.abs(delta) > ceiling) {
    return { state: "baseline", confidence: "low", deltaPct: delta };
  }
  return { state: "trend", confidence: "medium", deltaPct: delta };
}

/** Snapshot dates arrive as ISO "YYYY-MM-DD"; render them in Czech so they match
 *  the rest of the UI ("2. 7. 2026") rather than leaking a raw ISO string. */
export function fmtSnapshotDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("cs-CZ");
}

/** Short Czech chip shown next to the sentiment badge when interpretability is
 *  reduced — keeps the "this isn't a clean trend" caveat compact and consistent.
 *  Returns null when no caveat is needed (clean trend or high-confidence fact). */
export function stateChipLabel(state: KpiState, confidence: KpiConfidence): string | null {
  switch (state) {
    case "baseline":
      return cs.kpiInterpret.stavChip.baseline;
    case "ingest_dominated":
      return cs.kpiInterpret.stavChip.ingestDominated;
    case "insufficient_history":
      return cs.kpiInterpret.stavChip.malaHistorie;
    case "informational":
    case "trend":
      return confidence === "low" ? cs.kpiInterpret.stavChip.orientacni : null;
    default:
      return null;
  }
}

/** Build the render-facing {@link KpiInterpretation} from a {@link KpiReading}.
 *  Centralises sentiment-label resolution and derives the legacy `limited`
 *  flag, so call sites never touch label maps directly. */
export function buildInterpretation(reading: KpiReading): KpiInterpretation {
  return {
    meaning: reading.meaning,
    benchmark: reading.detail,
    direction: reading.sentiment,
    directionLabel: cs.kpiInterpret.smery[reading.sentiment],
    nextStep: reading.nextStep,
    nextStepLink: reading.nextStepLink,
    state: reading.state,
    confidence: reading.confidence,
    limited: reading.confidence !== "high",
  };
}
