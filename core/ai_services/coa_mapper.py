"""
core/ai_services/coa_mapper.py

Maps sanitized transaction descriptions to Chart of Accounts categories
using the Groq LLM API.

Design principles:
  - Zero hardcoding: categories are loaded from mapping/categories.json at runtime.
    Add/rename/remove a category there — no code changes needed here.
  - Unique-only: 173 rows → 57 LLM calls max (not 173).
  - Cache-first: mapping/cache.json prevents re-hitting the API for known descriptions.
    Cache persists across runs and is saved after every batch so progress is never lost.
  - Safe batching: descriptions are chunked into groups of 20 to avoid token overflow.
  - Validated output: every response is checked — missing keys are retried, unknown
    category values are overridden to "Uncategorized".
"""

import json
import re
import time
from pathlib import Path

import pandas as pd
from groq import Groq


# ---------------------------------------------------------------------------
# Configuration — change these here, never in main.py
# ---------------------------------------------------------------------------

CATEGORIES_FILE = Path("mapping") / "categories.json"
CACHE_FILE      = Path("mapping") / "cache.json"
MODEL           = "llama-3.1-8b-instant"
BATCH_SIZE      = 20     # max descriptions per API call
RETRY_LIMIT     = 2      # number of retries per failed/incomplete batch
RETRY_DELAY     = 3      # seconds between retries


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def _load_categories() -> list[dict]:
    """Load category list from categories.json. Raises if file is missing."""
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
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_category_block(categories: list[dict]) -> str:
    """Render numbered category definitions for the prompt body."""
    return "\n".join(
        f"{i}. {c['name']} — {c['description']}"
        for i, c in enumerate(categories, 1)
    )


def _build_prompt(
    descriptions: list[str],
    category_block: str,
    categories: list[dict],
) -> str:
    """
    Build a structured prompt for one batch.

    Accuracy improvements over a naive prompt:
    1. Explicitly warns the model that descriptions are run-together words
       caused by PDF extraction — the single biggest source of errors.
    2. Provides both a valid-names list (for the model to copy from exactly)
       and full definitions (for the model to reason from).
    3. Requires every input key to appear in the output — enforced by retry logic.
    4. Temperature is set to 0.0 in the API call for determinism.
    """
    valid_names_str = ", ".join(f'"{c["name"]}"' for c in categories)
    desc_json       = json.dumps(descriptions, indent=2, ensure_ascii=False)

    return f"""You are a financial data classification engine for an Indian business bank account.

Your task is to classify bank transaction descriptions into accounting categories.

IMPORTANT CONTEXT:
- These descriptions are extracted from HDFC Bank statements and have had PII removed.
- Many descriptions are concatenated without spaces due to PDF extraction.
  Example: "MASIHAUTOMOBILEPO" means "MASIH AUTOMOBILE" — a POS debit at an auto shop.
  Example: "HPCENTREMOTINPO" means "HP CENTRE MOTIN" — an HP petrol pump.
  Example: "DEEPAKMOTORSPOSD" means "DEEPAK MOTORS" — a vehicle service shop.
  Read run-together tokens phonetically and use context to determine the business type.
- Indian business context: UKAR HEALTHCARE is the account holder's company.
  Salary credits tagged with SALARY are payroll, not income from a third party.

VALID CATEGORIES — your values must be copied exactly from this list:
{valid_names_str}

CATEGORY DEFINITIONS — use these to decide:
{category_block}

STRICT INSTRUCTIONS:
1. Return a single flat JSON object. No nesting, no arrays, no markdown.
2. Every key must be one of the strings from the INPUT LIST, copied character-for-character.
3. Every value must be one of the valid category names above, copied exactly.
4. If you genuinely cannot determine the category, use "Uncategorized" — do NOT omit the key.
5. Do NOT add commentary, explanation, or any keys not in the input list.

INPUT LIST:
{desc_json}

Return ONLY the JSON object:"""


# ---------------------------------------------------------------------------
# Groq API call with retry
# ---------------------------------------------------------------------------

