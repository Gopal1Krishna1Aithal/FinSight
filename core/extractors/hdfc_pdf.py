# import re
# import pdfplumber

# # Column x-coordinate boundaries derived from the HDFC statement header row.
# # These are fixed for this PDF layout. Each tuple is (col_name, x_start, x_end).
# COL_BOUNDARIES = [
#     ('Date',       0,   70),
#     ('Narration',  70,  285),
#     ('Ref_No',     285, 358),
#     ('Value_Date', 358, 400),
#     ('Debit',      400, 488),
#     ('Credit',     488, 560),
#     ('Balance',    560, 640),
# ]

# # Matches DD/MM/YY or DD/MM/YYYY in the Date column only
# DATE_PATTERN = re.compile(r'^\d{2}/\d{2}/\d{2,4}$')


# def _assign_col(x0: float) -> str | None:
#     """Return the column name for a word starting at x0, or None if out of bounds."""
#     for name, start, end in COL_BOUNDARIES:
#         if start <= x0 < end:
#             return name
#     return None


# def _find_table_bounds(words: list[dict], page_height: float) -> tuple[float, float]:
#     """
#     Return (table_start_y, table_end_y) for a single page.

#     - table_start_y: y just below the header row (page 1) OR the first
#       transaction date (page 2+). We detect which case we're in by looking
#       for the word 'Date' at x0 < 70 — that's the column header, not the
#       account-info 'A/C Open Date' which sits at x0 > 300.
#     - table_end_y: the top of 'Page No.' text, 'STATEMENT' summary, or the
#       HDFC footer block — whichever comes first after the table body.
#     """
#     table_start = None

#     # Case 1: page has a header row — 'Date' in the Date column (x0 < 70)
#     for w in words:
#         if w['text'] == 'Date' and w['x0'] < 70:
#             table_start = w['top'] + 10   # skip the header row itself
#             break

#     # Case 2: no header (pages 2+) — use first transaction date
#     if table_start is None:
#         for w in words:
#             if DATE_PATTERN.match(w['text']) and w['x0'] < 70:
#                 table_start = w['top'] - 2
#                 break

#     if table_start is None:
#         return (page_height, page_height)   # nothing to extract

#     # Footer boundary: 'Page No.' run-together text ('PageNo.:'), or
#     # 'STATEMENT' (summary block), whichever is lower on the page.
#     table_end = page_height
#     for w in words:
#         if w['top'] <= table_start + 50:    # must be well below the table start
#             continue
#         text = w['text'].replace(' ', '')
#         if text.startswith('PageNo') or text.startswith('STATEMENT'):
#             table_end = min(table_end, w['top'])

#     return (table_start, table_end)


# def _extract_page_rows(page) -> list[dict]:
#     """
#     Extract all transaction rows from one PDF page as a list of dicts,
#     each with keys matching COL_BOUNDARIES column names.
#     """
#     words = page.extract_words()
#     table_start, table_end = _find_table_bounds(words, page.height)

#     if table_start >= table_end:
#         return []

#     # Group words into visual rows by rounding their y-coordinate.
#     # A tolerance of 3pt handles slight vertical misalignment within one row.
#     raw_rows: dict[int, dict] = {}
#     for w in words:
#         if not (table_start <= w['top'] < table_end):
#             continue
#         col = _assign_col(w['x0'])
#         if col is None:
#             continue
#         row_key = round(w['top'] / 3) * 3
#         if row_key not in raw_rows:
#             raw_rows[row_key] = {}
#         # Concatenate words that share the same cell (e.g. multi-word narrations)
#         raw_rows[row_key][col] = raw_rows[row_key].get(col, '') + w['text']

#     return [cols for _, cols in sorted(raw_rows.items())]


# class HDFCPDFExtractor:
#     def __init__(self, pdf_path: str):
#         self.pdf_path = pdf_path

#     def extract(self) -> list[dict] | None:
#         """
#         Return a flat list of row-dicts across all pages, with multiline
#         continuation rows (e.g. 'S DEBIT') already merged into their parent.

