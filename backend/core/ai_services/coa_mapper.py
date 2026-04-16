"""
core/ai_services/coa_mapper.py

Maps sanitized transaction descriptions to Chart of Accounts categories
using the Groq LLM API, with confidence scoring and reasoning for every result.

Cache schema (mapping/cache.json):
    {
      "MASIHAUTOMOBILEPO": {
        "category":   "Fuel & Auto",
        "confidence": 82,
        "reasoning":  "MASIH AUTOMOBILE — vehicle parts/service shop"
      },
      ...
    }

DataFrame columns added by .map():
    CoA_Category      str    — accounting category name
    Confidence_Score  int    — 0-100, model self-reported certainty
    Reasoning         str    — one-sentence explanation from the model
"""

import json
import re
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CATEGORIES_FILE = Path("mapping") / "categories.json"
CACHE_FILE = Path("mapping") / "cache.json"
MODEL = "llama-3.1-8b-instant"
BATCH_SIZE = 20  # descriptions per API call
RETRY_LIMIT = 2  # retries per failed/incomplete batch
RETRY_DELAY = 3  # seconds between retries
CONFIDENCE_THRESHOLD = 70  # below this → Review_Required = True
MAX_TOKENS = 2048  # nested JSON is ~3x larger than flat — must be higher


# ---------------------------------------------------------------------------
# Tier-1 Deterministic Taxonomy (SaaS Efficiency Engine)
# ---------------------------------------------------------------------------

_DETERMINISTIC_TAXONOMY = {
    r"ATM\s*WITHDRAWAL|NWD-|EAW-|ATW-": "ATM Withdrawal",
    r"CASH\s*DEPOSIT|CD-": "Cash Deposit",
    r"FUEL|HPCL|HP\s*CENTRE|HP\s*GAS|IOCL|PETROL|MOTORS|BPCL|SHELL": "Fuel & Auto",
    r"AIRTEL|JIO|IDEA|BSNL|BROADBAND|VODAFONE|ACTFI": "Utilities & Telecom",
    r"AMAZON|AMZN|FLIPKART|FKRT|MEESHO|RETAIL|JIOMART|BLINKIT|ZEPTO": "E-Commerce & Retail",
    r"UBER|OLA\s*CABS|IRCTC|TRAVEL|INDIGO|AIR\s*INDIA|VISTARA|MAKEMYTRIP|MMT": "Travel & Transport",
    r"SALARY|PAYROLL|PAY\s*ROLL|SAL-": "Payroll",
    r"RECHARGE|MOB\s*REC": "Utilities & Telecom",
    r"ZOMATO|SWIGGY|FOOD|RESTAURANT|CAFE|EATERY": "E-Commerce & Retail",
    r"HEALTHCARE|PHARMACY|MEDIC|HOSPITAL|1MG|APOLLO": "Healthcare & Medical",
    r"CHG|FEES|SERVICE\s*CHG|FINE|GST-|TAX|INT-": "Bank Charges & Fees",
    r"CC\s*AUTOPAY|SI-TAD|SI-MAD|CREDIT\s*CARD": "Credit Card Repayment",
    r"INTEREST|INT-": "Interest & Dividends",
    r"IMPS-|NEFT-|RTGS-|TRANSFER": "IMPS Transfer",
}

def _match_taxonomy(description: str) -> dict | None:
    """
    Check if the description matches a known high-precision pattern.
    Returns a Mapping Entry dict if found, else None.
    """
    import re
    desc_upper = description.upper()
    for pattern, cat in _DETERMINISTIC_TAXONOMY.items():
        if re.search(pattern, desc_upper):
            return {
                "category": cat,
                "confidence": 100,
                "reasoning": f"Deterministic match: Pattern '{pattern}' matched."
            }
    return None


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _load_categories() -> list[dict]:
    if not CATEGORIES_FILE.exists():
        raise FileNotFoundError(
            f"Category definitions not found at '{CATEGORIES_FILE}'.\n"
            "Create mapping/categories.json with a 'categories' list before running."
        )
    with open(CATEGORIES_FILE, "r") as f:
        data = json.load(f)
    categories = data.get("categories", [])
    if not categories:
        raise ValueError("'categories' list in categories.json is empty.")
    return categories


def _load_cache() -> dict:
    """
    Load cache and migrate any legacy flat entries.

    Legacy format (old):  {"desc": "Category Name"}
    Current format (new): {"desc": {"category": "...", "confidence": 90, "reasoning": "..."}}

    Any flat string entry is migrated to the new format with confidence=100
    (we trust the human who originally set it) and a migration note.
    """
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, "r") as f:
        raw = json.load(f)

    migrated = {}
    needs_save = False
    for key, val in raw.items():
        if isinstance(val, str):
            # Legacy flat entry — migrate silently
            migrated[key] = {
                "category": val,
                "confidence": 100,
                "reasoning": "Migrated from legacy flat cache.",
            }
            needs_save = True
        else:
            migrated[key] = val

    if needs_save:
        _save_cache(migrated)
        print("      [Cache] Migrated legacy flat entries to new nested format.")

    return migrated


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


