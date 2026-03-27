"""
core/extractors/extraction_validator.py

Post-extraction quality validator.

This runs BEFORE HDFCDataCleaner and checks that the raw list[dict] coming
out of any extractor (universal or HDFC) is structurally sound and
contains plausible financial data.

It does NOT fix data — it raises informative warnings so the operator can
decide whether to proceed or abort.

Checks performed:
  1. SCHEMA      — all seven expected keys present in every row
  2. ROW COUNT   — at least 1 usable row
  3. DATE PARSE  — reasonable fraction of rows have a parseable date
  4. NUMBERS     — Debit / Credit / Balance look like numbers where non-empty
  5. BALANCE     — running balance math integrity (same as validate_balances in
                   main.py, but runs on the raw strings before type coercion,
                   so it can gracefully skip rows where Balance is missing)
  6. EMPTY ROWS  — warns about rows with no date AND no amounts (orphaned 
                   continuation rows that the extractor failed to merge)

Usage:
    from core.extractors.extraction_validator import ExtractionValidator

    validator = ExtractionValidator(raw_rows)
    result = validator.validate()
    if not result.passed:
        print(result.report())
        # decide whether to abort or continue
"""

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {"Date", "Narration", "Ref_No", "Value_Date", "Debit", "Credit", "Balance"}

_DATE_PATTERNS = [
    re.compile(r"^\d{2}/\d{2}/\d{2}$"),       # DD/MM/YY
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),       # DD/MM/YYYY
    re.compile(r"^\d{2}-\d{2}-\d{2,4}$"),     # DD-MM-YY or DD-MM-YYYY
    re.compile(r"^\d{2}\s+\w{3}\s+\d{2,4}$"), # DD MMM YYYY  (e.g. "01 Apr 2023")
]


def _is_parseable_date(val: str) -> bool:
    val = val.strip()
    return any(p.match(val) for p in _DATE_PATTERNS)


def _is_number(val: str) -> bool:
    """Return True if val is a non-empty string that looks like a number."""
    val = val.strip().replace(",", "")
    if not val:
        return False
    try:
        float(val)
        return True
    except ValueError:
        return False


