import { cs } from "../../locale/cs";

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function TablePagination({ page, pageSize, total, onPageChange }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mt-4 text-sm text-ink-muted">
      <span>
        {cs.common.zobrazenoRozsah
          .replace("{from}", String(from))
          .replace("{to}", String(to))
          .replace("{total}", String(total))}
      </span>
      <div className="flex gap-2 items-center">
        <button className="btn-pagination" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          {cs.common.predchozi}
        </button>
        <span className="tabular-nums px-1">
          {cs.common.stranaZ.replace("{page}", String(page)).replace("{pages}", String(totalPages))}
        </span>
        <button className="btn-pagination" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          {cs.common.dalsi}
        </button>
      </div>
    </div>
  );
}

export const ADVANCED_TABLE_PAGE_SIZE = 25;