#         Each dict has keys: Date, Narration, Ref_No, Value_Date,
#                             Debit, Credit, Balance
#         Missing values are empty strings (never None).
#         """
#         all_rows: list[dict] = []

#         try:
#             with pdfplumber.open(self.pdf_path) as pdf:
#                 for page in pdf.pages:
#                     all_rows.extend(_extract_page_rows(page))
#         except Exception as e:
#             print(f"[HDFCPDFExtractor] Extraction error: {e}")
#             return None

#         return self._merge_continuations(all_rows)

#     # ------------------------------------------------------------------
#     # Private helpers
#     # ------------------------------------------------------------------

#     def _merge_continuations(self, rows: list[dict]) -> list[dict]:
#         """
#         Merge narration-only continuation rows (like 'SDEBIT', 'EBIT',
#         'COMMENTS', or IMPS sub-lines) into the preceding transaction row.

#         A row is a continuation if:
#           - It has no Date
#           - It has no numeric values (Debit / Credit / Balance)
#         """
#         merged: list[dict] = []
#         cols = [name for name, *_ in COL_BOUNDARIES]

#         for row in rows:
#             has_date = DATE_PATTERN.match(row.get('Date', ''))
#             has_numbers = any(
#                 row.get(c, '').strip()
#                 for c in ('Debit', 'Credit', 'Balance')
#             )

#             if has_date or has_numbers:
#                 # Ensure every column key exists
#                 for col in cols:
#                     row.setdefault(col, '')
#                 merged.append(row)
#             else:
#                 # Continuation — append narration text to previous row
#                 if merged and row.get('Narration', '').strip():
#                     merged[-1]['Narration'] += ' ' + row['Narration'].strip()

#         return merged








import re
import pdfplumber

# Column x-coordinate boundaries derived from the HDFC statement header row.
# These are fixed for this PDF layout. Each tuple is (col_name, x_start, x_end).
#
# Three boundaries widened (marked *) to support both the original scanned layout
# AND the newer computer-generated (Axiom-style) layout, while remaining fully
# backward-compatible with the original PDF:
#
#   Narration end : 285 → 270*  (right edge trimmed to give Ref_No room)
#   Ref_No  start : 285 → 270*  (Axiom ref-numbers start at x0 ≈ 275)
#   Debit   end   : 488 → 470*  (right edge trimmed to give Credit room)
#   Credit  start : 488 → 470*  (Axiom deposit amounts start at x0 ≈ 477)
#   Balance start : 560 → 535*  (Axiom balance amounts start at x0 ≈ 540)
#
# Original PDF amounts remain within their original columns:
#   Debit   x0 ≈ 438–456  → 400–470  ✓
#   Credit  x0 ≈ 516–534  → 470–535  ✓
#   Balance x0 ≈ 594–608  → 535–640  ✓
COL_BOUNDARIES = [
    ('Date',       0,   70),
    ('Narration',  70,  270),   # end: 285 → 270
    ('Ref_No',     270, 358),   # start: 285 → 270
    ('Value_Date', 358, 400),
    ('Debit',      400, 470),   # end: 488 → 470
    ('Credit',     470, 535),   # start: 488 → 470; end: 560 → 535
    ('Balance',    535, 640),   # start: 560 → 535
]

# Matches DD/MM/YY or DD/MM/YYYY in the Date column only
DATE_PATTERN = re.compile(r'^\d{2}/\d{2}/\d{2,4}$')


def _assign_col(x0: float) -> str | None:
    """Return the column name for a word starting at x0, or None if out of bounds."""
    for name, start, end in COL_BOUNDARIES:
        if start <= x0 < end:
            return name
    return None


