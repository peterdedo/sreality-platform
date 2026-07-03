"""Serializes tabular row data (list[dict]) into the export file formats the
API exposes. Kept separate from the endpoints in app/api/export.py so the
same serialization logic can be unit tested without a database.

Format notes:
- CSV is written with a UTF-8 BOM (utf-8-sig): Excel on Windows otherwise
  misreads plain UTF-8 CSVs containing Czech diacritics as a different
  codepage. Values themselves are never ASCII-folded -- the BOM is the fix,
  not mangling the data.
- XLSX uses openpyxl via pandas, with the header row bolded and frozen so
  large exports stay usable when scrolled.
- JSON is written with ensure_ascii=False so diacritics stay as literal
  UTF-8 characters instead of \\uXXXX escapes.
- Parquet uses pyarrow, useful for downstream analysis in pandas/DuckDB/Spark
  without a re-parsing step.
"""

import io
import json
import math
from datetime import date, datetime
from typing import Any

import pandas as pd
from openpyxl.styles import Font

SUPPORTED_FORMATS = ("csv", "xlsx", "json", "parquet")

_MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json; charset=utf-8",
    "parquet": "application/octet-stream",
}


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _clean_nan(value: Any) -> Any:
    """float('nan') is not valid JSON (json.dumps emits a bare `NaN` token
    that most strict JSON parsers reject) and pandas produces it whenever a
    numeric column has a missing value -- e.g. pct_change() on the first row
    of a group, or a rolling window that hasn't filled yet. Rows built from
    pandas (the analytics time-series export) must be scrubbed before any
    format is serialized, not just JSON, so CSV/XLSX/Parquet consumers don't
    see the literal string "nan" either."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def serialize_rows(rows: list[dict], fmt: str, filename_stem: str) -> tuple[bytes, str, str]:
    """Returns (content_bytes, media_type, filename) for the given rows and format."""
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Nepodporovaný formát exportu: {fmt}. Podporované formáty: {', '.join(SUPPORTED_FORMATS)}")

    rows = [{k: _clean_nan(v) for k, v in row.items()} for row in rows]

    media_type = _MEDIA_TYPES[fmt]
    filename = f"{filename_stem}.{fmt}"

    if fmt == "json":
        content = json.dumps(rows, ensure_ascii=False, default=_json_default, indent=2).encode("utf-8")
        return content, media_type, filename

    df = pd.DataFrame(rows)

    if fmt == "csv":
        content = df.to_csv(index=False).encode("utf-8-sig")
        return content, media_type, filename

    if fmt == "xlsx":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="data")
            sheet = writer.sheets["data"]
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            for column_cells in sheet.columns:
                max_len = max((len(str(c.value)) for c in column_cells if c.value is not None), default=10)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max_len + 2, 60)
        return buf.getvalue(), media_type, filename

    # parquet
    buf = io.BytesIO()
    df.to_parquet(buf, engine="pyarrow", index=False)
    return buf.getvalue(), media_type, filename
