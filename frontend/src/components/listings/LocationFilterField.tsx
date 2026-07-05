import { useEffect, useId, useRef, useState } from "react";
import { api, type ListingFilters, type LocationSuggestion } from "../../api/client";
import { useCachedAsync } from "../../hooks/useAsync";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { cs } from "../../locale/cs";

const KIND_LABELS: Record<LocationSuggestion["kind"], string> = {
  kraj: "Kraj",
  okres: "Okres",
  obec: "Obec",
  ctvrt: "Čtvrť",
  lokalita: "Adresa",
};

type Props = {
  value: ListingFilters;
  onChange: (value: ListingFilters) => void;
};

function filtersToQueryText(filters: ListingFilters): string {
  return filters.search ?? filters.district ?? filters.city ?? "";
}

function applySuggestion(base: ListingFilters, suggestion: LocationSuggestion): ListingFilters {
  const next: ListingFilters = {
    ...base,
    page: 1,
    search: undefined,
    region: undefined,
    district: undefined,
    city: undefined,
  };
  if (suggestion.region) next.region = suggestion.region;
  if (suggestion.district) next.district = suggestion.district;
  if (suggestion.city) next.city = suggestion.city;
  if (suggestion.search) next.search = suggestion.search;
  return next;
}

export function LocationFilterField({ value, onChange }: Props) {
  const listId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState(() => filtersToQueryText(value));
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState(false);
  const debouncedQuery = useDebouncedValue(query, 350);

  const regions = useCachedAsync("inventory-by-region", () => api.inventoryByRegion(), []);
  const suggestions = useCachedAsync(
    `location-suggest-${debouncedQuery.trim().toLowerCase()}`,
    () => (debouncedQuery.trim().length >= 2 ? api.locationSuggest(debouncedQuery.trim()) : Promise.resolve({ items: [] })),
    [debouncedQuery]
  );

  useEffect(() => {
    if (picked) {
      setPicked(false);
      return;
    }
    const trimmed = debouncedQuery.trim();
    onChange({
      ...value,
      page: 1,
      search: trimmed || undefined,
      district: undefined,
      city: undefined,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- debounced free-text search only
  }, [debouncedQuery]);

  useEffect(() => {
    const external = filtersToQueryText(value);
    if (external !== query) {
      setQuery(external);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- external filter reset only
  }, [value.search, value.region, value.district, value.city]);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function selectSuggestion(suggestion: LocationSuggestion) {
    setPicked(true);
    setQuery(suggestion.label);
    onChange(applySuggestion(value, suggestion));
    setOpen(false);
  }

  const showSuggestions = open && debouncedQuery.trim().length >= 2 && (suggestions.data?.items.length ?? 0) > 0;

  return (
    <div className="location-filter" ref={containerRef}>
      <div>
        <label className="field-label" htmlFor={`${listId}-location`}>
          {cs.listings.lokalita}
        </label>
        <input
          id={`${listId}-location`}
          type="search"
          role="combobox"
          aria-expanded={showSuggestions}
          aria-controls={`${listId}-suggestions`}
          aria-autocomplete="list"
          placeholder={cs.listings.lokalitaPlaceholder}
          className="input-field w-full min-w-[12rem] lg:w-64"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
        />
        <p className="text-[11px] text-ink-muted mt-1 leading-snug max-w-xs">{cs.listings.lokalitaNapoveda}</p>
      </div>

      <div>
        <label className="field-label" htmlFor={`${listId}-region`}>
          {cs.listings.kraj}
        </label>
        <select
          id={`${listId}-region`}
          className="select-field min-w-[11rem]"
          value={value.region ?? ""}
          onChange={(e) =>
            onChange({
              ...value,
              page: 1,
              region: e.target.value || undefined,
            })
          }
        >
          <option value="">{cs.listings.vseKraje}</option>
          {(regions.data ?? []).map((row) => (
            <option key={row.region ?? "unknown"} value={row.region ?? ""}>
              {row.region ?? "—"} ({row.listing_count.toLocaleString("cs-CZ")})
            </option>
          ))}
        </select>
      </div>

      {showSuggestions && (
        <ul id={`${listId}-suggestions`} className="location-filter__suggestions" role="listbox">
          {suggestions.data!.items.map((item) => (
            <li key={`${item.kind}-${item.label}`}>
              <button type="button" className="location-filter__option" onClick={() => selectSuggestion(item)}>
                <span>{item.label}</span>
                <span className="location-filter__kind">{KIND_LABELS[item.kind]}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
