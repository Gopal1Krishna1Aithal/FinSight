"""
compare_extractors.py  — run from backend/ directory:
    python compare_extractors.py

Runs both HDFCPDFExtractor and UniversalPDFExtractor on the same PDF
and prints a side-by-side comparison so you can validate what each finds.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# ── Config: point at any PDF you want to compare ──────────────────────────
import glob

PDF_FOLDER = os.path.join("data", "input", "pdfs")
all_pdfs = sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))
if not all_pdfs:
    all_pdfs = sorted(glob.glob(os.path.join("data", "input", "*.pdf")))

if not all_pdfs:
    print("[!] No PDFs found in data/input/pdfs/. Place a PDF there and rerun.")
    sys.exit(1)

PDF_PATH = all_pdfs[0]
print(f"\nComparing extractors on: {os.path.basename(PDF_PATH)}\n{'='*60}")

# ── HDFC pdfplumber extractor ──────────────────────────────────────────────
print("\n[1] Running HDFCPDFExtractor (pdfplumber, no API)...", flush=True)
from core.extractors.hdfc_pdf import HDFCPDFExtractor
hdfc_rows = HDFCPDFExtractor(PDF_PATH).extract() or []
print(f"    → {len(hdfc_rows)} rows extracted")

# ── Universal Gemini extractor ─────────────────────────────────────────────
print("\n[2] Running UniversalPDFExtractor (Gemini API)...", flush=True)
from core.extractors.universal_pdf import UniversalPDFExtractor
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("    [!] GEMINI_API_KEY not set — skipping universal extractor.")
    univ_rows = []
else:
    univ_rows = UniversalPDFExtractor(PDF_PATH, api_key=api_key).extract() or []
    print(f"    → {len(univ_rows)} rows extracted")

# ── Validation report for both ─────────────────────────────────────────────
from core.extractors.extraction_validator import ExtractionValidator

print("\n── HDFC Extractor Validation ──")
r_hdfc = ExtractionValidator(hdfc_rows).validate()
print(r_hdfc.report())

if univ_rows:
    print("\n── Universal Extractor Validation ──")
    r_univ = ExtractionValidator(univ_rows).validate()
    print(r_univ.report())

# ── Side-by-side first 5 rows ──────────────────────────────────────────────
def show_rows(label, rows, n=5):
    print(f"\n{'─'*60}\n  {label} — first {n} rows:\n{'─'*60}")
    for i, row in enumerate(rows[:n]):
        print(f"  [{i+1}] Date={row.get('Date','?')!r:12} "
              f"Debit={row.get('Debit','?'):>12} "
              f"Credit={row.get('Credit','?'):>12} "
              f"Balance={row.get('Balance','?'):>14}  "
              f"Narration={row.get('Narration','?')[:45]!r}")

show_rows("HDFC extractor", hdfc_rows)
if univ_rows:
    show_rows("Universal extractor", univ_rows)

# ── Summary diff ───────────────────────────────────────────────────────────
def sum_col(rows, col):
    total = 0.0
    for r in rows:
        try:
            total += float(str(r.get(col, '') or '').replace(',', '') or 0)
        except ValueError:
            pass
    return total

print(f"\n{'='*60}\n  SUMMARY\n{'='*60}")
print(f"  HDFC extractor     : {len(hdfc_rows):>4} rows")
if univ_rows:
    print(f"  Universal extractor: {len(univ_rows):>4} rows")
    diff = len(univ_rows) - len(hdfc_rows)
    if diff == 0:
        print("  ✅ Row counts match exactly.")
    elif abs(diff) <= 3:
        print(f"  ⚠  Difference of {diff:+d} rows — likely header/footer rows. Inspect manually.")
    else:
        print(f"  ❌ Significant difference ({diff:+d} rows) — one extractor may have missed rows.")

    for col in ("Debit", "Credit"):
        hdfc_sum = sum_col(hdfc_rows, col)
        univ_sum = sum_col(univ_rows, col)
        match = "✅" if abs(hdfc_sum - univ_sum) < 1.0 else "❌"
        print(f"  {match} Total {col:6}: HDFC=₹{hdfc_sum:>14,.2f}  Universal=₹{univ_sum:>14,.2f}  diff=₹{abs(hdfc_sum-univ_sum):.2f}")
else:
    for col in ("Debit", "Credit"):
        print(f"  Total {col}: HDFC=₹{sum_col(hdfc_rows, col):>14,.2f}")

print()
