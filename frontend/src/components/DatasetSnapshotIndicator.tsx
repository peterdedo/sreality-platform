import type { DatasetSummary } from "../api/types";
import { cs } from "../locale/cs";
import { formatDate } from "../constants";
import { freshnessBadgeClass } from "../theme/status";

type Props = {
  summary: DatasetSummary;
  compact?: boolean;
  /** Hide compare guidance in the strip — shown in collapsible dataset context instead. */
  essentialOnly?: boolean;
};

export function DatasetSnapshotIndicator({ summary, compact = false, essentialOnly = false }: Props) {
  const freshness = summary.dataset_freshness ?? "empty";
  const label =
    summary.snapshot_state_label_cs ??
    cs.dataset.stavSnapshotu[freshness as keyof typeof cs.dataset.stavSnapshotu] ??
    freshness;
  const updated = summary.last_dataset_update_at
    ? formatDate(summary.last_dataset_update_at)
    : cs.dataset.neznamePosledniScrape;

  if (compact) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted mb-3">
        <span className={freshnessBadgeClass(freshness)}>{label}</span>
        <span>
          {cs.dataset.aktualizaceSnapshotu}: {updated}
          {summary.running_scrape ? ` · ${cs.dataset.behCislo.replace("{runId}", String(summary.running_scrape.id))}` : ""}
          {summary.running_detail_backfill && !summary.running_scrape
            ? ` · ${cs.dataset.behCislo.replace("{runId}", String(summary.running_detail_backfill.id))}`
            : ""}
        </span>
      </div>
    );
  }

  return (
    <div className="snapshot-strip">
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <span className={freshnessBadgeClass(freshness)}>{label}</span>
        <span className="text-ink-muted text-xs">
          {cs.dataset.aktualizaceSnapshotu}: <strong className="text-ink font-semibold">{updated}</strong>
        </span>
        {summary.running_scrape && (
          <span className="text-ink-muted text-xs">
            · {cs.dataset.behCislo.replace("{runId}", String(summary.running_scrape.id))}
            · {summary.running_scrape.items_seen.toLocaleString("cs-CZ")} {cs.dataset.zpracovanoPolozek}
          </span>
        )}
        {summary.running_detail_backfill && !summary.running_scrape && (
          <span className="text-ink-muted text-xs">
            · {cs.dataset.behCislo.replace("{runId}", String(summary.running_detail_backfill.id))}
            · {summary.running_detail_backfill.items_seen.toLocaleString("cs-CZ")} {cs.dataset.zpracovanoPolozek}
          </span>
        )}
      </div>
      {summary.compare_guidance_cs && !essentialOnly && (
        <p className="text-xs text-ink-muted leading-relaxed">{summary.compare_guidance_cs}</p>
      )}
      {summary.safe_to_compare_with_sreality_total === false && freshness === "in_progress" && (
        <p className="text-xs text-brand mt-1.5 font-medium">{cs.dataset.neniBezpecnePorovnatSreality}</p>
      )}
    </div>
  );
}
