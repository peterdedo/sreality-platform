import { Link } from "react-router-dom";

import { api } from "../api/client";

import { PageContainer } from "../components/layout/PageContainer";

import { DatasetCoverageBanner } from "../components/DatasetCoverageBanner";

import { ErrorState, LoadingState } from "../components/StateHelpers";

import { KpiCard, Panel } from "../components/ui/primitives";

import { RefreshIndicator } from "../components/ui/RefreshIndicator";

import { useDatasetSummary, isDatasetInProgress } from "../hooks/useDatasetSummary";

import { useAsync, useCachedAsync } from "../hooks/useAsync";

import { cs } from "../locale/cs";

import { formatCzk } from "../constants";

export function PrehledTrhu() {
  const summary = useDatasetSummary();
  const newVsRemoved = useCachedAsync("new-vs-removed-30", () => api.newVsRemoved(30), []);
  const priceDrops = useAsync(() => api.priceDrops(5, 5, false), []);
  const inventory = useCachedAsync("inventory-by-region", () => api.inventoryByRegion(), []);

  return (
    <PageContainer title={cs.nav.prehledTrhu}>
      <RefreshIndicator active={summary.refreshing} />
      {summary.data && <DatasetCoverageBanner summary={summary.data} />}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <KpiCard
          label={
            isDatasetInProgress(summary.data)
              ? `${cs.prehled.aktivniNabidky} (průběžně)`
              : cs.prehled.aktivniNabidky
          }
          value={summary.loading ? "…" : (summary.data?.active_listing_count ?? "—")}
          tone="brand"
          loading={summary.loading}
          error={summary.error?.message}
        />
        <KpiCard
          label={cs.prehled.noveZa30}
          value={newVsRemoved.loading ? "…" : (newVsRemoved.data?.new_count ?? "—")}
          tone="accent"
          loading={newVsRemoved.loading}
          error={newVsRemoved.error?.message}
        />
        <KpiCard
          label={cs.prehled.stazeneZa30}
          value={newVsRemoved.loading ? "…" : (newVsRemoved.data?.removed_count ?? "—")}
          tone="danger"
          loading={newVsRemoved.loading}
          error={newVsRemoved.error?.message}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel
          title={cs.analytics.poklesyCeny}
          actions={
            <Link to="/analytika" className="link-subtle">
              Zobrazit vše →
            </Link>
          }
        >
          <p className="text-xs text-ink-muted mb-3">Náhled top 5 z celého datasetu.</p>
          {priceDrops.loading && !priceDrops.data && <LoadingState />}
          {priceDrops.refreshing && <RefreshIndicator active />}
          {priceDrops.error && <ErrorState message={priceDrops.error.message} />}
          {priceDrops.data && priceDrops.data.items.length === 0 && (
            <p className="text-ink-muted/70 text-sm py-6 text-center">{cs.common.zadnaData}</p>
          )}
          {priceDrops.data && priceDrops.data.items.length > 0 && (
            <ul className="divide-y divide-surface-border">
              {priceDrops.data.items.map((d) => (
                <li key={d.listing_id} className="py-2.5 flex justify-between gap-3 text-sm hover:bg-surface-muted/50 -mx-2 px-2 rounded-lg transition-colors">
                  <span className="truncate">{d.title}</span>
                  <span className="text-danger font-semibold shrink-0 tabular-nums">
                    {formatCzk(d.current_price_czk)} (-{d.drop_pct}%)
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title={cs.analytics.nabidkaPodleKraje}
          actions={
            <Link to="/analytika" className="link-subtle">
              Zobrazit graf →
            </Link>
          }
        >
          {inventory.loading && !inventory.data && <LoadingState />}
          {inventory.refreshing && <RefreshIndicator active />}
          {inventory.error && <ErrorState message={inventory.error.message} />}
          {inventory.data && (
            <ul className="divide-y divide-surface-border max-h-80 overflow-y-auto">
              {inventory.data.map((r) => (
                <li key={r.region ?? "unknown"} className="py-2.5 flex justify-between text-sm hover:bg-surface-muted/50 -mx-2 px-2 rounded-lg transition-colors">
                  <span>{r.region ?? "—"}</span>
                  <span className="font-semibold tabular-nums text-brand">{r.listing_count}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </PageContainer>
  );
}
