import { useEffect, useState } from "react";
import type { ListingFilters as Filters } from "../../api/client";
import { cs } from "../../locale/cs";

interface SavedView {
  name: string;
  filters: Filters;
  columns: string[];
}

const STORAGE_KEY = "sreality:savedListingViews";

function loadViews(): SavedView[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SavedView[]) : [];
  } catch {
    return [];
  }
}

function persistViews(views: SavedView[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(views));
}

interface Props {
  currentFilters: Filters;
  currentColumns: string[];
  onApply: (filters: Filters, columns: string[]) => void;
}

export function SavedViews({ currentFilters, currentColumns, onApply }: Props) {
  const [views, setViews] = useState<SavedView[]>([]);
  const [open, setOpen] = useState(false);
  const [nameInput, setNameInput] = useState("");

  useEffect(() => {
    setViews(loadViews());
  }, []);

  function save() {
    const name = nameInput.trim();
    if (!name) return;
    const next = [...views.filter((v) => v.name !== name), { name, filters: currentFilters, columns: currentColumns }];
    setViews(next);
    persistViews(next);
    setNameInput("");
  }

  function remove(name: string) {
    const next = views.filter((v) => v.name !== name);
    setViews(next);
    persistViews(next);
  }

  return (
    <div className="relative">
      <button
        className="btn-secondary"
        onClick={() => setOpen((v) => !v)}
      >
        {cs.listings.ulozenePohledy}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-1 z-20 panel-static shadow-nav p-3 w-72">
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                placeholder={cs.listings.nazevPohledu}
                className="input-field flex-1"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && save()}
              />
              <button
                className="btn-primary !px-3 disabled:opacity-40"
                disabled={!nameInput.trim()}
                onClick={save}
              >
                {cs.listings.ulozitPohled}
              </button>
            </div>

            {views.length === 0 && <p className="text-sm text-ink-muted/70">{cs.listings.zadnePohledy}</p>}

            <ul className="space-y-1 max-h-56 overflow-y-auto">
              {views.map((v) => (
                <li key={v.name} className="flex items-center justify-between gap-2">
                  <button
                    className="text-sm text-left flex-1 px-2 py-1 rounded hover:bg-surface-muted text-ink"
                    onClick={() => {
                      onApply(v.filters, v.columns);
                      setOpen(false);
                    }}
                  >
                    {v.name}
                  </button>
                  <button className="text-xs text-danger hover:underline" onClick={() => remove(v.name)}>
                    {cs.listings.smazatPohled}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
