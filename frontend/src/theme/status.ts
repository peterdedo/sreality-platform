/** Shared status pill / banner class strings using the 4ct palette. */
export const statusClasses = {
  success: "status-badge status-badge--success",
  error: "status-badge status-badge--error",
  warning: "status-badge status-badge--warning",
  pending: "status-badge status-badge--warning",
  neutral: "status-badge status-badge--neutral",
  info: "status-badge status-badge--info",
  successBanner: "status-banner status-banner--success",
} as const;

export type StatusPillVariant = Exclude<keyof typeof statusClasses, "successBanner">;

export function statusPill(variant: StatusPillVariant): string {
  return statusClasses[variant];
}

export const successBanner = "status-banner status-banner--success mb-4";

const RUN_STATUS_VARIANT: Record<string, StatusPillVariant> = {
  success: "success",
  failed: "error",
  running: "info",
  partial: "warning",
};

export function runStatusPill(status: string): string {
  return statusPill(RUN_STATUS_VARIANT[status] ?? "neutral");
}

const VALUATION_STATUS_VARIANT: Record<string, StatusPillVariant> = {
  under_market: "success",
  near_market: "neutral",
  over_market: "error",
};

export function valuationStatusPill(classification: string): string {
  return statusPill(VALUATION_STATUS_VARIANT[classification] ?? "neutral");
}

export function freshnessBadgeClass(freshness: string | undefined): string {
  switch (freshness) {
    case "in_progress":
      return "status-badge status-badge--info";
    case "final_complete":
      return "status-badge status-badge--success";
    case "final_partial":
      return "status-badge status-badge--warning";
    default:
      return "status-badge status-badge--neutral";
  }
}
