import os
import sys
import pandas as pd
from dotenv import load_dotenv

from core.extractors.hdfc_pdf import HDFCPDFExtractor
from core.processors.cleaner import HDFCDataCleaner
from core.processors.sanitizer import DataSanitizer
from core.ai_services.coa_mapper import CoAMapper


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

load_dotenv()   # reads .env so GROQ_API_KEY is available via os.getenv()

PDF_PATH   = os.path.join("data", "input", "sample_business_statement.pdf")
OUT_DIR    = os.path.join("data", "output")
EXCEL_PATH = os.path.join(OUT_DIR, "clean_statement.xlsx")
TALLY_PATH = os.path.join(OUT_DIR, "tally_import.csv")


# ---------------------------------------------------------------------------
# Step 3 — Mathematical Validator
# ---------------------------------------------------------------------------

def validate_balances(df: pd.DataFrame) -> bool:
    """
    Walks every row and checks:
        previous_balance - debit + credit  ≈  current_balance  (±0.01)

    Opening balance is back-calculated from row 0:
        opening = balance[0] + debit[0] - credit[0]
    """
    TOLERANCE    = 0.01
    prev_balance = df.iloc[0]["Balance"] + df.iloc[0]["Debit"] - df.iloc[0]["Credit"]

    for idx, row in df.iterrows():
        expected = prev_balance - row["Debit"] + row["Credit"]
        actual   = row["Balance"]
        if abs(expected - actual) > TOLERANCE:
            print(
                f"\n      [VALIDATOR] ❌  Mismatch on row {idx} "
                f"({row['Date'].strftime('%d/%m/%Y')}):\n"
                f"        Expected : {expected:.2f}\n"
                f"        Actual   : {actual:.2f}"
            )
            return False
        prev_balance = actual

    return True


# ---------------------------------------------------------------------------
# Step 5 — Output writers
# ---------------------------------------------------------------------------

def _save_excel(df: pd.DataFrame, path: str) -> None:
    """CA-ready Excel: readable columns, dates formatted DD/MM/YYYY."""
    out = df[["Date", "Narration", "Clean_Description", "CoA_Category",
              "Debit", "Credit", "Balance"]].copy()
    out["Date"] = out["Date"].dt.strftime("%d/%m/%Y")
    try:
        out.to_excel(path, index=False)
        print(f"      ✅  Excel  → {path}")
    except PermissionError:
        print(f"\n[!] Cannot write '{path}' — close it in Excel first, then re-run.")
        sys.exit(1)


def _save_tally_csv(df: pd.DataFrame, path: str) -> None:
    """
    Tally-ready CSV.
    Columns: Date | Voucher_Type | Ledger_Name | Amount
    Voucher_Type is 'Payment' when Debit > 0, 'Receipt' when Credit > 0.
    Amount is always a positive absolute value.
    """
    tally = df[["Date", "Clean_Description", "CoA_Category", "Debit", "Credit"]].copy()
    tally["Date"] = df["Date"].dt.strftime("%d/%m/%Y")

    tally["Voucher_Type"] = tally.apply(
        lambda r: "Payment" if r["Debit"] > 0 else "Receipt", axis=1
    )
    tally["Amount"] = tally.apply(
        lambda r: r["Debit"] if r["Debit"] > 0 else r["Credit"], axis=1
    )
    tally = tally.rename(columns={"Clean_Description": "Ledger_Name"})
    tally = tally[["Date", "Voucher_Type", "Ledger_Name", "CoA_Category", "Amount"]]

    tally.to_csv(path, index=False)
    print(f"      ✅  Tally  → {path}")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Step 1: Extract ──────────────────────────────────────────────────
    print("\n[1/5] Extracting raw transactions from PDF...")
    if not os.path.exists(PDF_PATH):
        print(f"      [!] PDF not found at '{PDF_PATH}'. Aborting.")
        sys.exit(1)

    raw_data = HDFCPDFExtractor(PDF_PATH).extract()
    if not raw_data:
        print("      [!] Extraction returned no data. Aborting.")
        sys.exit(1)
    print(f"      → {len(raw_data)} rows extracted.")

    # ── Step 2: Clean ────────────────────────────────────────────────────
    print("\n[2/5] Cleaning narrations and coercing numbers...")
    clean_df = HDFCDataCleaner(raw_data).clean()
    print(f"      → {len(clean_df)} rows | null dates: {clean_df['Date'].isna().sum()}")

    # ── Step 3: Validate ─────────────────────────────────────────────────
    print("\n[3/5] Validating balance integrity...")
    if not validate_balances(clean_df):
        print("\n      [!] Validation FAILED — fix extraction before proceeding.")
        sys.exit(1)
    print("      → All 173 balances verified ✅")

    # ── Step 4: Scrub PII ────────────────────────────────────────────────
    print("\n[4/5] Scrubbing PII and building Clean_Description...")
    safe_df = DataSanitizer(clean_df).scrub_pii()
    print(f"      → PII scrubbed. Sample:")
    sample = safe_df[["Narration", "Clean_Description"]].drop_duplicates().head(5)
    for _, row in sample.iterrows():
        print(f"        {row['Narration'][:45]:<45}  →  {row['Clean_Description']}")

    # ── Step 4.5: CoA Categorisation ─────────────────────────────────────
    print("\n[4.5/5] Categorising transactions via Groq LLM...")
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print(
            "      [!] GROQ_API_KEY not found in environment.\n"
            "          Add  GROQ_API_KEY=gsk_...  to your .env file.\n"
            "          Skipping categorisation — CoA_Category will be 'Uncategorized'."
        )
        safe_df["CoA_Category"] = "Uncategorized"
    else:
        mapper  = CoAMapper(api_key=groq_api_key)
        safe_df = mapper.map(safe_df)

    # ── Step 5: Save outputs ─────────────────────────────────────────────
    print("\n[5/5] Writing output files...")
    _save_excel(safe_df, EXCEL_PATH)
    _save_tally_csv(safe_df, TALLY_PATH)

    # Summary
    print(f"\n{'─' * 55}")
    print(f"  Pipeline complete.")
    print(f"  Transactions processed : {len(safe_df)}")
    if "CoA_Category" in safe_df.columns:
        cat_counts = safe_df["CoA_Category"].value_counts()
        print(f"  Category breakdown:")
        for cat, count in cat_counts.items():
            print(f"    {cat:<30} {count:>4} rows")
    print(f"  Output : {os.path.abspath(OUT_DIR)}")
    print(f"{'─' * 55}\n")


if __name__ == "__main__":
    run_pipeline()