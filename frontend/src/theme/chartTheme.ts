/** 4ct brand chart palette — green accent + navy primary. */
export const chartTheme = {
  primary: "#0055A5",
  accent: "#54AB34",
  grid: "#E2E8F0",
  axis: "#6B7280",
  null: "#94A3B8",
  heatmapLow: { r: 0, g: 85, b: 165 },
  heatmapHigh: { r: 84, g: 171, b: 52 },
} as const;

export function heatmapColor(value: number | null, min: number, max: number): string {
  if (value === null || max === min) return chartTheme.null;
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const { heatmapLow: low, heatmapHigh: high } = chartTheme;
  const r = Math.round(low.r + t * (high.r - low.r));
  const g = Math.round(low.g + t * (high.g - low.g));
  const b = Math.round(low.b + t * (high.b - low.b));
  return `rgb(${r},${g},${b})`;
}
