"""
core/extractors/universal_pdf.py

Universal bank statement extractor using the Google Gemini native PDF API.

Unlike HDFCPDFExtractor (which uses hardcoded x-coordinate column boundaries
specific to HDFC's PDF layout), this extractor passes the PDF directly to
Gemini and asks it to intelligently locate the transaction table, infer column
positions, merge multi-line narrations, and return structured JSON.

Works for:  HDFC, SBI, Axis, ICICI, Kotak, Yes Bank, IndusInd, any Indian bank
            — or any PDF that contains a tabular bank statement.

Output format is IDENTICAL to HDFCPDFExtractor so all downstream steps
(HDFCDataCleaner, DataSanitizer, CoAMapper, etc.) work without modification.

Each returned dict has keys:
    Date        — "DD/MM/YY" or "DD/MM/YYYY" string
    Narration   — full merged narration (continuation lines already merged in)
    Ref_No      — reference/cheque number or ""
    Value_Date  — value date string or ""
    Debit       — amount string without commas (e.g. "1234.56") or ""
    Credit      — amount string without commas or ""
    Balance     — running balance without commas or ""
"""

import json
import os
import re
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Gemini client — lazy import so the rest of the codebase doesn't break if
# google-genai is not installed (HDFC path still works without it).
# ---------------------------------------------------------------------------


def _get_client(api_key: str):
    try:
        from google import genai  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "google-genai package is required for UniversalPDFExtractor.\n"
            "Install it with:  pip install google-genai"
        ) from exc
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM_PROMPT = """You are a financial data extraction engine specialised in Indian bank statements.

Your task:
1. Find the transaction table in this bank statement PDF (it usually has columns like Date, Description/Narration, Debit/Withdrawal, Credit/Deposit, and Balance).
2. Extract EVERY transaction row across ALL pages.
3. IMPORTANT — Multi-line narrations: Some transactions span multiple PDF lines where the second/third lines contain only more narration text but no date or amount. Merge those continuation lines into the single preceding transaction's Narration field separated by a space.
4. Return a valid JSON array with no other text.

Return ONLY a JSON array of objects. Each object must have exactly these keys:
  "Date"       — transaction date exactly as printed (e.g. "01/04/23" or "01/04/2023")
  "Narration"  — full transaction description with continuation lines merged
  "Ref_No"     — cheque number, reference number, or empty string ""
  "Value_Date" — value date as printed, or empty string ""
  "Debit"      — withdrawal/debit amount as a plain number string without commas (e.g. "1234.56"), or "" if none
  "Credit"     — deposit/credit amount as a plain number string without commas, or "" if none
  "Balance"    — running balance as a plain number string without commas (e.g. "98765.43")

Rules:
- Remove thousand-separator commas from all number strings (e.g. "1,23,456.78" → "1234.56"). NEVER remove decimal points.
- If a column is blank in the statement, set it to "".
- Do NOT include page headers, account summary rows, opening/closing balance summary lines, or footers.
- Do NOT emit markdown, code fences, or any text outside the JSON array.
- Include EVERY transaction row, even if there are hundreds.
"""

