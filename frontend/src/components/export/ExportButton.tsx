import { useState } from "react";
import type { ExportFormat } from "../../api/client";
import { cs } from "../../locale/cs";

export interface ExportScopeOption {
  value: string;
  label: string;
  run: (format: ExportFormat) => Promise<void>;
}

interface Props {
  scopes: ExportScopeOption[];
}

const FORMAT_OPTIONS: { value: ExportFormat; label: string }[] = [
  { value: "csv", label: "CSV" },
  { value: "xlsx", label: "XLSX (Excel)" },
  { value: "json", label: "JSON" },
  { value: "parquet", label: "Parquet" },
];

/** Generic export dropdown: pick a scope (what to export) and a format (how),
 * then trigger the download. Scopes are supplied by the page, since what's
 * exportable differs between the listings table and the analytics pages. */
export function ExportButton({ scopes }: Props) {
  const [open, setOpen] = useState(false);
  const [scopeValue, setScopeValue] = useState(scopes[0]?.value ?? "");
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedScope = scopes.find((s) => s.value === scopeValue) ?? scopes[0];

  async function handleDownload() {
    if (!selectedScope) return;
    setBusy(true);
    setError(null);
    try {
      await selectedScope.run(format);
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : cs.export.exportSelhal);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative">
      <button
        className="btn-secondary"
        onClick={() => setOpen((v) => !v)}
      >
        {cs.export.export}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-1 z-20 panel-static shadow-nav p-3 w-72 space-y-3">
            <div>
              <label className="field-label">{cs.export.rozsahExportu}</label>
              <select
                className="select-field w-full"
                value={scopeValue}
                onChange={(e) => setScopeValue(e.target.value)}
              >
                {scopes.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="field-label">{cs.export.formatExportu}</label>
              <select
                className="select-field w-full"
                value={format}
                onChange={(e) => setFormat(e.target.value as ExportFormat)}
              >
                {FORMAT_OPTIONS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>

            <p className="text-xs text-ink-muted leading-relaxed">{cs.export.rozsahNapoveda}</p>

            {error && <p className="text-xs text-danger">{error}</p>}

            <button
              className="w-full btn-primary disabled:opacity-50"
              disabled={busy || !selectedScope}
              onClick={handleDownload}
            >
              {busy ? cs.export.exportujeSe : cs.export.stahnout}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
