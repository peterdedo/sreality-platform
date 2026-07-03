import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { ANOMALY_FLAG_LABELS, formatPercentPlain } from "../../constants";
import { cs } from "../../locale/cs";
import { useAsync } from "../../hooks/useAsync";
import { statusPill } from "../../theme/status";
import { EmptyState, ErrorState, LoadingState } from "../StateHelpers";
import { ADVANCED_TABLE_PAGE_SIZE, TablePagination } from "../ui/TablePagination";

export function AnomalyTable() {
  const [page, setPage] = useState(1);
  const [minScore, setMinScore] = useState(50);
  const pageSize = ADVANCED_TABLE_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  const { data, loading, error } = useAsync(
    () => api.advanced.anomalies(minScore, undefined, pageSize, offset),
    [minScore, page, pageSize, offset]
  );

  return (
    <section className="panel">
      <div className="panel__header !mb-2">
        <h2 className="panel__title">{cs.advanced.anomalie.titulek}</h2>
        <div className="flex items-center gap-2">
          <label className="field-label !mb-0">{cs.advanced.anomalie.minSkore}</label>
          <select
            className="select-field !min-w-[5rem]"
            value={minScore}
            onChange={(e) => {
              setMinScore(Number(e.target.value));
              setPage(1);
            }}
          >
            {[50, 65, 80].map((score) => (
              <option key={score} value={score}>
                ≥ {score}
              </option>
            ))}
          </select>
        </div>
      </div>
      {data && (
        <p className="text-xs text-ink-muted mb-3">{cs.advanced.anomalie.nahledTabulky.replace("{total}", String(data.total))}</p>
      )}

      {loading && !data && <LoadingState />}
      {loading && data && <p className="loading-inline mb-2">{cs.common.nacitani}</p>}
      {error && <ErrorState message={error.message} />}
      {data && data.items.length === 0 && <EmptyState message={cs.advanced.anomalie.zadneAnomalie} />}
      {data && data.items.length > 0 && (
        <>
          <div className="data-table-shell max-h-[520px] overflow-y-auto">
            <table className="data-table">
              <thead className="sticky top-0 z-[1] bg-surface-muted/95 backdrop-blur-sm">
                <tr>
                  <th className="text-left py-1">ID</th>
                  <th className="text-right py-1">{cs.advanced.anomalie.skore}</th>
                  <th className="text-left py-1">{cs.advanced.anomalie.priznaky}</th>
                  <th className="text-right py-1">{cs.advanced.anomalie.spolehlivostDat}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link to={`/nabidky/${row.listing_id}`} className="link-brand font-semibold">
                        #{row.listing_id}
                      </Link>
                    </td>
                    <td className="py-1 text-right font-medium text-danger tabular-nums">{Math.round(row.anomaly_score)}</td>
                    <td className="py-1">
                      <div className="flex flex-wrap gap-1">
                        {row.anomaly_flags.map((flag) => (
                          <span key={flag} className={statusPill("pending")}>
                            {ANOMALY_FLAG_LABELS[flag] ?? flag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-1 text-right text-ink-muted tabular-nums">
                      {formatPercentPlain(row.confidence_score * 100, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <TablePagination page={page} pageSize={pageSize} total={data.total} onPageChange={setPage} />
        </>
      )}
    </section>
  );
}
