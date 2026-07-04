import type { MarketDynamicsSnapshot } from "../../api/types";
import { formatPercent, formatPercentPlain } from "../../constants";
import { cs } from "../../locale/cs";
import {
  aggregateSnapshotsByDate,
  avg,
  latestTwoSnapshotDates,
} from "../../kpi/benchmarks";
import {
  interpretAdvancedMetric,
} from "../../kpi/interpret";
import { KpiCard } from "../ui/primitives";

function latestBySegment(snapshots: MarketDynamicsSnapshot[]): MarketDynamicsSnapshot[] {
  const bySegment = new Map<string, MarketDynamicsSnapshot>();
  for (const s of snapshots) {
    const key = `${s.category_main_cb}_${s.category_type_cb}`;
    const existing = bySegment.get(key);
    if (!existing || s.snapshot_date > existing.snapshot_date) {
      bySegment.set(key, s);
    }
  }
  return [...bySegment.values()];
}

type Props = {
  snapshots: MarketDynamicsSnapshot[];
  activeListingCount?: number;
};

export function KpiCardsAdvanced({ snapshots, activeListingCount }: Props) {
  const latest = latestBySegment(snapshots);

  const segmentActiveSum = latest.reduce((sum, s) => sum + s.listing_count, 0);
  const totalActive = activeListingCount ?? segmentActiveSum;

  const domValues = latest.map((s) => s.median_days_on_market).filter((v): v is number => v !== null);
  const medianDom = domValues.length ? Math.round(domValues.reduce((a, b) => a + b, 0) / domValues.length) : null;

  const dropShares = latest.map((s) => s.price_drop_share).filter((v): v is number => v !== null);
  const avgDropShare = dropShares.length ? dropShares.reduce((a, b) => a + b, 0) / dropShares.length : null;

  const changePcts = latest
    .map((s) => s.median_first_to_last_price_change_pct)
    .filter((v): v is number => v !== null);
  const medianChangePct = changePcts.length
    ? changePcts.reduce((a, b) => a + b, 0) / changePcts.length
    : null;

  const agg = aggregateSnapshotsByDate(snapshots);
  const pair = latestTwoSnapshotDates(agg);
  const prevDom = pair?.previous ? avg(pair.previous.median_days) : null;
  const prevDrop = pair?.previous ? avg(pair.previous.price_drop_shares) : null;
  const curDom = pair ? avg(pair.latest.median_days) : null;
  const curDrop = pair ? avg(pair.latest.price_drop_shares) : null;

  const cards = [
    {
      label: cs.advanced.kpi.aktivniInzeraty,
      value: totalActive.toLocaleString("cs-CZ"),
      tone: "brand" as const,
      interpretation: undefined,
    },
    {
      label: cs.advanced.kpi.medianDnuNaTrhu,
      value: medianDom !== null ? `${medianDom} dní` : "—",
      tone: "default" as const,
      interpretation:
        interpretAdvancedMetric("median_dom", curDom, prevDom, "medianDom") ?? undefined,
    },
    {
      label: cs.advanced.kpi.podilSnizeniCeny,
      value: avgDropShare !== null ? formatPercentPlain(avgDropShare * 100, 0) : "—",
      tone: "accent" as const,
      interpretation:
        interpretAdvancedMetric("drop_share", curDrop, prevDrop, "dropShare") ?? undefined,
    },
    {
      label: cs.advanced.kpi.medianZmenyCeny,
      value: formatPercent(medianChangePct),
      tone: "default" as const,
      interpretation:
        interpretAdvancedMetric("price_change", medianChangePct, null, "priceChange") ?? undefined,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {cards.map((c) => (
        <KpiCard
          key={c.label}
          label={c.label}
          value={c.value}
          tone={c.tone}
          interpretation={c.interpretation}
        />
      ))}
    </div>
  );
}
