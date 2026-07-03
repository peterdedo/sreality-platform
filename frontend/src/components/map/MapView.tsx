import type { Map as LeafletMap } from "leaflet";
import { useCallback, useEffect } from "react";
import { MapContainer, TileLayer, useMapEvents } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import type { MapMarker } from "../../api/types";
import type { MapBounds } from "../../hooks/useViewportBounds";
import { ClusteredListingMarkers } from "./ClusteredListingMarkers";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

const PRAGUE_CENTER: [number, number] = [49.8175, 15.473];

function BoundsWatcher({ onBoundsChange }: { onBoundsChange: (bounds: MapBounds) => void }) {
  const emit = useCallback(
    (map: LeafletMap) => {
      const b = map.getBounds();
      onBoundsChange({
        south: b.getSouth(),
        west: b.getWest(),
        north: b.getNorth(),
        east: b.getEast(),
      });
    },
    [onBoundsChange]
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

type Props = {
  markers: MapMarker[];
  onBoundsChange: (bounds: MapBounds) => void;
  isRefreshing?: boolean;
};

export function MapView({ markers, onBoundsChange, isRefreshing }: Props) {
  const navigate = useNavigate();
  const openDetail = useCallback((id: number) => navigate(`/nabidky/${id}`), [navigate]);

  return (
    <div className="map-shell">
      {isRefreshing && <div className="map-loading-pill">Načítání výřezu…</div>}
      <MapContainer center={PRAGUE_CENTER} zoom={7} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> přispěvatelé'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <BoundsWatcher onBoundsChange={onBoundsChange} />
        <ClusteredListingMarkers markers={markers} onOpenDetail={openDetail} />
      </MapContainer>
    </div>
  );
}
