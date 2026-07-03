import { useState } from "react";
import { DEAL_TYPES, PROPERTY_TYPES, ROOM_LAYOUTS } from "../../constants";
import { cs } from "../../locale/cs";
import type { ListingFilters as Filters } from "../../api/client";
import { AdvancedFiltersPanel } from "./AdvancedFiltersPanel";

interface Props {
  value: Filters;
  onChange: (value: Filters) => void;
}

export function ListingFiltersBar({ value, onChange }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  function update(patch: Partial<Filters>) {
    onChange({ ...value, ...patch, page: 1 });
  }

  return (
    <>
      <div className="filter-panel">
        <div>
          <label className="field-label">{cs.listings.hledat}</label>
          <input
            type="search"
            placeholder={cs.listings.hledatPlaceholder}
            className="input-field w-56"
            value={value.search ?? ""}
            onChange={(e) => update({ search: e.target.value || undefined })}
          />
        </div>

        <div>
          <label className="field-label">{cs.listings.typNemovitosti}</label>
          <select
            className="select-field min-w-[160px]"
            value={value.category_main_cb ?? ""}
            onChange={(e) => update({ category_main_cb: e.target.value ? Number(e.target.value) : undefined })}
          >
            <option value="">{cs.listings.vse}</option>
            {Object.entries(PROPERTY_TYPES).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="field-label">{cs.listings.typNabidky}</label>
          <select
            className="select-field min-w-[140px]"
            value={value.category_type_cb ?? ""}
            onChange={(e) => update({ category_type_cb: e.target.value ? Number(e.target.value) : undefined })}
          >
            <option value="">{cs.listings.vse}</option>
            {Object.entries(DEAL_TYPES).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="field-label">{cs.listings.dispozice}</label>
          <select
            className="select-field min-w-[120px]"
            value={value.category_sub_cb ?? ""}
            onChange={(e) => update({ category_sub_cb: e.target.value ? Number(e.target.value) : undefined })}
          >
            <option value="">{cs.listings.vse}</option>
            {Object.entries(ROOM_LAYOUTS).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="field-label">{cs.listings.cenaOd}</label>
          <input
            type="number"
            className="input-field w-32"
            value={value.price_min ?? ""}
            onChange={(e) => update({ price_min: e.target.value ? Number(e.target.value) : undefined })}
          />
        </div>

        <div>
          <label className="field-label">{cs.listings.cenaDo}</label>
          <input
            type="number"
            className="input-field w-32"
            value={value.price_max ?? ""}
            onChange={(e) => update({ price_max: e.target.value ? Number(e.target.value) : undefined })}
          />
        </div>

        <div>
          <label className="field-label">{cs.listings.plochaOd}</label>
          <input
            type="number"
            className="input-field w-24"
            value={value.usable_area_min ?? ""}
            onChange={(e) => update({ usable_area_min: e.target.value ? Number(e.target.value) : undefined })}
          />
        </div>

        <div>
          <label className="field-label">{cs.listings.plochaDo}</label>
          <input
            type="number"
            className="input-field w-24"
            value={value.usable_area_max ?? ""}
            onChange={(e) => update({ usable_area_max: e.target.value ? Number(e.target.value) : undefined })}
          />
        </div>

        <div>
          <label className="field-label">{cs.listings.stav}</label>
          <select
            className="select-field min-w-[150px]"
            value={value.is_active === false ? "false" : "true"}
            onChange={(e) => update({ is_active: e.target.value === "true" })}
          >
            <option value="true">{cs.listings.aktivni}</option>
            <option value="false">{cs.listings.neaktivni}</option>
          </select>
        </div>

        <button className="btn-ghost" onClick={() => setAdvancedOpen((v) => !v)}>
          {advancedOpen ? cs.listings.skrytFiltry : cs.listings.rozsireneFiltry}
        </button>

        <button
          className="btn-ghost text-ink-muted hover:text-ink"
          onClick={() => onChange({ page: 1, page_size: value.page_size, is_active: true })}
        >
          {cs.common.vymazatFiltry}
        </button>
      </div>

      {advancedOpen && <AdvancedFiltersPanel value={value} onChange={onChange} />}
    </>
  );
}
