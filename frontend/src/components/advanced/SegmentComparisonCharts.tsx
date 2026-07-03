import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../../api/client";
import { SEGMENT_DIMENSIONS, formatCzk } from "../../constants";
import { cs } from "../../locale/cs";
import { useAsync } from "../../hooks/useAsync";
import { chartTheme } from "../../theme/chartTheme";
import { EmptyState, ErrorState, LoadingState } from "../StateHelpers";

export function SegmentComparisonCharts() {
  const [dimension, setDimension] = useState(SEGMENT_DIMENSIONS[0].value);
  const { data, loading, error } = useAsync(() => api.advanced.segments(dimension), [dimension]);

  return (
    <section className="panel">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">{cs.advanced.segmenty.titulek}</h2>
        <select
          className="border border-ink-faint rounded-md px-2 py-1.5 text-sm"
          value={dimension}
          onChange={(e) => setDimension(e.target.value)}
        >
          {SEGMENT_DIMENSIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </div>

      {loading && <LoadingState />}
      {error && <ErrorState message={error.message} />}
      {data && data.length === 0 && <EmptyState />}
      {data && data.length > 0 && (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: chartTheme.axis }} angle={-20} textAnchor="end" height={60} />
              <YAxis tick={{ fontSize: 11, fill: chartTheme.axis }} />
              <Tooltip formatter={(v: number) => v.toLocaleString("cs-CZ")} />
              <Bar dataKey="listing_count" fill={chartTheme.primary} name={cs.advanced.segmenty.pocetNabidek} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>

          <table className="min-w-full text-sm mt-4">
            <thead className="text-ink-muted uppercase text-xs">
              <tr>
                <th className="text-left py-1">{cs.advanced.segmenty.dimenze}</th>
                <th className="text-right py-1">{cs.advanced.segmenty.pocetNabidek}</th>
                <th className="text-right py-1">{cs.advanced.segmenty.prumCena}</th>
                <th className="text-right py-1">{cs.advanced.segmenty.prumCenaZaM2}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {data.map((row) => (
                <tr key={String(row.value)}>
                  <td className="py-1">{row.label}</td>
                  <td className="py-1 text-right">{row.listing_count}</td>
                  <td className="py-1 text-right">{formatCzk(row.avg_price_czk)}</td>
                  <td className="py-1 text-right">{row.avg_price_per_m2 ? formatCzk(row.avg_price_per_m2) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
