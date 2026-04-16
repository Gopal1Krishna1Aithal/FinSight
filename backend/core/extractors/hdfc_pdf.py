import re
import os
from pathlib import Path

# Column x-coordinate boundaries derived from the HDFC statement header row.
COL_BOUNDARIES = [
    ('Date',       0,   70),
    ('Narration',  70,  285),
    ('Ref_No',     285, 358),
    ('Value_Date', 358, 400),
    ('Debit',      400, 488),
    ('Credit',     488, 560),
    ('Balance',    560, 640),
]

# Matches DD/MM/YY or DD/MM/YYYY in the Date column only
DATE_PATTERN = re.compile(r'^\d{2}/\d{2}/\d{2,4}$')

def _assign_col(x0: float) -> str | None:
    for name, start, end in COL_BOUNDARIES:
        if start <= x0 < end:
            return name
    return None

def _find_table_bounds(words: list[dict], page_height: float) -> tuple[float, float]:
    table_start = None
    for w in words:
        if w["text"] == "Date" and w["x0"] < 70:
            table_start = w["top"] + 15
            break
    if table_start is None:
        for w in words:
            if DATE_PATTERN.match(w["text"]) and w["x0"] < 70:
                table_start = w["top"] - 2
                break
    if table_start is None:
        return (page_height, page_height)
    table_end = page_height
    for w in words:
        if w["top"] <= table_start + 50:
            continue
        text = w["text"].replace(" ", "")
        if (
            text.startswith("PageNo")
            or text.startswith("STATEMENT")
            or text.startswith("*Closing")
        ):
            table_end = min(table_end, w["top"])
    return (table_start, table_end)

def _extract_page_rows(page) -> list[dict]:
    words = page.extract_words()
    table_start, table_end = _find_table_bounds(words, page.height)
    if table_start >= table_end:
        return []
    raw_rows: dict[int, dict] = {}
    for w in words:
        if not (table_start <= w["top"] < table_end):
            continue
        col = _assign_col(w["x0"])
        if col is None:
            continue
        row_key = round(w["top"] / 3) * 3
        if row_key not in raw_rows:
            raw_rows[row_key] = {}
        existing = raw_rows[row_key].get(col, "")
        raw_rows[row_key][col] = (existing + " " + w["text"]) if existing else w["text"]
    return [cols for _, cols in sorted(raw_rows.items())]

class HDFCPDFExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract(self) -> list[dict] | None:
        import pdfplumber
        all_rows: list[dict] = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    all_rows.extend(_extract_page_rows(page))
        except Exception as e:
            print(f"[HDFCPDFExtractor] Extraction error: {e}")
            return None
        return self._merge_continuations(all_rows)

    def _merge_continuations(self, rows: list[dict]) -> list[dict]:
        merged: list[dict] = []
        cols = [name for name, *_ in COL_BOUNDARIES]
        for row in rows:
            has_date = DATE_PATTERN.match(row.get("Date", ""))
            has_numbers = any(row.get(c, "").strip() for c in ("Debit", "Credit", "Balance"))
            if has_date or has_numbers:
                for col in cols:
                    row.setdefault(col, "")
                merged.append(row)
            else:
                if merged and row.get("Narration", "").strip():
                    merged[-1]["Narration"] += " " + row["Narration"].strip()
        return merged
