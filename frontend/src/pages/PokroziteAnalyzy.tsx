import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { DatasetCoverageBanner } from "../components/DatasetCoverageBanner";
import { PageContainer } from "../components/layout/PageContainer";
import { KpiCardsAdvanced } from "../components/advanced/KpiCardsAdvanced";
import { SegmentComparisonCharts } from "../components/advanced/SegmentComparisonCharts";
import { ValuationTable } from "../components/advanced/ValuationTable";
import { AnomalyTable } from "../components/advanced/AnomalyTable";
import { SpatialHeatmap } from "../components/advanced/SpatialHeatmap";
import { ComparablesPanel } from "../components/advanced/ComparablesPanel";
import { MethodologyNotes } from "../components/advanced/MethodologyNotes";
import { ExportButton, type ExportScopeOption } from "../components/export/ExportButton";
import { AnalyticsFreshnessBanner } from "../components/advanced/AnalyticsFreshnessBanner";
import { ErrorState, LoadingState } from "../components/StateHelpers";
import { useDatasetSummary } from "../hooks/useDatasetSummary";
import { useAsync } from "../hooks/useAsync";
import { cs } from "../locale/cs";
import { formatDate } from "../constants";
import { Panel } from "../components/ui/primitives";
import { LazyMount } from "../components/ui/LazyMount";
import { RefreshIndicator } from "../components/ui/RefreshIndicator";
import { runStatusPill, successBanner } from "../theme/status";

const RUN_STATUS_LABELS: Record<string, string> = {
  running: "Probíhá",
  success: "Úspěch",
  failed: "Selhal",
  partial: "Částečně úspěšný",
};

const POLL_MS = 15_000;

export function PokroziteAnalyzy() {
  const [message, setMessage] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [pollKey, setPollKey] = useState(0);
  const [comparablesListingId, setComparablesListingId] = useState<string>("");

  const dynamics = useAsync(() => api.advanced.marketDynamics(180), [refreshKey]);
  const summary = useDatasetSummary();
  const runs = useAsync(() => api.advanced.runs(20), [refreshKey, pollKey]);

  const hasRunningRecompute = runs.data?.some((r) => r.status === "running") ?? false;

  useEffect(() => {
    if (!hasRunningRecompute) return;
    const id = window.setInterval(() => setPollKey((k) => k + 1), POLL_MS);
    return () => window.clearInterval(id);
  }, [hasRunningRecompute]);

  async function handleTrigger() {
    setMessage(null);
    try {
      const res = await api.advanced.triggerRecompute();
      setMessage(res.message ?? cs.advanced.prepocetSpusten);
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Chyba");
    }
  }

  const exportScopes: ExportScopeOption[] = [
    { value: "timeseries", label: cs.export.exportCasoveRady, run: (format) => api.export.timeseries(format, { days: 730 }) },
    { value: "aggregation", label: cs.export.exportAgregace, run: (format) => api.export.timeseries(format, { days: 730 }) },
    { value: "valuation", label: cs.export.exportOdhaduCeny, run: (format) => api.export.valuation(format, {}) },
  ];

  return (
    <PageContainer
      title={cs.advanced.titulek}
      actions={
        <div className="flex items-center gap-2">
          <ExportButton scopes={exportScopes} />
          <button
            className="btn-primary"
            onClick={handleTrigger}
          >
            {cs.advanced.prepocitat}
          </button>
        </div>
      }
    >
      <p className="text-ink-muted text-sm mb-4 max-w-3xl">{cs.advanced.podtitulek}</p>
      {summary.data && <DatasetCoverageBanner summary={summary.data} />}
      <AnalyticsFreshnessBanner runs={runs.data} summary={summary.data ?? null} />

      {summary.data && summary.data.active_listing_count > 0 && (
        <div className="operator-checklist max-w-3xl">
          <p className="operator-checklist__title">{cs.advanced.freshness.operatorPostupTitulek}</p>
          <ol className="list-decimal list-inside space-y-1.5">
            {cs.advanced.freshness.operatorPostup.map((step, i) => (
              <li key={i}>
                {i === 0 ? (
                  <>
                    {step}{" "}
                    <Link to="/sprava-scrapingu" className="link-brand">
                      {cs.nav.spravaScrapingu}
                    </Link>
                    .
                  </>
                ) : (
                  step
                    .replace(/\{withValuation\}/g, String(summary.data!.active_with_valuation_count))
                    .replace(/\{withAnomaly\}/g, String(summary.data!.active_with_anomaly_count))
                    .replace(/\{active\}/g, String(summary.data!.active_listing_count))
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      <p className="text-xs text-ink-muted mb-4 max-w-3xl">{cs.advanced.kpi.poznamkaDataset}</p>

      <RefreshIndicator active={summary.refreshing || runs.refreshing} />

      {message && <div className={successBanner}>{message}</div>}

      <div className="space-y-6">
        <section>
          {dynamics.loading && !dynamics.data && <LoadingState />}
          {dynamics.refreshing && <RefreshIndicator active />}
          {dynamics.error && <ErrorState message={dynamics.error.message} />}
          {dynamics.data && (
            <KpiCardsAdvanced snapshots={dynamics.data} activeListingCount={summary.data?.active_listing_count} />
          )}
        </section>

        <LazyMount minHeight={200}>
          <ValuationTable />
        </LazyMount>
        <LazyMount minHeight={200}>
          <AnomalyTable />
        </LazyMount>
        <LazyMount minHeight={240}>
          <SegmentComparisonCharts />
        </LazyMount>
        <LazyMount minHeight={320}>
          <SpatialHeatmap />
        </LazyMount>

        <Panel title={cs.advanced.srovnatelne.titulek}>
          <label className="field-label">ID nabídky</label>
          <input
            type="number"
            className="input-field w-48 mb-4"
            placeholder="např. 1"
            value={comparablesListingId}
            onChange={(e) => setComparablesListingId(e.target.value)}
          />
          {comparablesListingId && <ComparablesPanel listingId={Number(comparablesListingId)} />}
        </Panel>

        <MethodologyNotes />

        <Panel title={cs.advanced.historieVypoctu} staticHover>
          {runs.loading && <LoadingState />}
          {runs.error && <ErrorState message={runs.error.message} />}
          {runs.data && (
            <div className="data-table-shell -mx-1">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="text-left py-1">Typ</th>
                  <th className="text-left py-1">Stav</th>
                  <th className="text-left py-1">Zahájeno</th>
                  <th className="text-left py-1">Dokončeno</th>
                  <th className="text-right py-1">Zpracováno položek</th>
                  <th className="text-right py-1">Chyb</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((run) => (
                  <Fragment key={run.id}>
                    <tr>
                      <td className="py-1">{run.run_type}</td>
                      <td className="py-1">
                        <span className={runStatusPill(run.status)}>
                          {RUN_STATUS_LABELS[run.status] ?? run.status}
                        </span>
                      </td>
                      <td className="py-1">{formatDate(run.started_at)}</td>
                      <td className="py-1">{run.finished_at ? formatDate(run.finished_at) : "—"}</td>
                      <td className="py-1 text-right">{run.items_processed}</td>
                      <td className="py-1 text-right">{run.error_count}</td>
                    </tr>
                    {run.error_message && (run.status === "failed" || run.status === "partial") && (
                      <tr>
                        <td colSpan={6} className="status-banner status-banner--warning !mb-0 !rounded-none text-xs border-x-0">
                          {run.error_message}
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
      </div>
    </PageContainer>
  );
}