def _build_category_block(categories: list[dict]) -> str:
    return "\n".join(
        f"{i}. {c['name']} — {c['description']}" for i, c in enumerate(categories, 1)
    )


def _build_prompt(
    descriptions: list[str],
    category_block: str,
    categories: list[dict],
) -> str:
    """
    Build the classification prompt for one batch.

    Output format requested per description:
        {
          "DESCRIPTION_KEY": {
            "category":   "<exact category name>",
            "confidence": <integer 0-100>,
            "reasoning":  "<one sentence>"
          }
        }

    Confidence guidance given explicitly so the model doesn't always return 95:
      - 90-100: unambiguous match (e.g., "ATM WITHDRAWAL", "SALARY", "CREDIT CARD AUTOPAY")
      - 70-89:  probable match with minor ambiguity
      - 50-69:  uncertain — could fit multiple categories
      - 0-49:   very unclear, essentially guessing
    """
    valid_names_str = ", ".join(f'"{c["name"]}"' for c in categories)
    desc_json = json.dumps(descriptions, indent=2, ensure_ascii=False)

    return f"""You are a financial data classification engine for an Indian business bank account.

CONTEXT:
- Descriptions are extracted from HDFC Bank PDF statements. PII has been removed.
- Many are run-together words due to PDF extraction artifacts.
  Read them phonetically: "MASIHAUTOMOBILEPO" = "MASIH AUTOMOBILE" (auto parts shop).
  "HPCENTREMOTINPO" = "HP CENTRE MOTIN" (HP petrol pump).
  "DEEPAKMOTORSPOSD" = "DEEPAK MOTORS" (vehicle servicing).
  "UKARHEALTHCAREPO" = "UKAR HEALTHCARE" (medical supplier — the account holder's business).
- SALARY entries are payroll credits from the owner's own company, not third-party income.
- ATM WITHDRAWAL, CASH DEPOSIT, FUND TRANSFER, CREDIT CARD AUTOPAY are self-explanatory.

VALID CATEGORY NAMES (copy values exactly from this list):
{valid_names_str}

CATEGORY DEFINITIONS:
{category_block}

CONFIDENCE SCORING GUIDE:
- 90-100: Unambiguous. The description maps to exactly one category with no doubt.
- 70-89:  Probable. Strong match but slight ambiguity exists.
- 50-69:  Uncertain. Could reasonably fit 2+ categories.
- 0-49:   Very unclear. The description is too garbled or generic to classify.

STRICT OUTPUT FORMAT:
Return a single JSON object. For EVERY description in the input list, include an entry:
{{
  "<description_key_copied_exactly>": {{
    "category":   "<one of the valid category names, copied exactly>",
    "confidence": <integer between 0 and 100>,
    "reasoning":  "<one concise sentence explaining why>"
  }}
}}

Rules:
1. Every key must match an input description character-for-character.
2. category must be one of the valid names above, copied exactly.
3. confidence must be an integer, not a string, not a float.
4. reasoning must be a single sentence under 20 words.
5. If truly unknown, set category to "Uncategorized" with low confidence.
6. No extra keys, no markdown, no explanation outside the JSON.

INPUT DESCRIPTIONS:
{desc_json}

Return ONLY the JSON object:"""


# ---------------------------------------------------------------------------
# Response validation helpers
# ---------------------------------------------------------------------------

_FALLBACK_ENTRY = lambda desc: {  # noqa: E731
    "category": "Uncategorized",
    "confidence": 0,
    "reasoning": "Could not be classified after all retries.",
}


def _validate_entry(key: str, entry, valid_names: set) -> dict:
    """
    Normalise one entry from the LLM response.
    Returns a guaranteed-safe dict with category/confidence/reasoning.
    """
    if not isinstance(entry, dict):
        return _FALLBACK_ENTRY(key)

    category = entry.get("category", "Uncategorized")
    confidence = entry.get("confidence", 0)
    reasoning = entry.get("reasoning", "")

    # Category must be a known name
    if category not in valid_names:
        print(
            f"        [Groq] Unknown category '{category}' for '{key}' → Uncategorized"
        )
        category = "Uncategorized"
        confidence = 0

    # Confidence must be an integer 0-100
    try:
        confidence = max(0, min(100, int(confidence)))
    except (TypeError, ValueError):
        confidence = 0

    # Reasoning must be a non-empty string
    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = "No reasoning provided."

    return {
        "category": category,
        "confidence": confidence,
        "reasoning": reasoning.strip(),
    }


# ---------------------------------------------------------------------------
# Groq API call with retry
# ---------------------------------------------------------------------------


