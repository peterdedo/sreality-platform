import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { InventoryRow } from "../../api/types";
import { chartTheme } from "../../theme/chartTheme";
import { EmptyState } from "../StateHelpers";

export function InventoryChart({ data }: { data: InventoryRow[] }) {
  if (data.length === 0) return <EmptyState />;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
        <XAxis dataKey="region" tick={{ fontSize: 11, fill: chartTheme.axis }} angle={-20} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 11, fill: chartTheme.axis }} />
        <Tooltip />
        <Bar dataKey="listing_count" fill={chartTheme.accent} name="Počet nabídek" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
