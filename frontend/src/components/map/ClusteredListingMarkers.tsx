import L from "leaflet";
import "leaflet.markercluster";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useMap } from "react-leaflet";
import type { MapMarker } from "../../api/types";
import { formatCzk } from "../../constants";
import { cs } from "../../locale/cs";
import "./leafletSetup";

type Props = {
  markers: MapMarker[];
  onOpenDetail: (id: number) => void;
};

function buildPopupContent(marker: MapMarker, onOpenDetail: (id: number) => void): HTMLElement {
  const container = L.DomUtil.create("div");
  container.className = "text-sm";

  const title = L.DomUtil.create("p", "font-medium", container);
  title.textContent = marker.title ?? "—";

  const price = L.DomUtil.create("p", "", container);
  price.textContent = formatCzk(marker.price_czk);

  const button = L.DomUtil.create("button", "text-brand underline mt-1", container);
  button.type = "button";
  button.textContent = "Zobrazit detail";
  L.DomEvent.on(button, "click", (event) => {
    L.DomEvent.stopPropagation(event);
    onOpenDetail(marker.id);
  });

  if (marker.source_url) {
    const external = L.DomUtil.create("a", "text-brand underline mt-1 block", container);
    external.href = marker.source_url;
    external.target = "_blank";
    external.rel = "noopener noreferrer";
    external.textContent = `${cs.detail.odkazSreality} ↗`;
    L.DomEvent.on(external, "click", (event) => {
      L.DomEvent.stopPropagation(event);
    });
  }

  return container;
}

export function ClusteredListingMarkers({ markers, onOpenDetail }: Props) {
  const map = useMap();
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null);
  const markerLayersRef = useRef<Map<number, L.Marker>>(new Map());
  const openDetail = useCallback((id: number) => onOpenDetail(id), [onOpenDetail]);
  const withGps = useMemo(() => markers.filter((m) => m.gps_lat != null && m.gps_lon != null), [markers]);

  useEffect(() => {
    const cluster = L.markerClusterGroup({
      chunkedLoading: true,
      chunkInterval: 200,
      chunkDelay: 50,
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      removeOutsideVisibleBounds: true,
    });
    clusterRef.current = cluster;
    map.addLayer(cluster);

    return () => {
      map.removeLayer(cluster);
      cluster.clearLayers();
      clusterRef.current = null;
      markerLayersRef.current.clear();
    };
  }, [map]);

  useEffect(() => {
    const cluster = clusterRef.current;
    if (!cluster) return;

    const nextIds = new Set(withGps.map((m) => m.id));
    const layers = markerLayersRef.current;

    for (const [id, layer] of layers) {
      if (!nextIds.has(id)) {
        cluster.removeLayer(layer);
        layers.delete(id);
      }
    }

    for (const marker of withGps) {
      const lat = marker.gps_lat!;
      const lon = marker.gps_lon!;
      const existing = layers.get(marker.id);

      if (existing) {
        const pos = existing.getLatLng();
        if (pos.lat !== lat || pos.lng !== lon) {
          existing.setLatLng([lat, lon]);
        }
        existing.bindPopup(() => buildPopupContent(marker, openDetail), { maxWidth: 320 });
        continue;
      }

      const layer = L.marker([lat, lon]);
      layer.bindPopup(() => buildPopupContent(marker, openDetail), { maxWidth: 320 });
      cluster.addLayer(layer);
      layers.set(marker.id, layer);
    }
  }, [withGps, openDetail]);

  return null;
}
