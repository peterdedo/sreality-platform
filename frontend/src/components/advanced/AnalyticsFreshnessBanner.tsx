import { Link } from "react-router-dom";
import type { AnalyticsRunRow, DatasetSummary } from "../../api/types";
import { formatDate } from "../../constants";
import { cs } from "../../locale/cs";
import { isDatasetInProgress } from "../../hooks/useDatasetSummary";
import { StatusBanner } from "../ui/primitives";

type Props = {
  runs: AnalyticsRunRow[] | null;
  summary: DatasetSummary | null;
};

/** Compares the last successful advanced-analytics recompute against the last
 * dataset update (scrape or detail backfill) so operators know when to rerun. */
export function AnalyticsFreshnessBanner({ runs, summary }: Props) {
  if (!runs || !summary) {
    return null;
  }

  const activeCount = summary.active_listing_count;
  const missingDetail = Math.max(0, activeCount - summary.active_with_detail_count);

  const running = runs.find((r) => r.status === "running");
  if (running) {
    return <StatusBanner variant="info">{cs.advanced.freshness.probihaPrepocet}</StatusBanner>;
  }

  if (isDatasetInProgress(summary)) {
    return (
      <StatusBanner variant="info">
        {cs.advanced.freshness.probihaScrapingAkce}{" "}
        <Link to="/sprava-scrapingu" className="link-brand font-semibold">
          {cs.nav.spravaScrapingu}
        </Link>
      </StatusBanner>
    );
  }

  if (missingDetail > 0 && activeCount > 0) {
    return (
      <StatusBanner variant="warning">
        {cs.advanced.freshness.chybiDetaily.replace("{missing}", String(missingDetail))}{" "}
        {cs.advanced.freshness.chybiDetailyAkce}{" "}
        <Link to="/sprava-scrapingu" className="link-brand font-semibold">
          {cs.nav.spravaScrapingu}
        </Link>
      </StatusBanner>
    );
  }

  const lastGood = runs.find((r) => r.status === "success" || r.status === "partial");
  if (!lastGood || !lastGood.finished_at) {
    return (
      <StatusBanner variant="warning">
        {cs.advanced.freshness.zadnyPrepocet} {cs.advanced.freshness.zadnyPrepocetAkce}
      </StatusBanner>
    );
  }

  const datasetReference =
    summary.last_dataset_update_at ?? summary.last_full_sweep_at ?? summary.last_successful_scrape_at;
  if (!datasetReference) {
    return null;
  }

  const analyticsAt = new Date(lastGood.finished_at).getTime();
  const datasetAt = new Date(datasetReference).getTime();
  const isStale = analyticsAt < datasetAt;

  if (lastGood.status === "partial") {
    return (
      <StatusBanner variant="warning">
        {cs.advanced.freshness.castecnyPrepocet
          .replace("{date}", formatDate(lastGood.finished_at))
          .replace("{errors}", String(lastGood.error_count))}
      </StatusBanner>
    );
  }

  if (isStale) {
    return (
      <StatusBanner variant="warning">
        {cs.advanced.freshness.zastaraly
          .replace("{analyticsDate}", formatDate(lastGood.finished_at))
          .replace("{datasetDate}", formatDate(datasetReference))}{" "}
        {cs.advanced.freshness.zastaralyAkce}
      </StatusBanner>
    );
  }

  return (
    <StatusBanner variant="success">
      {cs.advanced.freshness.aktualni.replace("{date}", formatDate(lastGood.finished_at))}
    </StatusBanner>
  );
}
