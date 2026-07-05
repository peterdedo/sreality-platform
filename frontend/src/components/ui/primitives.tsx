import type { PropsWithChildren, ReactNode } from "react";
import { isBackendConnectivityFailure } from "../../api/connectivity";
import { useSuppressConnectivityErrors } from "../../context/BackendStatusProvider";
import type { KpiInterpretation } from "../../kpi/types";
import type { BannerVariant } from "../../theme/tokens";
import { KpiInterpretationLine } from "../kpi/KpiInterpretationLine";

type Props = PropsWithChildren<{
  variant: BannerVariant;
  className?: string;
}>;

export function StatusBanner({ variant, className = "", children }: Props) {
  return <div className={`status-banner status-banner--${variant} ${className}`.trim()}>{children}</div>;
}

type PanelProps = PropsWithChildren<{
  title?: ReactNode;
  actions?: ReactNode;
  className?: string;
  staticHover?: boolean;
  featured?: boolean;
}>;

export function Panel({ title, actions, children, className = "", staticHover = false, featured = false }: PanelProps) {
  const panelClass = featured ? "panel panel--featured" : staticHover ? "panel-static" : "panel";
  return (
    <section className={`${panelClass} ${className}`.trim()}>
      {(title || actions) && (
        <div className="panel__header">
          {title ? <h2 className="panel__title">{title}</h2> : <span />}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

type KpiProps = {
  label: string;
  value: string | number;
  tone?: "default" | "accent" | "brand" | "danger";
  loading?: boolean;
  error?: string;
  hint?: string;
  interpretation?: KpiInterpretation;
};

export function KpiCard({ label, value, tone = "default", loading, error, hint, interpretation }: KpiProps) {
  const suppressConnectivityErrors = useSuppressConnectivityErrors();
  const showError = error && !(suppressConnectivityErrors && isBackendConnectivityFailure(error));

  // Group integers the Czech way (105 310) so the headline value matches the
  // grouped numbers used in every supporting line; pre-formatted strings
  // (e.g. "27 %", "…", "—") pass through untouched.
  const displayValue = typeof value === "number" ? value.toLocaleString("cs-CZ") : value;
  const toneClass =
    tone === "brand" ? "kpi-card--brand" : tone === "danger" ? "kpi-card--danger" : tone === "accent" ? "kpi-card--accent" : "";
  const valueClass =
    tone === "accent"
      ? "kpi-card__value kpi-card__value--accent"
      : tone === "brand"
        ? "kpi-card__value kpi-card__value--brand"
        : tone === "danger"
          ? "kpi-card__value kpi-card__value--danger"
          : "kpi-card__value";

  return (
    <div className={`kpi-card ${toneClass}`.trim()}>
      <div className="kpi-card__glow" aria-hidden />
      <p className="kpi-card__label">{label}</p>
      {loading ? (
        <div className="mt-3">
          <span className="loading-shimmer loading-shimmer--kpi" />
        </div>
      ) : showError ? (
        <p className="text-danger text-sm mt-2 font-medium">{error}</p>
      ) : (
        <>
          <p className={valueClass}>{displayValue}</p>
          {interpretation && !loading && !showError && <KpiInterpretationLine interpretation={interpretation} />}
          {!interpretation && hint && <p className="kpi-card__hint">{hint}</p>}
        </>
      )}
    </div>
  );
}
