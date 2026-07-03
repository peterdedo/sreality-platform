import { useState } from "react";
import { cs } from "../../locale/cs";
import { LISTING_COLUMNS } from "./columns";

interface Props {
  visibleColumns: string[];
  onChange: (columns: string[]) => void;
}

export function ColumnSelector({ visibleColumns, onChange }: Props) {
  const [open, setOpen] = useState(false);

  function toggle(key: string) {
    if (visibleColumns.includes(key)) {
      onChange(visibleColumns.filter((c) => c !== key));
    } else {
      onChange([...visibleColumns, key]);
    }
  }

  return (
    <div className="relative">
      <button
        className="btn-secondary"
        onClick={() => setOpen((v) => !v)}
      >
        {cs.listings.sloupce} ({visibleColumns.length})
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-1 z-20 panel-static shadow-nav p-2 w-64 max-h-80 overflow-y-auto">
            {LISTING_COLUMNS.map((col) => (
              <label key={col.key} className="flex items-center gap-2 px-2 py-1.5 text-sm hover:bg-surface-muted rounded cursor-pointer">
                <input type="checkbox" checked={visibleColumns.includes(col.key)} onChange={() => toggle(col.key)} />
                {col.label}
              </label>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
