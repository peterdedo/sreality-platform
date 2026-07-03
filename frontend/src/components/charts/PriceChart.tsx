import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PriceHistoryPoint } from "../../api/types";
import { formatCzk, formatDate } from "../../constants";
import { chartTheme } from "../../theme/chartTheme";
import { EmptyState } from "../StateHelpers";

export function PriceChart({ data }: { data: PriceHistoryPoint[] }) {
  if (data.length === 0) return <EmptyState />;

  const chartData = data.map((p) => ({ ...p, label: formatDate(p.recorded_at) }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: chartTheme.axis }} />
        <YAxis tickFormatter={(v) => formatCzk(v)} width={90} tick={{ fontSize: 11, fill: chartTheme.axis }} />
        <Tooltip formatter={(v: number) => formatCzk(v)} labelFormatter={(l) => l} />
        <Line type="monotone" dataKey="price_czk" stroke={chartTheme.primary} strokeWidth={2} dot={false} name="Cena" />
      </LineChart>
    </ResponsiveContainer>
  );
}
