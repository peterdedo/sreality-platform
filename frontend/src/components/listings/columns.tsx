import type { ReactNode } from "react";
import type { Listing } from "../../api/types";
import {
  BUILDING_CONDITION_LABELS,
  BUILDING_TYPE_LABELS,
  DEAL_TYPES,
  ELEVATOR_LABELS,
  ENERGY_EFFICIENCY_RATING_LABELS,
  FURNISHED_LABELS,
  OWNERSHIP_LABELS,
  PROPERTY_TYPES,
  ROOM_LAYOUTS,
  SELLER_TYPE_LABELS,
  formatCzk,
  formatDate,
} from "../../constants";
import { cs } from "../../locale/cs";
import { statusPill } from "../../theme/status";

export interface ColumnDef {
  key: string;
  label: string;
  align?: "left" | "right";
  render: (listing: Listing) => ReactNode;
}

// Column-registry pattern: table rendering, the column selector, and saved
// views all key off this single list, rather than hardcoded <th>/<td>s.
export const LISTING_COLUMNS: ColumnDef[] = [
  { key: "title", label: cs.listings.sloupceLabels.title, render: (l) => l.title ?? "—" },
  {
    key: "property_type",
    label: cs.listings.sloupceLabels.property_type,
    render: (l) => PROPERTY_TYPES[l.category_main_cb] ?? "—",
  },
  {
    key: "deal_type",
    label: cs.listings.sloupceLabels.deal_type,
    render: (l) => DEAL_TYPES[l.category_type_cb] ?? "—",
  },
  {
    key: "layout",
    label: cs.listings.sloupceLabels.layout,
    render: (l) => (l.category_sub_cb ? ROOM_LAYOUTS[l.category_sub_cb] ?? "—" : "—"),
  },
  { key: "price", label: cs.listings.sloupceLabels.price, align: "right", render: (l) => formatCzk(l.price_czk) },
  {
    key: "price_per_m2",
    label: cs.listings.sloupceLabels.price_per_m2,
    align: "right",
    render: (l) => (l.price_per_m2 ? formatCzk(l.price_per_m2) : "—"),
  },
  {
    key: "usable_area",
    label: cs.listings.sloupceLabels.usable_area,
    align: "right",
    render: (l) => (l.usable_area ? `${l.usable_area} m²` : "—"),
  },
  {
    key: "locality",
    label: cs.listings.sloupceLabels.locality,
    render: (l) => l.locality_text ?? l.city ?? "—",
  },
  {
    key: "ownership",
    label: cs.listings.sloupceLabels.ownership,
    render: (l) => (l.ownership ? OWNERSHIP_LABELS[l.ownership] ?? l.ownership : "—"),
  },
  {
    key: "building_condition",
    label: cs.listings.sloupceLabels.building_condition,
    render: (l) => (l.building_condition ? BUILDING_CONDITION_LABELS[l.building_condition] ?? l.building_condition : "—"),
  },
  {
    key: "building_type",
    label: cs.listings.sloupceLabels.building_type,
    render: (l) => (l.building_type ? BUILDING_TYPE_LABELS[l.building_type] ?? l.building_type : "—"),
  },
  {
    key: "energy_efficiency_rating",
    label: cs.listings.sloupceLabels.energy_efficiency_rating,
    render: (l) => (l.energy_efficiency_rating ? ENERGY_EFFICIENCY_RATING_LABELS[l.energy_efficiency_rating] ?? l.energy_efficiency_rating : "—"),
  },
  {
    key: "elevator",
    label: cs.listings.sloupceLabels.elevator,
    render: (l) => (l.elevator ? ELEVATOR_LABELS[l.elevator] ?? l.elevator : "—"),
  },
  {
    key: "furnished",
    label: cs.listings.sloupceLabels.furnished,
    render: (l) => (l.furnished ? FURNISHED_LABELS[l.furnished] ?? l.furnished : "—"),
  },
  { key: "floor", label: cs.listings.sloupceLabels.floor, render: (l) => l.floor ?? "—" },
  {
    key: "seller_type",
    label: cs.listings.sloupceLabels.seller_type,
    render: (l) => (l.seller_type ? SELLER_TYPE_LABELS[l.seller_type] ?? l.seller_type : "—"),
  },
  {
    key: "days_on_market",
    label: cs.listings.sloupceLabels.days_on_market,
    align: "right",
    render: (l) => (l.days_on_market !== null ? `${l.days_on_market} d` : "—"),
  },
  {
    key: "has_price_drop",
    label: cs.listings.sloupceLabels.has_price_drop,
    render: (l) =>
      l.has_price_drop ? (
        <span className={`inline-block ${statusPill("error")}`}>
          ↓ {cs.listings.poklesCeny}
        </span>
      ) : (
        "—"
      ),
  },
  { key: "last_updated_at", label: cs.listings.sloupceLabels.last_updated_at, render: (l) => formatDate(l.last_updated_at ?? l.last_seen_at) },
  { key: "first_seen_at", label: cs.listings.sloupceLabels.first_seen_at, render: (l) => formatDate(l.first_seen_at) },
];

export const DEFAULT_VISIBLE_COLUMNS = [
  "title",
  "property_type",
  "layout",
  "price",
  "price_per_m2",
  "usable_area",
  "locality",
  "ownership",
  "building_condition",
  "energy_efficiency_rating",
  "days_on_market",
  "has_price_drop",
  "last_updated_at",
];
