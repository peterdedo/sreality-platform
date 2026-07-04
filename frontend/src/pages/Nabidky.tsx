import { useMemo, useState } from "react";
import { api, type ListingFilters } from "../api/client";
import { PageContainer } from "../components/layout/PageContainer";
import { ListingFiltersBar } from "../components/listings/ListingFilters";
import { ListingsTable } from "../components/listings/ListingsTable";
import { ColumnSelector } from "../components/listings/ColumnSelector";
import { SavedViews } from "../components/listings/SavedViews";
import { DEFAULT_VISIBLE_COLUMNS } from "../components/listings/columns";
import { ExportButton, type ExportScopeOption } from "../components/export/ExportButton";
import { DatasetSnapshotIndicator } from "../components/DatasetSnapshotIndicator";
import { ErrorState, LoadingState } from "../components/StateHelpers";
import { RefreshIndicator } from "../components/ui/RefreshIndicator";
import { useAsync } from "../hooks/useAsync";
import { useDatasetSummary } from "../hooks/useDatasetSummary";
import { cs } from "../locale/cs";

const COLUMNS_STORAGE_KEY = "sreality:visibleListingColumns";

function loadVisibleColumns(): string[] {
  try {
    const raw = localStorage.getItem(COLUMNS_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : DEFAULT_VISIBLE_COLUMNS;
  } catch {
    return DEFAULT_VISIBLE_COLUMNS;
  }
}

function filtersCacheKey(filters: ListingFilters): string {
  return JSON.stringify(filters);
}

export function Nabidky() {
  const [filters, setFilters] = useState<ListingFilters>({ page: 1, page_size: 25, is_active: true });
  const [visibleColumns, setVisibleColumns] = useState<string[]>(loadVisibleColumns);
  const filtersKey = useMemo(() => filtersCacheKey(filters), [filters]);
  const summary = useDatasetSummary();
  const { data, loading, error, refreshing } = useAsync(() => api.listings(filters), [filtersKey]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  function updateVisibleColumns(columns: string[]) {
    setVisibleColumns(columns);
    localStorage.setItem(COLUMNS_STORAGE_KEY, JSON.stringify(columns));
  }

  const hasActiveFilters = Object.keys(filters).some(
    (key) => !["page", "page_size", "is_active", "sort_by", "sort_dir"].includes(key)
  );

  const exportScopes: ExportScopeOption[] = [
    {
      value: "filtered",
      label: hasActiveFilters ? cs.export.exportFiltrovanychDat : cs.export.exportAktualniTabulky,
      run: (format) => api.export.listings("cleaned", format, { ...filters, page: undefined, page_size: undefined }),
    },
    {
      value: "raw",
      label: cs.export.exportSurovychDat,
      run: (format) => api.export.listings("raw", format, { ...filters, page: undefined, page_size: undefined }),
    },
  ];

  return (
    <PageContainer title={cs.listings.titulek} subtitle={cs.listings.podtitulek}>
      {summary.data && <DatasetSnapshotIndicator summary={summary.data} compact />}
      <ListingFiltersBar value={filters} onChange={setFilters} />

      <div className="flex items-center justify-end gap-2 mb-3">
        <SavedViews
          currentFilters={filters}
          currentColumns={visibleColumns}
          onApply={(f, c) => {
            setFilters(f);
            updateVisibleColumns(c);
          }}
        />
        <ColumnSelector visibleColumns={visibleColumns} onChange={updateVisibleColumns} />
        <ExportButton scopes={exportScopes} />
      </div>

      {loading && !data && <LoadingState />}
      {refreshing && <RefreshIndicator active />}
      {error && <ErrorState message={error.message} />}
      {data && (
        <>
          <ListingsTable
            items={data.items}
            visibleColumns={visibleColumns}
            sortBy={filters.sort_by}
            sortDir={filters.sort_dir}
            onSortChange={(sortBy, sortDir) => setFilters((f) => ({ ...f, sort_by: sortBy, sort_dir: sortDir, page: 1 }))}
          />
          <div className="flex items-center justify-between mt-4 text-sm text-ink-muted">
            <span className="font-medium">
              {cs.common.celkemDleFiltru}: <span className="text-brand tabular-nums">{data.total}</span>
            </span>
            <div className="flex gap-2 items-center">
              <button
                className="btn-pagination"
                disabled={(filters.page ?? 1) <= 1}
                onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
              >
                {cs.common.predchozi}
              </button>
              <span className="tabular-nums px-1">
                {cs.common.stranaZ.replace("{page}", String(filters.page ?? 1)).replace("{pages}", String(totalPages))}
              </span>
              <button
                className="btn-pagination"
                disabled={(filters.page ?? 1) >= totalPages}
                onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
              >
                {cs.common.dalsi}
              </button>
            </div>
          </div>
        </>
      )}
    </PageContainer>
  );
}