_EXTRACTION_USER_PROMPT = (
    "Extract all transaction rows from this bank statement PDF exactly as instructed. "
    "Return ONLY the JSON array."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Matches the JSON array we're looking for even if Gemini wraps it in markdown
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _parse_response(raw: str) -> list[dict]:
    """
    Extract the JSON array from Gemini's raw response text.
    Strips markdown code fences if present.
    """
    raw = raw.strip()
    # Strip ```json ... ``` fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)

    match = _JSON_ARRAY_RE.search(raw)
    if not match:
        raise ValueError(
            f"No JSON array found in Gemini response. "
            f"Response start: {raw[:200]}"
        )
    return json.loads(match.group(0))


def _normalise_row(row: dict) -> dict:
    """
    Normalise a single row dict returned by Gemini.
    - Ensure all seven expected keys exist (default to "")
    - Strip any residual commas from number fields
    - Convert all values to strings
    """
    required_keys = ["Date", "Narration", "Ref_No", "Value_Date", "Debit", "Credit", "Balance"]
    out = {}
    for key in required_keys:
        val = str(row.get(key, "") or "").strip()
        # Remove thousand-separator commas from numeric fields
        if key in ("Debit", "Credit", "Balance"):
            val = val.replace(",", "")
        out[key] = val
    return out


# ---------------------------------------------------------------------------
# File upload helper (handles PDFs > direct content limit)
# ---------------------------------------------------------------------------


def _upload_pdf(client, pdf_path: str):
    """Upload a PDF via Gemini Files API and return the file object."""
    from google.genai import types as genai_types  # type: ignore

    print(f"      [Universal] Uploading '{os.path.basename(pdf_path)}' to Gemini Files API...")
    with open(pdf_path, "rb") as f:
        file_obj = client.files.upload(
            file=f,
            config=genai_types.UploadFileConfig(mime_type="application/pdf"),
        )

    # Poll until processing is complete
    max_wait = 120  # seconds
    elapsed = 0
    while elapsed < max_wait:
        file_obj = client.files.get(name=file_obj.name)
        state = str(getattr(file_obj, "state", "")).upper()
        if "ACTIVE" in state or "PROCESSED" in state:
            break
        if "FAILED" in state:
            raise RuntimeError(
                f"Gemini file processing failed for '{pdf_path}'. State: {state}"
            )
        time.sleep(3)
        elapsed += 3

    print(f"      [Universal] File ready: {file_obj.name}")
    return file_obj


def _delete_file_safe(client, file_obj) -> None:
    """Best-effort delete of the uploaded file from Gemini Files API."""
    try:
        client.files.delete(name=file_obj.name)
    except Exception:
        pass  # Non-fatal


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------


class UniversalPDFExtractor:
    """
    Extracts transaction data from ANY bank statement PDF using Gemini's
    native multi-modal PDF understanding.

    Drop-in replacement for HDFCPDFExtractor — returns the same list[dict].

    Usage:
        extractor = UniversalPDFExtractor("/path/to/statement.pdf")
        rows = extractor.extract()  # list[dict] or None on failure
    """

    MODEL = "gemini-2.5-flash"
    RETRY_LIMIT = 2
    RETRY_DELAY = 5  # seconds

    def __init__(self, pdf_path: str, api_key: str | None = None):
        self.pdf_path = pdf_path
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Add it to your .env file:\n"
                "  GEMINI_API_KEY=AIza..."
            )
        self.client = _get_client(self.api_key)

    def extract(self) -> list[dict] | None:
        """
        Extract all transaction rows from the PDF.

        Returns:
            list[dict] — normalised rows with keys matching HDFCPDFExtractor
            None       — on unrecoverable failure (caller should fall back)
        """
        print(f"      [Universal] Extracting '{os.path.basename(self.pdf_path)}'...")

        file_obj = None
        try:
            file_obj = _upload_pdf(self.client, self.pdf_path)
            rows = self._extract_with_retry(file_obj)
        except Exception as exc:
            print(f"      [Universal] ❌ Extraction failed: {exc}")
            return None
        finally:
            if file_obj is not None:
                _delete_file_safe(self.client, file_obj)

        if not rows:
            print("      [Universal] ⚠  No rows returned by Gemini.")
            return None

        normalised = [_normalise_row(r) for r in rows]
        print(f"      [Universal] ✅ {len(normalised)} raw rows extracted.")
        return normalised

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _extract_with_retry(self, file_obj) -> list[dict]:
        """
        Call Gemini with retry on JSON parse failure.
        On each attempt re-uses the same uploaded file object.
        """
        from google.genai import types as genai_types  # type: ignore

        last_error = None

        for attempt in range(1, self.RETRY_LIMIT + 2):
            try:
                print(
                    f"      [Universal] Calling Gemini (attempt {attempt}/{self.RETRY_LIMIT + 1})..."
                )
                response = self.client.models.generate_content(
                    model=self.MODEL,
                    contents=[
                        genai_types.Part.from_uri(
                            file_uri=file_obj.uri,
                            mime_type="application/pdf",
                        ),
                        _EXTRACTION_USER_PROMPT,
                    ],
                    config=genai_types.GenerateContentConfig(
                        system_instruction=_EXTRACTION_SYSTEM_PROMPT,
                        temperature=0.0,
                    ),
                )

                raw_text = response.text.strip()
                rows = _parse_response(raw_text)

                if not isinstance(rows, list):
                    raise ValueError(
                        f"Expected a JSON array, got {type(rows).__name__}"
                    )

                return rows

            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                print(
                    f"      [Universal] Attempt {attempt}: parse error — {exc}. "
                    f"{'Retrying...' if attempt <= self.RETRY_LIMIT else 'Giving up.'}"
                )
                if attempt <= self.RETRY_LIMIT:
                    time.sleep(self.RETRY_DELAY)

            except Exception as exc:
                last_error = exc
                print(
                    f"      [Universal] Attempt {attempt}: API error — {exc}. "
                    f"{'Retrying...' if attempt <= self.RETRY_LIMIT else 'Giving up.'}"
                )
                if attempt <= self.RETRY_LIMIT:
                    time.sleep(self.RETRY_DELAY)

        raise RuntimeError(
            f"All {self.RETRY_LIMIT + 1} attempts failed. Last error: {last_error}"
        )
