import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { formatCzk, formatPercent } from "../../constants";
import { cs } from "../../locale/cs";
import { useAsync } from "../../hooks/useAsync";
import { EmptyState, ErrorState, LoadingState } from "../StateHelpers";

export function ComparablesPanel({ listingId }: { listingId: number }) {
  const { data, loading, error } = useAsync(() => api.advanced.comparables(listingId, 8), [listingId]);

  return (
    <div>
      {loading && <LoadingState />}
      {error && <ErrorState message={error.message} />}
      {data && data.comparables.length === 0 && (
        <EmptyState message={data.note ?? cs.advanced.srovnatelne.zadneSrovnatelne} />
      )}
      {data && data.comparables.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-4 mb-3 text-sm">
            <div>
              <p className="text-ink-muted">{cs.advanced.srovnatelne.medianCena}</p>
              <p className="font-semibold">{formatCzk(data.median_comparable_price_czk)}</p>
            </div>
            <div>
              <p className="text-ink-muted">{cs.advanced.srovnatelne.medianCenaM2}</p>
              <p className="font-semibold">{formatCzk(data.median_comparable_price_per_m2)}</p>
            </div>
          </div>
          {data.deviation_from_comparables_pct !== null && (
            <p className="text-sm mb-3">
              {cs.advanced.srovnatelne.odchylkaOdSrovnatelnych}:{" "}
              <span className="font-medium">{formatPercent(data.deviation_from_comparables_pct)}</span>
            </p>
          )}
          {data.note && <p className="text-warning-dark text-xs mb-3">{data.note}</p>}
          <div className="data-table-shell">
          <table className="data-table">
            <tbody>
              {data.comparables.map((c) => (
                <tr key={c.listing_id}>
                  <td>
                    <Link to={`/nabidky/${c.listing_id}`} className="link-brand">
                      {c.title ?? `#${c.listing_id}`}
                    </Link>
                  </td>
                  <td className="text-right tabular-nums">{formatCzk(c.price_czk)}</td>
                  <td className="text-right tabular-nums text-ink-muted">{c.price_per_m2 ? `${formatCzk(c.price_per_m2)}/m²` : "—"}</td>
                  <td className="text-right text-ink-muted">{cs.advanced.srovnatelne.vzdalenost}: {c.distance_km} km</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </>
      )}
    </div>
  );
}
