import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { RunItemLog, ScrapingRun } from "../api/types";
import { DatasetCoverageBanner } from "../components/DatasetCoverageBanner";
import { PageContainer } from "../components/layout/PageContainer";
import { ErrorState, LoadingState } from "../components/StateHelpers";
import { useAsync } from "../hooks/useAsync";
import { useDatasetSummary } from "../hooks/useDatasetSummary";
import { cs } from "../locale/cs";
import { formatDate } from "../constants";
import { StatusBanner, Panel } from "../components/ui/primitives";
import { RefreshIndicator } from "../components/ui/RefreshIndicator";
import { runStatusPill, successBanner } from "../theme/status";

const POLL_MS = 15_000;

const RUN_TYPE_LABELS: Record<string, string> = {
  full: "Plný",
  incremental: "Přírůstkový",
  detail_backfill: "Doplnění detailů",
};

const STATUS_LABELS: Record<string, string> = {
  running: "Probíhá",
  success: "Úspěch",
  failed: "Selhal",
  partial: "Částečně úspěšný",
};

function RunItemsPanel({ runId, errorCount }: { runId: number; errorCount: number }) {
  const { data, loading, error } = useAsync(() => api.scrapingRunItems(runId), [runId]);

  if (loading) return <p className="text-sm text-ink-muted/70 px-3 py-2">{cs.scraping.nacitaniChyb}</p>;
  if (error) return <ErrorState message={error.message} />;
  if (!data || data.length === 0) {
    return <p className="text-sm text-ink-muted/70 px-3 py-2">{cs.scraping.zadneChybyNacteny}</p>;
  }

  const truncated = errorCount > data.length;

  return (
    <>
      {truncated && (
        <p className="text-xs text-amber-800 px-3 py-2">
          {cs.scraping.chybyLimitApi
            .replace("{shown}", String(data.length))
            .replace("{total}", String(errorCount))}
        </p>
      )}
      <table className="min-w-full text-xs">
        <thead className="text-ink-muted uppercase">
          <tr>
            <th className="text-left px-3 py-1">{cs.scraping.polozka}</th>
            <th className="text-left px-3 py-1">{cs.scraping.faze}</th>
            <th className="text-left px-3 py-1">{cs.scraping.zprava}</th>
            <th className="text-left px-3 py-1">{cs.scraping.cas}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border">
          {data.map((item: RunItemLog) => (
            <tr key={item.id}>
              <td className="px-3 py-1 font-mono">{item.hash_id ?? "—"}</td>
              <td className="px-3 py-1">
                {cs.scraping.fazeLabels[item.stage as keyof typeof cs.scraping.fazeLabels] ?? item.stage}
              </td>
              <td className="px-3 py-1 text-ink">{item.message}</td>
              <td className="px-3 py-1 text-ink-muted/70">{formatDate(item.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function activeBackfillRun(runs: ScrapingRun[] | null | undefined): ScrapingRun | undefined {
  return runs?.find((r) => r.status === "running" && r.run_type === "detail_backfill");
}

export function SpravaScrapingu() {
  const [message, setMessage] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [pollKey, setPollKey] = useState(0);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const { data, loading, error, refreshing } = useAsync(() => api.scrapingRuns(50), [refreshKey, pollKey]);
  const summary = useDatasetSummary();

  const hasRunning = data?.some((r) => r.status === "running") ?? false;
  const backfillRun = activeBackfillRun(data);
  const shouldPollSummary = hasRunning || summary.data?.dataset_freshness === "in_progress";

  useEffect(() => {
    if (!shouldPollSummary) return;
    const id = window.setInterval(() => setPollKey((k) => k + 1), POLL_MS);
    return () => window.clearInterval(id);
  }, [shouldPollSummary]);

  const activeCount = summary.data?.active_listing_count ?? 0;
  const withDetail = summary.data?.active_with_detail_count ?? 0;
  const missingDetail = Math.max(0, activeCount - withDetail);

  async function handleTrigger() {
    setMessage(null);
    try {
      const res = await api.triggerScraping();
      setMessage(res.message ?? cs.scraping.spusteno);
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Chyba");
    }
  }

  async function handleBackfillDetails() {
    setMessage(null);
    try {
      const res = await api.triggerMissingDetailBackfill();
      setMessage(res.message ?? cs.scraping.doplnitDetailySpusteno);
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Chyba");
    }
  }

  return (
    <PageContainer
      title={cs.scraping.titulek}
      actions={
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={handleBackfillDetails} title={cs.scraping.doplnitDetailyPoznamka}>
            {cs.scraping.doplnitDetaily}
          </button>
          <button className="btn-primary" onClick={handleTrigger}>
            {cs.scraping.spustitScraping}
          </button>
        </div>
      }
    >
      {summary.data && <DatasetCoverageBanner summary={summary.data} />}
      <RefreshIndicator active={refreshing || summary.refreshing} />
      {message && <div className={successBanner}>{message}</div>}
      <p className="text-xs text-ink-muted mb-3 max-w-2xl">{cs.scraping.doplnitDetailyPoznamka}</p>

      {activeCount > 0 && (
        <StatusBanner variant="neutral">
          {cs.scraping.pokrytiDetailu
            .replace("{withDetail}", String(withDetail))
            .replace("{active}", String(activeCount))
            .replace("{missing}", String(missingDetail))}
        </StatusBanner>
      )}

      {backfillRun && (
        <StatusBanner variant="info">
          {cs.scraping.backfillProbiha
            .replace("{runId}", String(backfillRun.id))
            .replace("{itemsSeen}", String(backfillRun.items_seen))}
        </StatusBanner>
      )}

      {missingDetail === 0 && activeCount > 0 && !backfillRun && (
        <StatusBanner variant="success">
          {cs.scraping.dalsiKrokAnalytics}{" "}
          <Link to="/pokrocile-analyzy" className="link-brand font-semibold">
            {cs.nav.pokroziteAnalyzy}
          </Link>
        </StatusBanner>
      )}

      <Panel title={cs.scraping.historieBehu} staticHover>
      {loading && !data && <LoadingState />}
      {error && <ErrorState message={error.message} />}
      {data && (
        <div className="data-table-shell -mx-1">
          <table className="data-table text-sm">
            <thead>
              <tr>
                <th className="text-left px-3 py-2">{cs.scraping.typBehu}</th>
                <th className="text-left px-3 py-2">{cs.scraping.stav}</th>
                <th className="text-left px-3 py-2">{cs.scraping.zahajeno}</th>
                <th className="text-left px-3 py-2">{cs.scraping.dokonceno}</th>
                <th className="text-right px-3 py-2">{cs.scraping.stranekNacteno}</th>
                <th className="text-right px-3 py-2">{cs.scraping.polozekCelkem}</th>
                <th className="text-right px-3 py-2">{cs.scraping.novych}</th>
                <th className="text-right px-3 py-2">{cs.scraping.aktualizovanych}</th>
                <th className="text-right px-3 py-2">{cs.scraping.stazenych}</th>
                <th className="text-right px-3 py-2">{cs.scraping.chyb}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((run) => (
                <Fragment key={run.id}>
                  <tr>
                    <td className="px-3 py-2">{RUN_TYPE_LABELS[run.run_type] ?? run.run_type}</td>
                    <td className="px-3 py-2">
                      <span className={runStatusPill(run.status)}>{STATUS_LABELS[run.status] ?? run.status}</span>
                    </td>
                    <td className="px-3 py-2">{formatDate(run.started_at)}</td>
                    <td className="px-3 py-2">{run.finished_at ? formatDate(run.finished_at) : "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{run.pages_fetched}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-medium">{run.items_seen}</td>
                    <td className="px-3 py-2 text-right text-accent">{run.items_new}</td>
                    <td className="px-3 py-2 text-right text-brand">{run.items_updated}</td>
                    <td className="px-3 py-2 text-right text-danger">{run.items_removed}</td>
                    <td className="px-3 py-2 text-right">
                      {run.error_count > 0 ? (
                        <button className="link-brand" onClick={() => setExpandedRunId(expandedRunId === run.id ? null : run.id)}>
                          {run.error_count} · {expandedRunId === run.id ? cs.scraping.skrytChyby : cs.scraping.zobrazitChyby}
                        </button>
                      ) : (
                        run.error_count
                      )}
                    </td>
                  </tr>
                  {run.error_message && (run.status === "partial" || run.status === "failed") && (
                    <tr>
                      <td colSpan={10} className="status-banner status-banner--warning !mb-0 !rounded-none text-xs border-x-0">
                        {run.error_message}
                      </td>
                    </tr>
                  )}
                  {expandedRunId === run.id && (
                    <tr>
                      <td colSpan={10} className="bg-surface-muted p-0">
                        <RunItemsPanel runId={run.id} errorCount={run.error_count} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </Panel>
    </PageContainer>
  );
}
