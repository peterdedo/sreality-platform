import { api } from "../api/client";
import { PageContainer } from "../components/layout/PageContainer";
import { MapView } from "../components/map/MapView";
import { DatasetCoverageBanner } from "../components/DatasetCoverageBanner";
import { ErrorState } from "../components/StateHelpers";
import { useDatasetSummary } from "../hooks/useDatasetSummary";
import { useViewportBounds } from "../hooks/useViewportBounds";
import { useAsync } from "../hooks/useAsync";
import { cs } from "../locale/cs";

// Safety cap on markers per viewport fetch -- a fully zoomed-out view over a
// dense area still returns far fewer rows than the unbounded full dataset,
// but this keeps a pathological case (e.g. whole-country zoom) bounded too.
const VIEWPORT_MARKER_LIMIT = 5000;

export function Mapa() {
  const { bounds, onBoundsChange } = useViewportBounds();
  const summary = useDatasetSummary();

  const boundsKey = bounds ? `${bounds.south},${bounds.west},${bounds.north},${bounds.east}` : "pending";
  const markers = useAsync(
    () =>
      bounds
        ? api.mapMarkers({ is_active: true, ...bounds, limit: VIEWPORT_MARKER_LIMIT })
        : Promise.resolve({ items: [], total: 0, truncated: false }),
    [boundsKey]
  );

  // Bounds only exist once the map itself has mounted and reported its
  // viewport (see MapView's BoundsWatcher) -- so the map must always render;
  // it cannot be gated behind "bounds are known" without deadlocking.
  const isInitialLoad = bounds === null;
  const isRefreshing = !isInitialLoad && markers.loading;

  return (
    <PageContainer title={cs.map.titulek}>
      {summary.data && (
        <DatasetCoverageBanner summary={summary.data} context="map" mapLoadedCount={markers.data?.total ?? markers.data?.items.length ?? 0} />
      )}
      <p className="map-context-note">{cs.map.vyrezNapoveda}</p>
      {markers.error && <ErrorState message={markers.error.message} />}
      {markers.data?.truncated && (
        <div className="map-truncation-banner">
          {cs.map.orezanoVyrez
            .replace("{total}", String(markers.data.total))
            .replace("{shown}", String(markers.data.items.length))}
        </div>
      )}
      <MapView
        markers={markers.data?.items ?? []}
        onBoundsChange={onBoundsChange}
        isRefreshing={isInitialLoad || isRefreshing}
      />
    </PageContainer>
  );
}
