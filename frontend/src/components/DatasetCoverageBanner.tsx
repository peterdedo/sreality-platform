import type { DatasetSummary } from "../api/types";
import { cs } from "../locale/cs";
import { formatDate } from "../constants";
import { DatasetSnapshotIndicator } from "./DatasetSnapshotIndicator";
import { StatusBanner } from "./ui/primitives";
import { isDatasetInProgress } from "../hooks/useDatasetSummary";

type Props = {
  summary: DatasetSummary;
  context?: "default" | "map";
  mapLoadedCount?: number;
  /** When true, long explanatory copy moves into a collapsible section. Warnings stay visible. */
  collapsible?: boolean;
};

function InProgressScrapeBanner({ summary }: { summary: DatasetSummary }) {
  const run = summary.running_scrape;
  if (!isDatasetInProgress(summary) || !run) {
    return null;
  }
  const text = cs.dataset.probihaScraping
    .replace("{runId}", String(run.id))
    .replace("{itemsSeen}", run.items_seen.toLocaleString("cs-CZ"))
    .replace("{pagesFetched}", run.pages_fetched.toLocaleString("cs-CZ"))
    .replace("{activeCount}", summary.active_listing_count.toLocaleString("cs-CZ"));
  return <StatusBanner variant="info">{text}</StatusBanner>;
}

function IncompleteDatasetWarning({ summary }: { summary: DatasetSummary }) {
  if (isDatasetInProgress(summary)) {
    return null;
  }
  if (summary.dataset_completeness !== "partial") {
    return null;
  }
  const sliceCount = summary.active_category_slice_count ?? 0;
  const expected = summary.expected_category_slice_count ?? 20;
  const text = cs.dataset.nekompletniDatasetBezSreality
    .replace("{activeCount}", String(summary.active_listing_count))
    .replace("{sliceCount}", String(sliceCount))
    .replace("{expectedSlices}", String(expected));
  return <StatusBanner variant="warning">{text}</StatusBanner>;
}

function finalScrapeLabel(summary: DatasetSummary): string {
  if (isDatasetInProgress(summary)) {
    return cs.dataset.probihaScrapingKratce.replace(
      "{runId}",
      String(summary.running_scrape?.id ?? "?")
    );
  }
  if (summary.dataset_freshness === "final_complete" && summary.last_full_sweep_at) {
    return `${cs.dataset.posledniUplnySweep}: ${formatDate(summary.last_full_sweep_at)}`;
  }
  if (summary.last_successful_scrape_at) {
    return `${cs.dataset.posledniUspesnyBeh}: ${formatDate(summary.last_successful_scrape_at)}`;
  }
  return cs.dataset.neznamePosledniScrape;
}

function ContextParagraph({
  summary,
  context,
  mapLoadedCount,
}: {
  summary: DatasetSummary;
  context: "default" | "map";
  mapLoadedCount?: number;
}) {
  const scrapeLabel = finalScrapeLabel(summary);

  if (context === "map" && mapLoadedCount !== undefined) {
    return (
      <p className="map-context-note">
        {cs.dataset.mapPoznamka
          .replace("{mapCount}", String(mapLoadedCount))
          .replace("{activeCount}", String(summary.active_listing_count))
          .replace("{withoutGps}", String(summary.active_without_gps_count))
          .replace("{lastScrape}", scrapeLabel)}
      </p>
    );
  }

  return (
    <p className="text-ink-muted/90 text-sm leading-relaxed">
      {isDatasetInProgress(summary)
        ? cs.dataset.poznamkaProbiha
            .replace("{activeCount}", String(summary.active_listing_count))
            .replace("{withRegion}", String(summary.active_with_region_count))
            .replace("{withGps}", String(summary.active_with_gps_count))
            .replace("{lastScrape}", scrapeLabel)
        : cs.dataset.poznamka
            .replace("{activeCount}", String(summary.active_listing_count))
            .replace("{withRegion}", String(summary.active_with_region_count))
            .replace("{withoutRegion}", String(summary.active_without_region_count))
            .replace("{withGps}", String(summary.active_with_gps_count))
            .replace("{lastScrape}", scrapeLabel)}
    </p>
  );
}

function CollapsibleContext({
  summary,
  context,
  mapLoadedCount,
}: {
  summary: DatasetSummary;
  context: "default" | "map";
  mapLoadedCount?: number;
}) {
  return (
    <details className="dataset-context-details">
      <summary className="dataset-context-details__summary">{cs.dataset.viceKontextu}</summary>
      <div className="dataset-context-details__body">
        <ContextParagraph summary={summary} context={context} mapLoadedCount={mapLoadedCount} />
        {summary.compare_guidance_cs && (
          <p className="text-xs text-ink-muted leading-relaxed mt-2">{summary.compare_guidance_cs}</p>
        )}
      </div>
    </details>
  );
}

export function DatasetCoverageBanner({
  summary,
  context = "default",
  mapLoadedCount,
  collapsible = true,
}: Props) {
  const regionWarning = summary.needs_region_backfill ? (
    <StatusBanner variant="warning">
      {cs.dataset.backfillUpozorneni.replace(
        "{revision}",
        summary.schema_revision ?? cs.dataset.backfillNeznameRevizi
      )}
    </StatusBanner>
  ) : null;

  const contextBlock = collapsible ? (
    <CollapsibleContext summary={summary} context={context} mapLoadedCount={mapLoadedCount} />
  ) : (
    <div className="mb-4">
      <ContextParagraph summary={summary} context={context} mapLoadedCount={mapLoadedCount} />
    </div>
  );

  return (
    <>
      <DatasetSnapshotIndicator summary={summary} essentialOnly={collapsible} />
      <InProgressScrapeBanner summary={summary} />
      <IncompleteDatasetWarning summary={summary} />
      {regionWarning}
      {contextBlock}
    </>
  );
}
