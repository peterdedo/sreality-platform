import {
  BUILDING_CONDITION_LABELS,
  BUILDING_TYPE_LABELS,
  ELEVATOR_LABELS,
  ENERGY_EFFICIENCY_RATING_LABELS,
  FURNISHED_LABELS,
  OWNERSHIP_LABELS,
  SELLER_TYPE_LABELS,
} from "../../constants";
import { cs } from "../../locale/cs";
import type { ListingFilters as Filters } from "../../api/client";

interface Props {
  value: Filters;
  onChange: (value: Filters) => void;
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | undefined;
  onChange: (value: number | undefined) => void;
}) {
  return (
    <div>
      <label className="field-label">{label}</label>
      <input
        type="number"
        className="input-field w-full"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
      />
    </div>
  );
}

function CodebookSelect({
  label,
  labels,
  value,
  onChange,
}: {
  label: string;
  labels: Record<string, string>;
  value: string | undefined;
  onChange: (value: string | undefined) => void;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-ink-muted mb-1">{label}</label>
      <select
        className="select-field w-full"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || undefined)}
      >
        <option value="">{cs.listings.vse}</option>
        {Object.entries(labels).map(([code, text]) => (
          <option key={code} value={code}>
            {text}
          </option>
        ))}
      </select>
    </div>
  );
}

function TriStateCheckbox({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | undefined;
  onChange: (value: boolean | undefined) => void;
}) {
  const state = value === true ? "true" : value === false ? "false" : "";
  return (
    <div>
      <label className="block text-xs font-medium text-ink-muted mb-1">{label}</label>
      <select
        className="select-field w-full"
        value={state}
        onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value === "true")}
      >
        <option value="">{cs.listings.vse}</option>
        <option value="true">{cs.listings.ano}</option>
        <option value="false">{cs.listings.ne}</option>
      </select>
    </div>
  );
}

export function AdvancedFiltersPanel({ value, onChange }: Props) {
  function update(patch: Partial<Filters>) {
    onChange({ ...value, ...patch, page: 1 });
  }

  return (
    <div className="bg-surface border border-surface-border rounded-lg p-4 mb-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <NumberField label={cs.listings.plochaOd} value={value.usable_area_min} onChange={(v) => update({ usable_area_min: v })} />
      <NumberField label={cs.listings.plochaDo} value={value.usable_area_max} onChange={(v) => update({ usable_area_max: v })} />
      <NumberField
        label={cs.listings.plochaPozemkuOd}
        value={value.land_area_min}
        onChange={(v) => update({ land_area_min: v })}
      />
      <NumberField
        label={cs.listings.plochaPozemkuDo}
        value={value.land_area_max}
        onChange={(v) => update({ land_area_max: v })}
      />
      <NumberField label={cs.listings.podlaziOd} value={value.floor_number_min} onChange={(v) => update({ floor_number_min: v })} />
      <NumberField label={cs.listings.podlaziDo} value={value.floor_number_max} onChange={(v) => update({ floor_number_max: v })} />

      <NumberField
        label={`${cs.listings.cenaZaM2} ${cs.listings.cenaOd.toLowerCase()}`}
        value={value.price_per_m2_min}
        onChange={(v) => update({ price_per_m2_min: v })}
      />
      <NumberField
        label={`${cs.listings.cenaZaM2} ${cs.listings.cenaDo.toLowerCase()}`}
        value={value.price_per_m2_max}
        onChange={(v) => update({ price_per_m2_max: v })}
      />
      <NumberField label={cs.listings.dnyNaTrhuOd} value={value.days_on_market_min} onChange={(v) => update({ days_on_market_min: v })} />
      <NumberField label={cs.listings.dnyNaTrhuDo} value={value.days_on_market_max} onChange={(v) => update({ days_on_market_max: v })} />

      <CodebookSelect
        label={cs.listings.vlastnictvi}
        labels={OWNERSHIP_LABELS}
        value={value.ownership}
        onChange={(v) => update({ ownership: v })}
      />
      <CodebookSelect
        label={cs.listings.typBudovy}
        labels={BUILDING_TYPE_LABELS}
        value={value.building_type}
        onChange={(v) => update({ building_type: v })}
      />
      <CodebookSelect
        label={cs.listings.stavBudovy}
        labels={BUILDING_CONDITION_LABELS}
        value={value.building_condition}
        onChange={(v) => update({ building_condition: v })}
      />
      <CodebookSelect
        label={cs.listings.energetickyStitek}
        labels={ENERGY_EFFICIENCY_RATING_LABELS}
        value={value.energy_efficiency_rating}
        onChange={(v) => update({ energy_efficiency_rating: v })}
      />
      <CodebookSelect
        label={cs.listings.vybaveni}
        labels={FURNISHED_LABELS}
        value={value.furnished}
        onChange={(v) => update({ furnished: v })}
      />
      <CodebookSelect
        label={cs.listings.vytah}
        labels={ELEVATOR_LABELS}
        value={value.elevator}
        onChange={(v) => update({ elevator: v })}
      />
      <CodebookSelect
        label={cs.listings.typInzerenta}
        labels={SELLER_TYPE_LABELS}
        value={value.seller_type}
        onChange={(v) => update({ seller_type: v })}
      />

      <TriStateCheckbox label={cs.listings.balkon} value={value.balcony} onChange={(v) => update({ balcony: v })} />
      <TriStateCheckbox label={cs.listings.terasa} value={value.terrace} onChange={(v) => update({ terrace: v })} />
      <TriStateCheckbox label={cs.listings.sklep} value={value.cellar} onChange={(v) => update({ cellar: v })} />
      <TriStateCheckbox label={cs.listings.garaz} value={value.garage} onChange={(v) => update({ garage: v })} />
      <TriStateCheckbox label={cs.listings.zahrada} value={value.garden} onChange={(v) => update({ garden: v })} />
      <TriStateCheckbox label={cs.listings.parkovani} value={value.has_parking} onChange={(v) => update({ has_parking: v })} />

      <div>
        <label className="block text-xs font-medium text-ink-muted mb-1">{cs.listings.kraj}</label>
        <input
          type="text"
          className="select-field w-full"
          placeholder={cs.listings.krajPlaceholder}
          value={value.region ?? ""}
          onChange={(e) => update({ region: e.target.value || undefined })}
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-ink-muted mb-1">{cs.listings.okres}</label>
        <input
          type="text"
          className="select-field w-full"
          value={value.district ?? ""}
          onChange={(e) => update({ district: e.target.value || undefined })}
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-ink-muted mb-1">{cs.listings.mesto}</label>
        <input
          type="text"
          className="select-field w-full"
          value={value.city ?? ""}
          onChange={(e) => update({ city: e.target.value || undefined })}
        />
      </div>

      <div className="flex items-end">
        <label className="flex items-center gap-2 text-sm text-ink mb-1.5">
          <input
            type="checkbox"
            checked={value.has_price_drop === true}
            onChange={(e) => update({ has_price_drop: e.target.checked ? true : undefined })}
          />
          {cs.listings.jenSePoklesemCeny}
        </label>
      </div>
    </div>
  );
}
