import { describe, expect, it } from "vitest";
import {
  buildInterpretation,
  classifyPeriodChange,
  IMPLAUSIBLE_MARKET_DELTA_PCT,
  stateChipLabel,
} from "./model";
import { cs } from "../locale/cs";

describe("classifyPeriodChange", () => {
  it("returns insufficient_history when there is no previous snapshot", () => {
    const result = classifyPeriodChange(105310, undefined);
    expect(result.state).toBe("insufficient_history");
    expect(result.deltaPct).toBeNull();
  });

  it("returns insufficient_history when current is missing", () => {
    const result = classifyPeriodChange(null, 100);
    expect(result.state).toBe("insufficient_history");
    expect(result.deltaPct).toBeNull();
  });

  it("returns insufficient_history when previous is zero (division undefined)", () => {
    const result = classifyPeriodChange(50, 0);
    expect(result.state).toBe("insufficient_history");
    expect(result.deltaPct).toBeNull();
  });

  it("classifies a plausible delta as trend", () => {
    // +5 % -- ordinary period movement.
    const result = classifyPeriodChange(105, 100);
    expect(result.state).toBe("trend");
    expect(result.confidence).toBe("medium");
    expect(result.deltaPct).toBeCloseTo(5, 5);
  });

  it("classifies a negative plausible delta as trend too", () => {
    const result = classifyPeriodChange(90, 100);
    expect(result.state).toBe("trend");
    expect(result.deltaPct).toBeCloseTo(-10, 5);
  });

  it("classifies a delta above IMPLAUSIBLE_MARKET_DELTA_PCT as baseline", () => {
    // Regression case: the original dashboard bug compared ~1.8k (demo era)
    // against 105 310 (post full-scrape) and rendered "+5647 %" as a trend.
    const result = classifyPeriodChange(105310, 1800);
    expect(result.state).toBe("baseline");
    expect(result.confidence).toBe("low");
    expect(result.deltaPct).toBeGreaterThan(IMPLAUSIBLE_MARKET_DELTA_PCT);
  });

  it("treats a delta exactly at the ceiling as still plausible (trend)", () => {
    // 100 -> 140 is exactly +40 %, the configured ceiling; only deltas
    // strictly greater than the ceiling are downgraded to baseline.
    const result = classifyPeriodChange(140, 100);
    expect(result.state).toBe("trend");
  });

  it("treats a delta just above the ceiling as baseline", () => {
    const result = classifyPeriodChange(140.01, 100);
    expect(result.state).toBe("baseline");
  });

  it("respects a custom implausibility ceiling", () => {
    const result = classifyPeriodChange(110, 100, { implausibleAbovePct: 5 });
    expect(result.state).toBe("baseline");
  });
});

describe("buildInterpretation", () => {
  it("maps a trend reading through unchanged, with correct direction label", () => {
    const interp = buildInterpretation({
      state: "trend",
      confidence: "medium",
      sentiment: "watch",
      comparison: { kind: "previous_snapshot", label: "2. 7. 2026" },
      meaning: "Kolik inzerátů je právě aktivních.",
      detail: "Oproti předchozímu snapshotu (2. 7. 2026): +5,0 %.",
      nextStep: "Prohlédněte nabídky",
      nextStepLink: { to: "/nabidky", label: "Nabídky" },
    });

    expect(interp.meaning).toBe("Kolik inzerátů je právě aktivních.");
    expect(interp.benchmark).toBe("Oproti předchozímu snapshotu (2. 7. 2026): +5,0 %.");
    expect(interp.direction).toBe("watch");
    expect(interp.directionLabel).toBe(cs.kpiInterpret.smery.watch);
    expect(interp.state).toBe("trend");
    expect(interp.confidence).toBe("medium");
    expect(interp.nextStep).toBe("Prohlédněte nabídky");
    expect(interp.nextStepLink).toEqual({ to: "/nabidky", label: "Nabídky" });
  });

  it.each([
    ["high", false],
    ["medium", true],
    ["low", true],
  ] as const)("derives limited=%s for confidence=%s", (confidence, expectedLimited) => {
    const interp = buildInterpretation({
      state: "informational",
      confidence,
      sentiment: "neutral",
      comparison: { kind: "none" },
      meaning: "x",
    });
    expect(interp.limited).toBe(expectedLimited);
  });

  it("resolves the Czech direction label for every sentiment used by the model", () => {
    const sentiments = ["healthy", "stable", "neutral", "watch", "concern", "unavailable", "partial"] as const;
    for (const sentiment of sentiments) {
      const interp = buildInterpretation({
        state: "informational",
        confidence: "high",
        sentiment,
        comparison: { kind: "none" },
        meaning: "x",
      });
      expect(interp.directionLabel).toBe(cs.kpiInterpret.smery[sentiment]);
    }
  });
});

describe("stateChipLabel", () => {
  it('returns "Bez trendu" for baseline', () => {
    expect(stateChipLabel("baseline", "low")).toBe("Bez trendu");
    expect(stateChipLabel("baseline", "low")).toBe(cs.kpiInterpret.stavChip.baseline);
  });

  it('returns "Vliv importu" for ingest_dominated', () => {
    expect(stateChipLabel("ingest_dominated", "low")).toBe("Vliv importu");
    expect(stateChipLabel("ingest_dominated", "low")).toBe(cs.kpiInterpret.stavChip.ingestDominated);
  });

  it('returns "Málo historie" for insufficient_history', () => {
    expect(stateChipLabel("insufficient_history", "low")).toBe("Málo historie");
    expect(stateChipLabel("insufficient_history", "low")).toBe(cs.kpiInterpret.stavChip.malaHistorie);
  });

  it('returns "Orientační" for informational + low confidence', () => {
    expect(stateChipLabel("informational", "low")).toBe("Orientační");
    expect(stateChipLabel("informational", "low")).toBe(cs.kpiInterpret.stavChip.orientacni);
  });

  it("returns null for informational + high confidence (no caveat needed)", () => {
    expect(stateChipLabel("informational", "high")).toBeNull();
  });

  it('returns "Orientační" for trend + low confidence', () => {
    expect(stateChipLabel("trend", "low")).toBe("Orientační");
  });

  it("returns null for a clean trend at high or medium confidence", () => {
    expect(stateChipLabel("trend", "high")).toBeNull();
    expect(stateChipLabel("trend", "medium")).toBeNull();
  });
});
