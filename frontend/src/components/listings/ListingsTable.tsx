import { useNavigate } from "react-router-dom";
import type { Listing } from "../../api/types";
import { cs } from "../../locale/cs";
import { EmptyState } from "../StateHelpers";
import { SrealityLink } from "../SrealityLink";
import { LISTING_COLUMNS } from "./columns";
import type { ListingFilters as Filters } from "../../api/client";

interface Props {
  items: Listing[];
  visibleColumns: string[];
  sortBy?: Filters["sort_by"];
  sortDir?: Filters["sort_dir"];
  onSortChange?: (sortBy: string, sortDir: "asc" | "desc") => void;
}

const SORTABLE_COLUMN_KEYS: Record<string, string> = {
  price: "price_czk",
  price_per_m2: "price_per_m2",
  usable_area: "usable_area",
  days_on_market: "days_on_market",
  first_seen_at: "first_seen_at",
  last_updated_at: "last_seen_at",
};

export function ListingsTable({ items, visibleColumns, sortBy, sortDir, onSortChange }: Props) {
  const navigate = useNavigate();
  const columns = LISTING_COLUMNS.filter((c) => visibleColumns.includes(c.key));

  if (items.length === 0) {
    return <EmptyState message={cs.listings.zadneNabidky} />;
  }

  return (
    <div className="data-table-shell">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => {
              const sortKey = SORTABLE_COLUMN_KEYS[col.key];
              const isActive = sortKey && sortBy === sortKey;
              return (
                <th
                  key={col.key}
                  className={`${col.align === "right" ? "text-right" : "text-left"} ${
                    sortKey && onSortChange ? "cursor-pointer select-none hover:text-brand" : ""
                  }`}
                  onClick={
                    sortKey && onSortChange
                      ? () => onSortChange(sortKey, isActive && sortDir === "desc" ? "asc" : "desc")
                      : undefined
                  }
                >
                  {col.label}
                  {isActive && <span className="ml-1 text-accent">{sortDir === "asc" ? "↑" : "↓"}</span>}
                </th>
              );
            })}
            <th className="text-left">{cs.listings.sreality}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((listing) => (
            <tr key={listing.id} className="row-clickable" onClick={() => navigate(`/nabidky/${listing.id}`)}>
              {columns.map((col, i) => (
                <td
                  key={col.key}
                  className={`${col.align === "right" ? "text-right tabular-nums" : ""} ${
                    i === 0 ? "font-semibold text-navy" : "text-ink"
                  }`}
                >
                  {col.render(listing)}
                </td>
              ))}
              <td onClick={(e) => e.stopPropagation()}>
                <SrealityLink href={listing.source_url} className="link-brand">
                  ↗
                </SrealityLink>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
