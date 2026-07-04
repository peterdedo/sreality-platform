import { Link } from "react-router-dom";
import type { AnalyticsRunRow, DatasetSummary, ScrapingRun } from "../api/types";
import { cs } from "../locale/cs";
import { isDatasetInProgress } from "../hooks/useDatasetSummary";
import { StatusBanner } from "./ui/primitives";

type Props = {
  summary: DatasetSummary;
  scrapingRuns?: ScrapingRun[] | null;
  analyticsRuns?: AnalyticsRunRow[] | null;
  /** Which page is showing the hint — wording adapts slightly. */
  context: "scraping" | "analytics";
};

function activeBackfillRun(runs: ScrapingRun[] | null | undefined): ScrapingRun | undefined {
  return runs?.find((r) => r.status === "running" && r.run_type === "detail_backfill");
}

/** Single clear next-action banner bridging Správa scrapingu ↔ Pokročilé analýzy. */
export function OperatorNextStep({ summary, scrapingRuns, analyticsRuns, context }: Props) {
  const activeCount = summary.active_listing_count;
  if (activeCount <= 0) {
    return null;
  }

  const missingDetail = Math.max(0, activeCount - summary.active_with_detail_count);
  const scraping = isDatasetInProgress(summary);
  const backfill = activeBackfillRun(scrapingRuns);
  const recomputeRunning = analyticsRuns?.some((r) => r.status === "running") ?? false;

  if (recomputeRunning && context === "analytics") {
    return null;
  }

  if (scraping && !backfill) {
    return (
      <StatusBanner variant="info">
        {cs.scraping.cekaScraping}{" "}
        <Link to="/sprava-scrapingu" className="link-brand font-semibold">
          {cs.nav.spravaScrapingu}
        </Link>
        {" · "}
        <Link to="/pokrocile-analyzy" className="link-brand font-semibold">
          {cs.nav.pokroziteAnalyzy}
        </Link>
      </StatusBanner>
    );
  }

  if (backfill) {
    return null;
  }

  if (missingDetail > 0 && context === "scraping") {
    return <StatusBanner variant="warning">{cs.scraping.dalsiKrokDetaily}</StatusBanner>;
  }

  if (missingDetail > 0 && context === "analytics") {
    return (
      <StatusBanner variant="warning">
        {cs.advanced.freshness.chybiDetaily.replace("{missing}", String(missingDetail))}{" "}
        <Link to="/sprava-scrapingu" className="link-brand font-semibold">
          {cs.nav.spravaScrapingu}
        </Link>
      </StatusBanner>
    );
  }

  if (missingDetail === 0 && context === "scraping" && !recomputeRunning) {
    return (
      <StatusBanner variant="success">
        {cs.scraping.dalsiKrokAnalytics}{" "}
        <Link to="/pokrocile-analyzy" className="link-brand font-semibold">
          {cs.nav.pokroziteAnalyzy}
        </Link>
      </StatusBanner>
    );
  }

  return null;
}
