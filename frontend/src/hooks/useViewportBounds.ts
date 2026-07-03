import { useCallback, useRef, useState } from "react";

export interface MapBounds {
  south: number;
  west: number;
  north: number;
  east: number;
}

export interface MapViewport extends MapBounds {
  zoom: number;
}

const DEBOUNCE_MS = 350;

/** Debounces rapid pan/zoom bounds updates so a drag doesn't fire a request
 * per frame -- only the settled viewport triggers a refetch. */
export function useViewportBounds(options?: { trackZoom?: boolean }) {
  const trackZoom = options?.trackZoom ?? false;
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [zoom, setZoom] = useState<number | null>(null);
  const timeoutRef = useRef<number | undefined>(undefined);

  const onBoundsChange = useCallback(
    (next: MapBounds, nextZoom?: number) => {
      if (timeoutRef.current !== undefined) {
        window.clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = window.setTimeout(() => {
        setBounds(next);
        if (trackZoom && nextZoom !== undefined) setZoom(nextZoom);
      }, DEBOUNCE_MS);
    },
    [trackZoom]
  );

  return { bounds, zoom, onBoundsChange };
}
