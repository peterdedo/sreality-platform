import { api } from "../api/client";

import { PageContainer } from "../components/layout/PageContainer";

import { InventoryChart } from "../components/charts/InventoryChart";

import { DatasetCoverageBanner } from "../components/DatasetCoverageBanner";

import { ErrorState, LoadingState, EmptyState } from "../components/StateHelpers";

import { Panel } from "../components/ui/primitives";

import { LazyMount } from "../components/ui/LazyMount";

import { RefreshIndicator } from "../components/ui/RefreshIndicator";

import { useDatasetSummary } from "../hooks/useDatasetSummary";

import { useAsync, useCachedAsync } from "../hooks/useAsync";

import { cs } from "../locale/cs";

import { formatCzk } from "../constants";

const PRICE_DROPS_PREVIEW = 50;

export function Analytika() {
  const summary = useDatasetSummary();
  const inventory = useCachedAsync("inventory-by-region", () => api.inventoryByRegion(), []);
  const newVsRemoved = useCachedAsync("new-vs-removed-30", () => api.newVsRemoved(30), []);
  const pricePerM2 = useAsync(() => api.pricePerM2(), []);
  const priceDrops = useAsync(() => api.priceDrops(5, PRICE_DROPS_PREVIEW, false), []);

  return (
    <PageContainer title={cs.analytics.titulek}>
      <RefreshIndicator active={summary.refreshing} />
      {summary.data && <DatasetCoverageBanner summary={summary.data} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title={cs.analytics.nabidkaPodleKraje}>
          {inventory.loading && !inventory.data && <LoadingState />}
          {inventory.refreshing && <RefreshIndicator active />}
          {inventory.error && <ErrorState message={inventory.error.message} />}
          {inventory.data && <InventoryChart data={inventory.data} />}
        </Panel>

        <Panel title={`${cs.analytics.noveVsStazene} (30 dní)`}>
          {newVsRemoved.loading && !newVsRemoved.data && <LoadingState />}
          {newVsRemoved.refreshing && <RefreshIndicator active />}
          {newVsRemoved.error && <ErrorState message={newVsRemoved.error.message} />}
          {newVsRemoved.data && (
            <div className="flex gap-10 justify-center py-8">
              <div className="text-center">
                <p className="text-3xl font-bold text-accent-dark tabular-nums">{newVsRemoved.data.new_count}</p>
                <p className="text-ink-muted text-sm mt-1">Nové nabídky v datasetu</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-danger tabular-nums">{newVsRemoved.data.removed_count}</p>
                <p className="text-ink-muted text-sm mt-1">Stažené nabídky z datasetu</p>
              </div>
            </div>
          )}
        </Panel>

        <LazyMount minHeight={280}>
          <Panel title={`${cs.analytics.cenaZaM2} podle lokality`} className="lg:col-span-2">
            {pricePerM2.loading && !pricePerM2.data && <LoadingState />}
            {pricePerM2.refreshing && <RefreshIndicator active />}
            {pricePerM2.error && <ErrorState message={pricePerM2.error.message} />}
            {pricePerM2.data && pricePerM2.data.length === 0 && <EmptyState />}
            {pricePerM2.data && pricePerM2.data.length > 0 && (
              <>
                <p className="text-xs text-ink-muted mb-3">
                  {cs.analytics.cenaZaM2Tabulka.replace("{count}", String(pricePerM2.data.length))}
                </p>
                <div className="data-table-shell max-h-[480px] overflow-y-auto">
                  <table className="data-table">
                    <thead className="sticky top-0 z-[1] bg-surface-muted/95 backdrop-blur-sm">
                      <tr>
                        <th className="text-left">Kraj</th>
                        <th className="text-left">Okres</th>
                        <th className="text-left">Obec</th>
                        <th className="text-right">Prům. cena</th>
                        <th className="text-right">Cena za m²</th>
                        <th className="text-right">Počet</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pricePerM2.data.map((row, i) => (
                        <tr key={i}>
                          <td>{row.region ?? "—"}</td>
                          <td>{row.district ?? "—"}</td>
                          <td>{row.municipality ?? "—"}</td>
                          <td className="text-right tabular-nums">{formatCzk(row.avg_price_czk)}</td>
                          <td className="text-right tabular-nums">{row.avg_price_per_m2 ? formatCzk(row.avg_price_per_m2) : "—"}</td>
                          <td className="text-right tabular-nums font-medium text-brand">{row.listing_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Panel>
        </LazyMount>

        <LazyMount minHeight={280}>
          <Panel title={cs.analytics.poklesyCeny} className="lg:col-span-2">
            <p className="text-xs text-ink-muted mb-3">
              {cs.dataset.poklesyNahledLimit.replace("{limit}", String(PRICE_DROPS_PREVIEW))}
            </p>
            {priceDrops.loading && !priceDrops.data && <LoadingState />}
            {priceDrops.refreshing && <RefreshIndicator active />}
            {priceDrops.error && <ErrorState message={priceDrops.error.message} />}
            {priceDrops.data && priceDrops.data.items.length === 0 && <EmptyState />}
            {priceDrops.data && priceDrops.data.items.length > 0 && (
              <div className="data-table-shell max-h-[480px] overflow-y-auto">
                <table className="data-table">
                  <thead className="sticky top-0 z-[1] bg-surface-muted/95 backdrop-blur-sm">
                    <tr>
                      <th className="text-left">Nabídka</th>
                      <th className="text-right">Původní cena</th>
                      <th className="text-right">Nová cena</th>
                      <th className="text-right">Pokles</th>
                    </tr>
                  </thead>
                  <tbody>
                    {priceDrops.data.items.map((row) => (
                      <tr key={row.listing_id}>
                        <td className="font-medium text-navy">{row.title ?? "—"}</td>
                        <td className="text-right tabular-nums">{formatCzk(row.previous_price_czk)}</td>
                        <td className="text-right tabular-nums">{formatCzk(row.current_price_czk)}</td>
                        <td className="text-right text-danger font-semibold tabular-nums">-{row.drop_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </LazyMount>
      </div>
    </PageContainer>
  );
}
