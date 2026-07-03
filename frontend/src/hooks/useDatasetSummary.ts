import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DatasetSummary } from "../api/types";
import { useAsync } from "./useAsync";
import { invalidateQueryCache, readQueryCache, writeQueryCache } from "./queryCache";

const CACHE_KEY = "dataset-summary";
const CACHE_TTL_MS = 12_000;
const POLL_MS = 30_000;

/** Dataset summary with short-lived cache + auto-refresh while a scrape is in progress. */
export function useDatasetSummary() {
  const [pollKey, setPollKey] = useState(0);
  const cached = readQueryCache<DatasetSummary>(CACHE_KEY);

  const summary = useAsync(async () => {
    const data = await api.datasetSummary();
    writeQueryCache(CACHE_KEY, data, CACHE_TTL_MS);
    return data;
  }, [pollKey]);

  // Seed from cache on first paint so navigation feels instant.
  const data = summary.data ?? cached;
  const loading = summary.loading && data === null;
  const refreshing = summary.refreshing;

  useEffect(() => {
    if (data?.dataset_freshness !== "in_progress") {
      return;
    }
    const id = window.setInterval(() => {
      invalidateQueryCache(CACHE_KEY);
      setPollKey((k) => k + 1);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [data?.dataset_freshness]);

  return { ...summary, data, loading, refreshing };
}

export function isDatasetCountFinal(summary: DatasetSummary | null | undefined): boolean {
  return summary?.is_count_final === true;
}

export function isDatasetInProgress(summary: DatasetSummary | null | undefined): boolean {
  return summary?.dataset_freshness === "in_progress";
}