def _to_float(val: str) -> float | None:
    val = val.strip().replace(",", "")
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    passed: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Statistics
    total_rows: int = 0
    rows_with_valid_date: int = 0
    rows_with_amounts: int = 0
    orphaned_rows: int = 0
    missing_schema_rows: int = 0
    balance_mismatches: int = 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def report(self) -> str:
        lines = [
            "=" * 60,
            " EXTRACTION VALIDATION REPORT",
            "=" * 60,
            f"  Total rows extracted      : {self.total_rows}",
            f"  Rows with valid date      : {self.rows_with_valid_date}",
            f"  Rows with amounts         : {self.rows_with_amounts}",
            f"  Orphaned / unmerged rows  : {self.orphaned_rows}",
            f"  Schema-incomplete rows    : {self.missing_schema_rows}",
            f"  Balance chain mismatches  : {self.balance_mismatches}",
            "",
        ]
        if self.errors:
            lines.append("  ❌ ERRORS (pipeline should NOT proceed):")
            for e in self.errors:
                lines.append(f"     • {e}")
            lines.append("")
        if self.warnings:
            lines.append("  ⚠  WARNINGS (review recommended):")
            for w in self.warnings:
                lines.append(f"     • {w}")
            lines.append("")
        lines.append(f"  Overall: {'✅ PASSED' if self.passed else '❌ FAILED'}")
        lines.append("=" * 60)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class ExtractionValidator:
    """
    Validates the raw list[dict] output of any extractor.

    Args:
        raw_rows: The list returned by HDFCPDFExtractor.extract() or
                  UniversalPDFExtractor.extract().
        min_rows: Minimum number of rows to consider extraction non-empty.
                  Default 1.
        min_date_ratio: Minimum fraction of rows that must have a parseable
                        date.  Default 0.7 (70%).
        balance_tolerance: Float tolerance for balance chain validation.
                           Default 1.0 (₹1 — generous for OCR/rounding).
    """

    def __init__(
        self,
        raw_rows: list[dict],
        min_rows: int = 1,
        min_date_ratio: float = 0.70,
        balance_tolerance: float = 1.0,
    ):
        self.raw_rows = raw_rows or []
        self.min_rows = min_rows
        self.min_date_ratio = min_date_ratio
        self.balance_tolerance = balance_tolerance

    def validate(self) -> ValidationResult:
        result = ValidationResult()
        result.total_rows = len(self.raw_rows)

        # --- Check 1: Not empty ----------------------------------------------
        if result.total_rows < self.min_rows:
            result.add_error(
                f"Extraction returned {result.total_rows} rows "
                f"(minimum expected: {self.min_rows}). "
                "The PDF may not contain a transaction table, or extraction failed."
            )
            return result  # No point running further checks

        # --- Check 2: Schema completeness ------------------------------------
        for i, row in enumerate(self.raw_rows):
            missing = REQUIRED_KEYS - set(row.keys())
            if missing:
                result.missing_schema_rows += 1
                if result.missing_schema_rows == 1:
                    result.add_warning(
                        f"Row {i} is missing expected keys: {missing}. "
                        "This may cause downstream failures."
                    )

        if result.missing_schema_rows > result.total_rows * 0.1:
            result.add_error(
                f"{result.missing_schema_rows}/{result.total_rows} rows are missing "
                "required schema keys. Extraction quality is too low."
            )

        # --- Check 3: Date parseability --------------------------------------
        for row in self.raw_rows:
            date_val = str(row.get("Date", "")).strip()
            if _is_parseable_date(date_val):
                result.rows_with_valid_date += 1

        date_ratio = result.rows_with_valid_date / result.total_rows
        if date_ratio < self.min_date_ratio:
            result.add_error(
                f"Only {result.rows_with_valid_date}/{result.total_rows} rows "
                f"({date_ratio:.0%}) have a recognisable date format. "
                f"Expected ≥ {self.min_date_ratio:.0%}. "
                "Likely an extraction layout mismatch."
            )

        # --- Check 4: Numeric amounts ----------------------------------------
        bad_amount_count = 0
        for row in self.raw_rows:
            has_any_amount = False
            for col in ("Debit", "Credit", "Balance"):
                val = str(row.get(col, "")).strip()
                if val:  # non-empty → must be a number
                    if _is_number(val):
                        has_any_amount = True
                    else:
                        bad_amount_count += 1
                        result.add_warning(
                            f"Non-numeric value '{val}' in column '{col}': "
                            f"Narration='{str(row.get('Narration',''))[:40]}'"
                        )
            if has_any_amount:
                result.rows_with_amounts += 1

        if bad_amount_count > 5:
            result.add_error(
                f"{bad_amount_count} non-numeric values found in Debit/Credit/Balance "
                "columns. Extraction may be misaligning columns."
            )

        # --- Check 5: Orphaned rows (no date + no amounts) -------------------
        for row in self.raw_rows:
            has_date = _is_parseable_date(str(row.get("Date", "")))
            has_amounts = any(
                _is_number(str(row.get(c, "")))
                for c in ("Debit", "Credit", "Balance")
            )
            if not has_date and not has_amounts:
                result.orphaned_rows += 1

        if result.orphaned_rows > 0:
            result.add_warning(
                f"{result.orphaned_rows} rows have no date AND no amounts. "
                "These may be continuation narration lines that were not merged. "
                "The HDFCDataCleaner will drop them; consider improving the extractor prompt."
            )

        # --- Check 6: Balance chain integrity --------------------------------
        # Only runs on rows that have both a number Balance and a date.
        typed_rows: list[tuple[float, float, float]] = []  # (debit, credit, balance)
        for row in self.raw_rows:
            d = _to_float(str(row.get("Debit", "")))
            c = _to_float(str(row.get("Credit", "")))
            b = _to_float(str(row.get("Balance", "")))
            if b is not None and _is_parseable_date(str(row.get("Date", ""))):
                typed_rows.append((d or 0.0, c or 0.0, b))

        if len(typed_rows) >= 2:
            # Reconstruct opening balance from first row
            prev_bal = typed_rows[0][2] + typed_rows[0][0] - typed_rows[0][1]
            for i, (debit, credit, balance) in enumerate(typed_rows):
                expected = prev_bal - debit + credit
                if abs(expected - balance) > self.balance_tolerance:
                    result.balance_mismatches += 1
                    if result.balance_mismatches <= 3:  # cap noise in warnings
                        result.add_warning(
                            f"Balance mismatch on typed row {i}: "
                            f"expected ₹{expected:,.2f}, got ₹{balance:,.2f} "
                            f"(diff ₹{abs(expected - balance):,.2f})"
                        )
                prev_bal = balance

            if result.balance_mismatches > 0:
                msg = (
                    f"{result.balance_mismatches} balance chain mismatches detected. "
                )
                # More than 5% of rows failing → hard error
                if result.balance_mismatches > len(typed_rows) * 0.05:
                    result.add_error(
                        msg + "Too many mismatches — extraction may have garbled amounts. "
                        "Do NOT import this data."
                    )
                else:
                    result.add_warning(
                        msg + "Minor mismatches may be due to rounding in the original PDF."
                    )
        elif len(typed_rows) < 2:
            result.add_warning(
                "Not enough rows with both a date and a balance to validate the "
                "balance chain. Run a manual spot check."
            )

        return result
