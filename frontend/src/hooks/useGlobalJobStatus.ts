import { useEffect, useState } from "react";
import { api } from "../api/client";
import { cs } from "../locale/cs";
import { useAsync } from "./useAsync";
import { isDatasetInProgress, useDatasetSummary } from "./useDatasetSummary";

const POLL_MS = 20_000;

export type GlobalJobStatus = {
  scraping: boolean;
  recompute: boolean;
  active: boolean;
  label: string | null;
  linkTo: "/sprava-scrapingu" | "/pokrocile-analyzy";
};

/** Lightweight global view of background scraping and analytics recompute jobs. */
export function useGlobalJobStatus(): GlobalJobStatus {
  const summary = useDatasetSummary();
  const [pollKey, setPollKey] = useState(0);

  const analyticsRuns = useAsync(() => api.advanced.runs(5), [pollKey]);
  const scrapingRuns = useAsync(() => api.scrapingRuns(5), [pollKey]);

  const scraping =
    isDatasetInProgress(summary.data) ||
    (scrapingRuns.data?.some((r) => r.status === "running") ?? false);
  const recompute = analyticsRuns.data?.some((r) => r.status === "running") ?? false;
  const active = scraping || recompute;

  useEffect(() => {
    if (!active) {
      return;
    }
    const id = window.setInterval(() => setPollKey((k) => k + 1), POLL_MS);
    return () => window.clearInterval(id);
  }, [active]);

  let label: string | null = null;
  if (scraping && recompute) {
    label = cs.jobs.scrapingARecompute;
  } else if (scraping) {
    label = cs.jobs.scraping;
  } else if (recompute) {
    label = cs.jobs.recompute;
  }

  const linkTo = scraping ? "/sprava-scrapingu" : "/pokrocile-analyzy";

  return { scraping, recompute, active, label, linkTo };
}