def _call_groq(
    client: "Groq",
    descriptions: list[str],
    category_block: str,
    categories: list[dict],
) -> dict:
    """
    Call Groq for one batch. Returns {description: {category, confidence, reasoning}}.
    Retries up to RETRY_LIMIT times on failure or incomplete response.
    """
    valid_names = {c["name"] for c in categories}
    remaining = list(descriptions)
    accumulated: dict = {}

    for attempt in range(1, RETRY_LIMIT + 2):
        prompt = _build_prompt(remaining, category_block, categories)

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=MAX_TOKENS,
            )

            raw = response.choices[0].message.content.strip()
            raw = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE
            ).strip()

            parsed: dict = json.loads(raw)

            # Validate and normalise every returned entry
            for key, entry in parsed.items():
                accumulated[key] = _validate_entry(key, entry, valid_names)

            # Check which input descriptions are still missing
            remaining = [d for d in descriptions if d not in accumulated]

            if not remaining:
                return accumulated

            print(
                f"        [Groq] Attempt {attempt}: {len(remaining)} keys missing. "
                f"{'Retrying...' if attempt <= RETRY_LIMIT else 'Giving up.'}"
            )
            if attempt <= RETRY_LIMIT:
                time.sleep(RETRY_DELAY)
            else:
                for d in remaining:
                    accumulated[d] = _FALLBACK_ENTRY(d)
                return accumulated

        except json.JSONDecodeError as e:
            print(f"        [Groq] Attempt {attempt}: JSON parse error — {e}")
            if attempt > RETRY_LIMIT:
                for d in remaining:
                    accumulated[d] = _FALLBACK_ENTRY(d)
                return accumulated
            time.sleep(RETRY_DELAY)

        except Exception as e:
            print(f"        [Groq] Attempt {attempt}: API error — {e}")
            if attempt > RETRY_LIMIT:
                for d in remaining:
                    accumulated[d] = _FALLBACK_ENTRY(d)
                return accumulated
            time.sleep(RETRY_DELAY)

    for d in remaining:
        accumulated[d] = _FALLBACK_ENTRY(d)
    return accumulated


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class CoAMapper:
    """
    Categorises transactions in a sanitized DataFrame using Groq LLM.

    Adds three columns to the DataFrame:
        CoA_Category      — accounting category name
        Confidence_Score  — integer 0-100
        Reasoning         — one-sentence explanation

    The Review_Required flag is computed in main.py/_save_excel(),
    not here — it is a presentation concern, not a data concern.

    Usage:
        mapper = CoAMapper(api_key=os.getenv("GROQ_API_KEY"))
        df = mapper.map(safe_df)
    """

    def __init__(self, api_key: str):
        from groq import Groq
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file:\n"
                "  GROQ_API_KEY=gsk_..."
            )
        self.client = Groq(api_key=api_key)
        self.categories = _load_categories()
        self.category_block = _build_category_block(self.categories)
        self.cache = _load_cache()

    def map(self, df: pd.DataFrame if "pd" in globals() else object) -> object:
        import pandas as pd
        df = df.copy()

        # ── Startup-Tier Hybrid Optimization: Deterministic First ───────
        all_unique = df["Clean_Description"].unique().tolist()
        for desc in all_unique:
            if desc not in self.cache:
                tax_match = _match_taxonomy(desc)
                if tax_match:
                    self.cache[desc] = tax_match
        _save_cache(self.cache)

        # ── 1. Split cached vs uncached (LLM is only for unknown narrations)
        uncached = [d for d in all_unique if d not in self.cache]
        cached_count = len(all_unique) - len(uncached)

        print(f"      Unique descriptions  : {len(all_unique)}")
        print(f"      Cache hits           : {cached_count}")
        print(f"      Sending to Groq      : {len(uncached)}")

        # ── 2. Batch → Groq → cache ────────────────────────────────────
        if uncached:
            batches = [
                uncached[i : i + BATCH_SIZE]
                for i in range(0, len(uncached), BATCH_SIZE)
            ]
            print(f"      Batches              : {len(batches)} × ≤{BATCH_SIZE}")

            for idx, batch in enumerate(batches, 1):
                print(f"      → Batch {idx}/{len(batches)}: {len(batch)} descriptions")
                result = _call_groq(
                    self.client, batch, self.category_block, self.categories
                )
                self.cache.update(result)
                _save_cache(self.cache)
                print(f"        Saved. Cache now has {len(self.cache)} entries.")

        # ── 3. Expand cache entries into three DataFrame columns ───────
        def _get_field(desc: str, field: str, default):
            entry = self.cache.get(desc)
            if isinstance(entry, dict):
                return entry.get(field, default)
            return default

        df["CoA_Category"] = df["Clean_Description"].apply(
            lambda d: _get_field(d, "category", "Uncategorized")
        )
        df["Confidence_Score"] = df["Clean_Description"].apply(
            lambda d: _get_field(d, "confidence", 0)
        )
        df["Reasoning"] = df["Clean_Description"].apply(
            lambda d: _get_field(d, "reasoning", "Not classified.")
        )

        # ── 4. Report low-confidence and uncategorized rows ───────────
        needs_review = df[
            (df["Confidence_Score"] < CONFIDENCE_THRESHOLD)
            | (df["CoA_Category"] == "Uncategorized")
        ]
        if len(needs_review):
            print(f"\n      ⚠  {len(needs_review)} rows will be flagged for review:")
            for _, r in (
                needs_review[["Clean_Description", "CoA_Category", "Confidence_Score"]]
                .drop_duplicates()
                .iterrows()
            ):
                print(
                    f"         [{r['Confidence_Score']:>3}%] {r['CoA_Category']:<25} ← {r['Clean_Description']}"
                )

        return df
