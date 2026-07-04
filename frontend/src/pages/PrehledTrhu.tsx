import { Link } from "react-router-dom";
import { api } from "../api/client";
import { PanelInsight } from "../components/kpi/KpiInterpretationLine";
import { PageContainer } from "../components/layout/PageContainer";
import { DatasetCoverageBanner } from "../components/DatasetCoverageBanner";
import { ErrorState, LoadingState } from "../components/StateHelpers";
import { KpiCard, Panel } from "../components/ui/primitives";
import { RefreshIndicator } from "../components/ui/RefreshIndicator";
import { useDatasetSummary } from "../hooks/useDatasetSummary";
import { useAsync, useCachedAsync } from "../hooks/useAsync";
import {
  interpretActiveListings,
  interpretNewListings30,
  interpretPriceDrops,
  interpretRegionalInventory,
  interpretRemovedListings30,
  interpretUnderMarketShare,
  latestAvgDropShare,
} from "../kpi/interpret";
import { cs } from "../locale/cs";
import { formatCzk } from "../constants";

export function PrehledTrhu() {
  const summary = useDatasetSummary();
  const newVsRemoved = useCachedAsync("new-vs-removed-30", () => api.newVsRemoved(30), []);
  const priceDrops = useAsync(() => api.priceDrops(5, 5, true), []);
  const inventory = useCachedAsync("inventory-by-region", () => api.inventoryByRegion(), []);
  const marketSnapshots = useCachedAsync("market-dynamics-90", () => api.advanced.marketDynamics(90), []);
  const valuationSummary = useCachedAsync("valuation-summary", () => api.advanced.valuationSummary(), []);

  const activeCount = summary.data?.active_listing_count ?? 0;
  const newCount = newVsRemoved.data?.new_count ?? 0;
  const removedCount = newVsRemoved.data?.removed_count ?? 0;
  const avgDropShare = marketSnapshots.data ? latestAvgDropShare(marketSnapshots.data) : null;

  const activeInterp = interpretActiveListings(summary.data, marketSnapshots.data);
  const newInterp =
    newVsRemoved.data != null
      ? interpretNewListings30(newCount, removedCount, summary.data)
      : undefined;
  const removedInterp =
    newVsRemoved.data != null
      ? interpretRemovedListings30(removedCount, newCount, summary.data)
      : undefined;
  const underMarketInterp = interpretUnderMarketShare(
    valuationSummary.data,
    activeCount,
    summary.data?.active_with_valuation_count ?? 0
  );
  const priceDropInterp = interpretPriceDrops(
    priceDrops.data?.total_matched ?? null,
    activeCount,
    priceDrops.data?.items.length ?? 0,
    avgDropShare
  );
  const regionInterp = inventory.data ? interpretRegionalInventory(inventory.data) : null;

  const underMarketPct =
    valuationSummary.data && valuationSummary.data.total_valued_listings > 0
      ? Math.round(
          ((valuationSummary.data.by_classification.under_market ?? 0) /
            valuationSummary.data.total_valued_listings) *
            100
        )
      : null;

  return (
    <PageContainer title={cs.nav.prehledTrhu} subtitle={cs.prehled.podtitulek}>
      <RefreshIndicator active={summary.refreshing} />
      {summary.data && <DatasetCoverageBanner summary={summary.data} collapsible />}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <KpiCard
          label={
            summary.data?.dataset_freshness === "in_progress"
              ? `${cs.prehled.aktivniNabidky} (průběžně)`
              : cs.prehled.aktivniNabidky
          }
          value={summary.loading ? "…" : (summary.data?.active_listing_count ?? "—")}
          tone="brand"
          loading={summary.loading}
          error={summary.error?.message}
          interpretation={summary.data ? activeInterp : undefined}
        />
        <KpiCard
          label={cs.prehled.noveZa30}
          value={newVsRemoved.loading ? "…" : (newVsRemoved.data?.new_count ?? "—")}
          tone="accent"
          loading={newVsRemoved.loading}
          error={newVsRemoved.error?.message}
          interpretation={newInterp}
        />
        <KpiCard
          label={cs.prehled.stazeneZa30}
          value={newVsRemoved.loading ? "…" : (newVsRemoved.data?.removed_count ?? "—")}
          tone="danger"
          loading={newVsRemoved.loading}
          error={newVsRemoved.error?.message}
          interpretation={removedInterp}
        />
        <KpiCard
          label={cs.kpiInterpret.podTrhem.kpiLabel}
          value={
            valuationSummary.loading
              ? "…"
              : underMarketPct != null
                ? `${underMarketPct} %`
                : "—"
          }
          tone="default"
          loading={valuationSummary.loading}
          error={valuationSummary.error?.message}
          interpretation={underMarketInterp ?? undefined}
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
          <PanelInsight interpretation={priceDropInterp} />
          {priceDrops.loading && !priceDrops.data && <LoadingState />}
          {priceDrops.refreshing && <RefreshIndicator active />}
          {priceDrops.error && <ErrorState message={priceDrops.error.message} />}
          {priceDrops.data && priceDrops.data.items.length === 0 && (
            <p className="text-ink-muted/70 text-sm py-6 text-center">{cs.common.zadnaData}</p>
          )}
          {priceDrops.data && priceDrops.data.items.length > 0 && (
            <ul className="divide-y divide-surface-border">
              {priceDrops.data.items.map((d) => (
                <li key={d.listing_id} className="py-2.5 hover:bg-surface-muted/50 -mx-2 px-2 rounded-lg transition-colors">
                  <Link
                    to={`/nabidky/${d.listing_id}`}
                    className="flex justify-between gap-3 text-sm no-underline text-inherit"
                  >
                    <span className="truncate">{d.title}</span>
                    <span className="text-danger font-semibold shrink-0 tabular-nums">
                      {formatCzk(d.current_price_czk)} (-{d.drop_pct}%)
                    </span>
                  </Link>
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
          {regionInterp && <PanelInsight interpretation={regionInterp} />}
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