def _find_table_bounds(words: list[dict], page_height: float) -> tuple[float, float]:
    """
    Return (table_start_y, table_end_y) for a single page.

    - table_start_y: y just below the header row (page 1) OR the first
      transaction date (page 2+). We detect which case we're in by looking
      for the word 'Date' at x0 < 70 — that's the column header, not the
      account-info 'A/C Open Date' which sits at x0 > 300.
    - table_end_y: the top of 'Page No.' text, 'STATEMENT' summary, or the
      HDFC footer block — whichever comes first after the table body.
    """
    table_start = None

    # Case 1: page has a header row — 'Date' in the Date column (x0 < 70)
    for w in words:
        if w['text'] == 'Date' and w['x0'] < 70:
            # +15 clears both single-line headers (original PDF) and two-line
            # headers like "Withdrawal / Amt. (Rs.)" in modern PDFs, while
            # still including the first transaction row in both cases.
            table_start = w['top'] + 15
            break

    # Case 2: no header (pages 2+) — use first transaction date
    if table_start is None:
        for w in words:
            if DATE_PATTERN.match(w['text']) and w['x0'] < 70:
                table_start = w['top'] - 2
                break

    if table_start is None:
        return (page_height, page_height)   # nothing to extract

    # Footer boundary: 'Page No.' run-together text ('PageNo.:'), or
    # 'STATEMENT' (summary block), or 'HDFC BANK LIMITED' footer line —
    # whichever comes first after the table body.
    table_end = page_height
    for w in words:
        if w['top'] <= table_start + 50:    # must be well below the table start
            continue
        text = w['text'].replace(' ', '')
        if (text.startswith('PageNo')
                or text.startswith('STATEMENT')
                or text.startswith('*Closing')):   # footer line present in all layouts
            table_end = min(table_end, w['top'])

    return (table_start, table_end)


def _extract_page_rows(page) -> list[dict]:
    """
    Extract all transaction rows from one PDF page as a list of dicts,
    each with keys matching COL_BOUNDARIES column names.
    """
    words = page.extract_words()
    table_start, table_end = _find_table_bounds(words, page.height)

    if table_start >= table_end:
        return []

    # Group words into visual rows by rounding their y-coordinate.
    # A tolerance of 3pt handles slight vertical misalignment within one row.
    raw_rows: dict[int, dict] = {}
    for w in words:
        if not (table_start <= w['top'] < table_end):
            continue
        col = _assign_col(w['x0'])
        if col is None:
            continue
        row_key = round(w['top'] / 3) * 3
        if row_key not in raw_rows:
            raw_rows[row_key] = {}
        # Concatenate words that share the same cell (e.g. multi-word narrations).
        # Space separator ensures words are joined correctly in computer-generated
        # PDFs where each word is extracted individually (unlike scanned PDFs where
        # pdfplumber merges adjacent text into a single word token).
        existing = raw_rows[row_key].get(col, '')
        raw_rows[row_key][col] = (existing + ' ' + w['text']) if existing else w['text']

    return [cols for _, cols in sorted(raw_rows.items())]


class HDFCPDFExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract(self) -> list[dict] | None:
        """
        Return a flat list of row-dicts across all pages, with multiline
        continuation rows (e.g. 'S DEBIT') already merged into their parent.

        Each dict has keys: Date, Narration, Ref_No, Value_Date,
                            Debit, Credit, Balance
        Missing values are empty strings (never None).
        """
        all_rows: list[dict] = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    all_rows.extend(_extract_page_rows(page))
        except Exception as e:
            print(f"[HDFCPDFExtractor] Extraction error: {e}")
            return None

        return self._merge_continuations(all_rows)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _merge_continuations(self, rows: list[dict]) -> list[dict]:
        """
        Merge narration-only continuation rows (like 'SDEBIT', 'EBIT',
        'COMMENTS', or IMPS sub-lines) into the preceding transaction row.

        A row is a continuation if:
          - It has no Date
          - It has no numeric values (Debit / Credit / Balance)
        """
        merged: list[dict] = []
        cols = [name for name, *_ in COL_BOUNDARIES]

        for row in rows:
            has_date = DATE_PATTERN.match(row.get('Date', ''))
            has_numbers = any(
                row.get(c, '').strip()
                for c in ('Debit', 'Credit', 'Balance')
            )

            if has_date or has_numbers:
                # Ensure every column key exists
                for col in cols:
                    row.setdefault(col, '')
                merged.append(row)
            else:
                # Continuation — append narration text to previous row
                if merged and row.get('Narration', '').strip():
                    merged[-1]['Narration'] += ' ' + row['Narration'].strip()

        return merged