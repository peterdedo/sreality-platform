import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { VALUATION_CLASSIFICATION_LABELS, VALUATION_CONFIDENCE_LABELS, formatCzk, formatPercent } from "../../constants";
import { cs } from "../../locale/cs";
import { useAsync } from "../../hooks/useAsync";
import { valuationStatusPill } from "../../theme/status";
import { EmptyState, ErrorState, LoadingState } from "../StateHelpers";
import { ADVANCED_TABLE_PAGE_SIZE, TablePagination } from "../ui/TablePagination";

export function ValuationTable() {
  const [classification, setClassification] = useState<string>("");
  const [page, setPage] = useState(1);
  const pageSize = ADVANCED_TABLE_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  const { data, loading, error } = useAsync(
    () => api.advanced.valuationList(classification || undefined, undefined, pageSize, offset),
    [classification, page, pageSize, offset]
  );

  return (
    <section className="panel">
      <div className="panel__header !mb-2">
        <h2 className="panel__title">{cs.advanced.ocenovani.titulek}</h2>
        <select
          className="select-field"
          value={classification}
          onChange={(e) => {
            setClassification(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{cs.advanced.ocenovani.vse}</option>
          <option value="under_market">{cs.advanced.ocenovani.podTrhem}</option>
          <option value="near_market">{cs.advanced.ocenovani.naTrhu}</option>
          <option value="over_market">{cs.advanced.ocenovani.nadTrhem}</option>
        </select>
      </div>
      <p className="text-ink-muted text-sm mb-3">{cs.advanced.ocenovani.podnadpis}</p>

      {loading && !data && <LoadingState />}
      {loading && data && <p className="loading-inline mb-2">{cs.common.nacitani}</p>}
      {error && <ErrorState message={error.message} />}
      {data && data.items.length === 0 && <EmptyState />}
      {data && data.items.length > 0 && (
        <>
          <div className="data-table-shell max-h-[520px] overflow-y-auto">
            <table className="data-table">
              <thead className="sticky top-0 z-[1] bg-surface-muted/95 backdrop-blur-sm">
                <tr>
                  <th className="text-left py-1">ID</th>
                  <th className="text-right py-1">{cs.advanced.ocenovani.ocekavanaCena}</th>
                  <th className="text-right py-1">{cs.advanced.ocenovani.ocekavanaCenaM2}</th>
                  <th className="text-right py-1">{cs.advanced.ocenovani.odchylka}</th>
                  <th className="text-left py-1">{cs.advanced.ocenovani.klasifikace}</th>
                  <th className="text-left py-1">{cs.advanced.ocenovani.duveryhodnost}</th>
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
                    <td className="text-right tabular-nums">{formatCzk(row.expected_price_czk)}</td>
                    <td className="text-right tabular-nums">{formatCzk(row.expected_price_per_m2)}</td>
                    <td className="text-right tabular-nums">{formatPercent(row.residual_percent)}</td>
                    <td className="py-1">
                      {row.classification ? (
                        <span className={valuationStatusPill(row.classification)}>
                          {VALUATION_CLASSIFICATION_LABELS[row.classification]}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-1 text-ink-muted">{VALUATION_CONFIDENCE_LABELS[row.confidence]}</td>
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
