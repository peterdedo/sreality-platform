import L from "leaflet";
import type { Map as LeafletMap } from "leaflet";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { api } from "../../api/client";
import type { SpatialGridCell, SpatialHeatmapResponse } from "../../api/types";
import { formatCzk, formatPercentPlain } from "../../constants";
import { cs } from "../../locale/cs";
import { useAsync } from "../../hooks/useAsync";
import type { MapBounds } from "../../hooks/useViewportBounds";
import { useViewportBounds } from "../../hooks/useViewportBounds";
import { heatmapColor } from "../../theme/chartTheme";
import { EmptyState, ErrorState, LoadingState } from "../StateHelpers";
import { RefreshIndicator } from "../ui/RefreshIndicator";
import "../map/leafletSetup";

const PRAGUE_CENTER: [number, number] = [49.8175, 15.473];
const DEFAULT_ZOOM = 7;

type Metric = "avg_price_per_m2" | "price_drop_intensity" | "turnover_rate";

function metricValue(cell: SpatialGridCell, metric: Metric): number | null {
  return cell[metric];
}

function gridStepKm(stepDegrees: number): string {
  return (stepDegrees * 111).toFixed(1).replace(".", ",");
}

function ViewportWatcher({
  onViewportChange,
}: {
  onViewportChange: (bounds: MapBounds, zoom: number) => void;
}) {
  const emit = useCallback(
    (map: LeafletMap) => {
      const b = map.getBounds();
      onViewportChange(
        {
          south: b.getSouth(),
          west: b.getWest(),
          north: b.getNorth(),
          east: b.getEast(),
        },
        map.getZoom()
      );
    },
    [onViewportChange]
  );

  const map = useMapEvents({
    moveend: () => emit(map),
    zoomend: () => emit(map),
  });

  useEffect(() => {
    emit(map);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}

function HeatmapCellLayer({
  cells,
  metric,
  min,
  max,
  gridStepDegrees,
}: {
  cells: SpatialGridCell[];
  metric: Metric;
  min: number;
  max: number;
  gridStepDegrees: number;
}) {
  const map = useMap();
  const layerRef = useRef<L.LayerGroup | null>(null);
  const half = gridStepDegrees / 2;

  useEffect(() => {
    const group = L.layerGroup();
    layerRef.current = group;
    map.addLayer(group);
    return () => {
      map.removeLayer(group);
      group.clearLayers();
      layerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    const group = layerRef.current;
    if (!group) return;

    group.clearLayers();
    for (const cell of cells) {
      const value = metricValue(cell, metric);
      const rect = L.rectangle(
        [
          [cell.lat_center - half, cell.lon_center - half],
          [cell.lat_center + half, cell.lon_center + half],
        ],
        {
          color: heatmapColor(value, min, max),
          fillOpacity: 0.6,
          weight: 1,
        }
      );
      rect.bindPopup(
        `<div class="text-sm">
          <p>${cs.advanced.prostorova.pocetNabidekVBunce}: ${cell.listing_count}</p>
          <p>${cs.advanced.prostorova.cenaZaM2}: ${cell.avg_price_per_m2 ? formatCzk(cell.avg_price_per_m2) : "—"}</p>
          <p>${cs.advanced.prostorova.intenzitaPoklesu}: ${
            cell.price_drop_intensity !== null ? formatPercentPlain(cell.price_drop_intensity * 100, 0) : "—"
          }</p>
          <p>${cs.advanced.prostorova.obrat}: ${formatPercentPlain(cell.turnover_rate * 100, 0)}</p>
        </div>`
      );
      group.addLayer(rect);
    }
  }, [cells, metric, min, max, half]);

  return null;
}

export function SpatialHeatmap() {
  const [metric, setMetric] = useState<Metric>("avg_price_per_m2");
  const { bounds, zoom, onBoundsChange } = useViewportBounds({ trackZoom: true });

  const viewportKey = bounds ? `${bounds.south},${bounds.west},${bounds.north},${bounds.east},${zoom ?? DEFAULT_ZOOM}` : "pending";

  const heatmap = useAsync<SpatialHeatmapResponse>(
    () =>
      bounds
        ? api.advanced.spatialHeatmap({ ...bounds, zoom: zoom ?? DEFAULT_ZOOM })
        : Promise.resolve({
            items: [],
            grid_step_degrees: 0.01,
            bbox_applied: false,
            cell_count: 0,
            aggregated: false,
            source: "live" as const,
          }),
    [viewportKey]
  );

  const cells = heatmap.data?.items ?? [];
  const values = cells.map((c) => metricValue(c, metric)).filter((v): v is number => v !== null);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const gridStep = heatmap.data?.grid_step_degrees ?? 0.01;

  const metaLine = useMemo(() => {
    if (!heatmap.data || !bounds) return null;
    const parts = [
      cs.advanced.prostorova.bunkyVeVyrezu
        .replace("{count}", String(heatmap.data.cell_count))
        .replace("{step}", String(heatmap.data.grid_step_degrees)),
    ];
    if (heatmap.data.aggregated) {
      parts.push(cs.advanced.prostorova.agregovanaMrizka.replace("{km}", gridStepKm(gridStep)));
    }
    return parts.join(" ");
  }, [heatmap.data, bounds, gridStep]);

  const waitingForViewport = bounds === null;
  const showDataLoading = !waitingForViewport && heatmap.loading && !heatmap.data;

  return (
    <section className="panel">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
        <h2 className="font-semibold">{cs.advanced.prostorova.titulek}</h2>
        <select
          className="border border-ink-faint rounded-md px-2 py-1.5 text-sm w-full sm:w-auto"
          value={metric}
          onChange={(e) => setMetric(e.target.value as Metric)}
        >
          <option value="avg_price_per_m2">{cs.advanced.prostorova.cenaZaM2}</option>
          <option value="price_drop_intensity">{cs.advanced.prostorova.intenzitaPoklesu}</option>
          <option value="turnover_rate">{cs.advanced.prostorova.obrat}</option>
        </select>
      </div>

      <p className="text-xs text-ink-muted mb-3">{cs.advanced.prostorova.vyrezNapoveda}</p>
      {metaLine && <p className="text-xs text-ink-muted mb-3">{metaLine}</p>}
      {heatmap.refreshing && <RefreshIndicator active />}

      {showDataLoading && <LoadingState />}
      {heatmap.error && <ErrorState message={heatmap.error.message} />}
      {!showDataLoading && !waitingForViewport && heatmap.data && heatmap.data.cell_count === 0 && <EmptyState />}

      <div className="h-[420px] sm:h-[500px] rounded-lg overflow-hidden border border-surface-border">
        <MapContainer center={PRAGUE_CENTER} zoom={DEFAULT_ZOOM} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> přispěvatelé'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ViewportWatcher onViewportChange={onBoundsChange} />
          {heatmap.data && heatmap.data.cell_count > 0 && (
            <HeatmapCellLayer cells={cells} metric={metric} min={min} max={max} gridStepDegrees={gridStep} />
          )}
        </MapContainer>
      </div>
    </section>
  );
}