def _call_groq(
    client: Groq,
    descriptions: list[str],
    category_block: str,
    categories: list[dict],
) -> dict:
    """
    Call Groq for one batch of descriptions.
    Returns {description: category} for every item in descriptions.
    Falls back to "Uncategorized" after RETRY_LIMIT failures.
    """
    valid_names = {c["name"] for c in categories}
    remaining   = list(descriptions)   # may shrink on retry (only re-send missing keys)

    accumulated: dict = {}

    for attempt in range(1, RETRY_LIMIT + 2):
        prompt = _build_prompt(remaining, category_block, categories)
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=1024,
            )

            raw = response.choices[0].message.content.strip()
            # Strip accidental markdown fences (model sometimes wraps anyway)
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

            result: dict = json.loads(raw)

            # Fix values that don't match any known category
            for key in list(result.keys()):
                if result[key] not in valid_names:
                    print(
                        f"        [Groq] Unknown value '{result[key]}' for '{key}' "
                        "— corrected to 'Uncategorized'"
                    )
                    result[key] = "Uncategorized"

            accumulated.update(result)

            # Check which requested keys are still missing from the accumulated result
            remaining = [d for d in descriptions if d not in accumulated]

            if not remaining:
                return accumulated          # all keys accounted for — done

            # Some keys missing — retry with only the missing subset
            print(
                f"        [Groq] Attempt {attempt}: {len(remaining)} keys missing. "
                f"{'Retrying...' if attempt <= RETRY_LIMIT else 'Giving up — marking Uncategorized.'}"
            )
            if attempt <= RETRY_LIMIT:
                time.sleep(RETRY_DELAY)
            else:
                for d in remaining:
                    accumulated[d] = "Uncategorized"
                return accumulated

        except json.JSONDecodeError as e:
            print(f"        [Groq] Attempt {attempt}: JSON parse error — {e}")
            if attempt > RETRY_LIMIT:
                for d in remaining:
                    accumulated[d] = "Uncategorized"
                return accumulated
            time.sleep(RETRY_DELAY)

        except Exception as e:
            print(f"        [Groq] Attempt {attempt}: API error — {e}")
            if attempt > RETRY_LIMIT:
                for d in remaining:
                    accumulated[d] = "Uncategorized"
                return accumulated
            time.sleep(RETRY_DELAY)

    # Should never reach here, but safety net
    for d in remaining:
        accumulated[d] = "Uncategorized"
    return accumulated


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class CoAMapper:
    """
    Categorises transactions in a sanitized DataFrame using Groq LLM.

    Args:
        api_key: Your Groq API key (read from .env in main.py — never hardcoded).

    Usage:
        mapper = CoAMapper(api_key=os.getenv("GROQ_API_KEY"))
        df = mapper.map(safe_df)
        # df now has a 'CoA_Category' column
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file:\n"
                "  GROQ_API_KEY=gsk_..."
            )
        self.client         = Groq(api_key=api_key)
        self.categories     = _load_categories()
        self.category_block = _build_category_block(self.categories)
        self.cache          = _load_cache()

    def map(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main entry point. Returns df with a new 'CoA_Category' column.
        All other columns are unchanged.
        """
        df = df.copy()

        # ── Step 1: Separate cached from uncached ──────────────────────
        all_unique: list[str] = df["Clean_Description"].unique().tolist()
        uncached:   list[str] = [d for d in all_unique if d not in self.cache]
        cached_count          = len(all_unique) - len(uncached)

        print(f"      Unique descriptions  : {len(all_unique)}")
        print(f"      Cache hits           : {cached_count}")
        print(f"      Sending to Groq      : {len(uncached)}")

        # ── Step 2: Batch → Groq → update cache ───────────────────────
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
                _save_cache(self.cache)   # persist after every batch
                print(f"        Cache saved ({len(self.cache)} total entries).")

        # ── Step 3: Map back to full DataFrame ─────────────────────────
        df["CoA_Category"] = (
            df["Clean_Description"]
            .map(self.cache)
            .fillna("Uncategorized")
        )

        # Report anything that fell through
        uncategorized = df[df["CoA_Category"] == "Uncategorized"]["Clean_Description"].unique()
        if len(uncategorized):
            print(f"\n      ⚠  {len(uncategorized)} descriptions mapped to Uncategorized:")
            for u in uncategorized:
                print(f"         - {repr(u)}")

        return df