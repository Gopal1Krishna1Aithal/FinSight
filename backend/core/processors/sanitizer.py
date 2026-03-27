"""
core/processors/sanitizer.py

Scrubs PII and bank-noise from HDFC narrations, producing a Clean_Description
column suitable for LLM categorisation.

WHAT IS AND IS NOT HARDCODED HERE
──────────────────────────────────
Structural handlers (ATW/NWD/EAW, POS, UPI, IMPS, CC, CD, FEE, FUND TRF) are
intentionally in code. These prefixes are fixed by RBI/NPCI standards and are
identical across every HDFC Bank account in India. They will not change.

What changes per-account (and therefore lives in sanitizer_config.json):
  - salary_prefixes      : the employer name prefix on salary credit lines
  - boilerplate_phrases  : noise phrases to strip (configurable so you can add
                           new ones without touching code)
  - merchant_aliases     : short tokens to rename/remove (PTM*, AIP*, ONE97, etc.)

To use this sanitizer on a different account, only edit sanitizer_config.json.
"""

import json
import re
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path("mapping") / "sanitizer_config.json"


def _load_config() -> dict:
    """
    Load account-specific config from sanitizer_config.json.
    Falls back to safe defaults if the file is missing, so the sanitizer
    still works (without employer-recognition) rather than crashing.
    """
    defaults = {
        "salary_prefixes": [],
        "boilerplate_phrases": [
            "PAYMENTFROMPHONEPE",
            "PAYMENT FROM PHONEPE",
            "POS DEBIT",
            "POSDEBIT",
            "AUTOPAY SI-TAD",
            "AUTOPAY SI-MAD",
            "AUTOPAYSI-TAD",
            "AUTOPAYSI-MAD",
            "COMMENTS",
            "IMPSTXN",
            "IMPS TXN",
            "ONBEHALFOF",
            "BENEFICIARYVERIFICATION",
            "IMPSTRANSACTION",
        ],
        "merchant_aliases": {"PTM*": "", "AIP*": "", "ONE97": "PAYTM", "TPS*": ""},
    }
    if not _CONFIG_PATH.exists():
        return defaults
    with open(_CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    # Merge: keys present in file override defaults; missing keys use defaults
    return {**defaults, **{k: v for k, v in cfg.items() if not k.startswith("_")}}


# ---------------------------------------------------------------------------
# Compiled structural patterns
# These match HDFC transaction codes defined by RBI/NPCI — they are stable.
# ---------------------------------------------------------------------------

# Card numbers: 6 digits + 1-6 X/* mask + 4 digits
_CARD_NUMBER = re.compile(r"\d{6}[Xx*]{1,6}\d{4}")

# UPI VPA handles: person@bank
_UPI_HANDLE = re.compile(r"[\w.\-]+@[\w.\-]+")

# Pure-digit runs of 7+ chars (ref numbers, account numbers, txn IDs)
_LONG_DIGITS = re.compile(r"\b\d{7,}\b")

# ATM terminal codes: mixed alpha+digit tokens 5-9 chars
# e.g. S1AWDE11  SPCND016  APN2685A  D3619800  DECN1263
_TERMINAL_CODE = re.compile(r"\b(?=[A-Z0-9]*[0-9])(?=[A-Z0-9]*[A-Z])[A-Z0-9]{5,9}\b")

# Whitespace normaliser
_WHITESPACE = re.compile(r"\s+")

# X-string masking (masked account numbers: XXXXXXXXXXX0, XXXXXXX, etc.)
_X_MASK = re.compile(r"X{3,}\d*")


# Boilerplate word boundary pattern — built dynamically from config
def _build_boilerplate_pattern(phrases: list[str]) -> re.Pattern:
    """
    Build a single compiled regex that matches any of the boilerplate phrases.
    Sorted by length descending so longer phrases match before substrings.
    """
    sorted_phrases = sorted(phrases, key=len, reverse=True)
    escaped = [re.escape(p) for p in sorted_phrases]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Structural handlers — one per RBI/NPCI transaction code
# These are stable across all HDFC accounts.
# ---------------------------------------------------------------------------


def _handle_pos(text: str, _cfg: dict) -> str:
    """POS / POSREF / CRV POS — extract merchant name."""
    text = re.sub(r"^(?:CRV\s*)?POS\s*(?:REF)?\s*", "", text, flags=re.IGNORECASE)
    text = _CARD_NUMBER.sub("", text)
    text = re.sub(r"-?\d{2}/\d{2}\s*", "", text)  # date fragments like -04/04
    text = re.sub(
        r"\s*(?:POS\s*)?(?:DE?BIT|S\s*DEBIT|EBIT)$", "", text, flags=re.IGNORECASE
    )
    text = re.sub(r"\s+T$", "", text)  # trailing "T" from split "DEBI T"
    return text.strip(" -_.")


def _handle_atm(text: str, _cfg: dict) -> str:
    """ATW / NWD / EAW — keep location, strip card + terminal code."""
    text = re.sub(r"^(?:ATW|NWD|EAW)-", "", text, flags=re.IGNORECASE)
    text = _CARD_NUMBER.sub("", text)
    text = _TERMINAL_CODE.sub("", text)
    location = text.strip(" -_.")
    return ("ATM WITHDRAWAL " + location).strip()


def _handle_upi(text: str, _cfg: dict) -> str:
    """UPI — extract the payee label from the description segment."""
    text = re.sub(r"^UPI-[\d]+-?", "", text, flags=re.IGNORECASE)
    text = _UPI_HANDLE.sub("", text)
    text = _LONG_DIGITS.sub("", text)
    text = re.sub(r"-?PAYMENT\s*FROM\s*PHONEPE", "", text, flags=re.IGNORECASE)
    text = re.sub(r"-?PAY-[\d]*-?UPI", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[\d\s\-]+", "", text)
    result = text.strip(" -_.")
    return result if result else "UPI TRANSFER"


def _handle_imps(text: str, _cfg: dict) -> str:
    """IMPS — extract beneficiary name after ref number."""
    text = re.sub(r"^IMPS-\d+-?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"-?HDFC-[X\d]+", "", text, flags=re.IGNORECASE)
    text = _X_MASK.sub("", text)
    text = re.sub(r"-?\d+-?COMMENTS", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"IMPSTXN|IMPSTRANSACTION\w*|ONBEHALFOF\w*|BENEFICIARYVERIFICATION\w*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"MER[A-Z]+", "", text)  # MERSIWANALAMM artefact
    text = _LONG_DIGITS.sub("", text)
    result = text.strip(" -_.")
    return result if result else "IMPS TRANSFER"


def _handle_cc(text: str, _cfg: dict) -> str:
    """CC — credit card autopay."""
    text = re.sub(r"^CC\s*", "", text, flags=re.IGNORECASE)
    text = _CARD_NUMBER.sub("", text)
    text = re.sub(r"^0+", "", text)  # leading zeros left after card removal
    text = re.sub(r"AUTOPAY\s*SI-(?:TAD|MAD)", "AUTOPAY", text, flags=re.IGNORECASE)
    return ("CREDIT CARD " + text.strip(" -_.")).strip()


def _handle_fund(text: str, _cfg: dict) -> str:
    """FUND TRF — internal fund transfer."""
    text = re.sub(r"^FUND\s*TRF\s*DM?-?", "", text, flags=re.IGNORECASE)
    text = _CARD_NUMBER.sub("", text)
    return ("FUND TRANSFER " + text.strip(" -_.")).strip()


def _handle_fee(text: str, _cfg: dict) -> str:
    """FEE — ATM or service charge."""
    text = re.sub(r"^FEE-", "", text, flags=re.IGNORECASE)
    text = re.sub(r"AOR\w+", "", text, flags=re.IGNORECASE)  # AOR ref codes
    text = _LONG_DIGITS.sub("", text)
    text = re.sub(r"\(1TXN\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\d{2}/\d{2}/\d{2}", "", text)  # embedded date
    return ("BANK FEE " + text.strip(" -_.()")).strip()


def _handle_cd(text: str, _cfg: dict) -> str:
    """CD — cash deposit."""
    text = re.sub(r"^CD-", "", text, flags=re.IGNORECASE)
    text = _LONG_DIGITS.sub("", text)
    return ("CASH DEPOSIT " + text.strip(" -_.")).strip()


def _handle_salary(text: str, cfg: dict) -> str:
    """
    Employer salary credit.
    The employer prefix is loaded from config — not hardcoded here.
    Detects ADVANCE vs regular salary from the content after the prefix.
    """
    # Strip the employer prefix (any of the configured ones)
    for prefix in cfg.get("salary_prefixes", []):
        text = re.sub(rf"^{re.escape(prefix)}-?", "", text, flags=re.IGNORECASE)

    # Detect advance vs regular salary
    if re.search(r"ADVANCE", text, re.IGNORECASE):
        return "SALARY ADVANCE"

    # Strip the employee name/code — anything after SAL prefix is payroll metadata
    text = re.sub(r"^SAL\w*", "", text, flags=re.IGNORECASE)

    return (
        ("SALARY " + text.strip(" -_.")).strip()
        if text.strip(" -_.")
        else "SALARY CREDIT"
    )


def _handle_default(text: str, cfg: dict) -> str:
    """
    Fallback for narrations that don't match any structural prefix.
    Strips card numbers, long digits, X-masks, and UPI handles.
    Also applies the boilerplate phrases from config.
    """
    text = _CARD_NUMBER.sub("", text)
    text = _UPI_HANDLE.sub("", text)
    text = _LONG_DIGITS.sub("", text)
    text = _X_MASK.sub("", text)
    # Strip configured boilerplate
    boilerplate_pat = _build_boilerplate_pattern(cfg.get("boilerplate_phrases", []))
    text = boilerplate_pat.sub("", text)
    return text.strip(" -_.")


# ---------------------------------------------------------------------------
# Dispatch table — structural prefixes only, stable across all HDFC accounts
# ---------------------------------------------------------------------------
#
# The salary handler is injected at runtime from config, not listed here.
# This allows the pattern to be built from the configured employer prefixes.

_STRUCTURAL_DISPATCH = [
    (re.compile(r"^(?:CRV\s*)?POS", re.IGNORECASE), _handle_pos),
    (re.compile(r"^(?:ATW|NWD|EAW)-", re.IGNORECASE), _handle_atm),
    (re.compile(r"^UPI-", re.IGNORECASE), _handle_upi),
    (re.compile(r"^IMPS-", re.IGNORECASE), _handle_imps),
    (re.compile(r"^CC\s*\d", re.IGNORECASE), _handle_cc),
    (re.compile(r"^FUND\s*TRF", re.IGNORECASE), _handle_fund),
    (re.compile(r"^FEE-", re.IGNORECASE), _handle_fee),
    (re.compile(r"^CD-", re.IGNORECASE), _handle_cd),
]


def _build_dispatch(cfg: dict) -> list:
    """
    Build the full dispatch table by appending config-driven salary patterns
    to the structural table.

    Salary patterns are built from cfg['salary_prefixes'] so they work for
    any employer, not just UKARHEALTHCAR.
    """
    dispatch = list(_STRUCTURAL_DISPATCH)
    for prefix in cfg.get("salary_prefixes", []):
        pattern = re.compile(rf"^{re.escape(prefix)}-", re.IGNORECASE)
        dispatch.append((pattern, _handle_salary))
    return dispatch


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class DataSanitizer:
    """
    Scrubs PII and bank-noise from HDFC narrations.

    On init, loads mapping/sanitizer_config.json for account-specific settings.
    If the config file is missing, falls back to safe defaults (structural
    cleaning still works; employer salary recognition is disabled).

    Input  : DataFrame with a 'Narration' column (already cleaned by HDFCDataCleaner)
    Output : Same DataFrame plus a 'Clean_Description' column

    'Narration'         → preserved verbatim for audit trails
    'Clean_Description' → what gets sent to the LLM / shown in reports
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.cfg = _load_config()
        self.dispatch = _build_dispatch(self.cfg)
        self._boilerplate = _build_boilerplate_pattern(
            self.cfg.get("boilerplate_phrases", [])
        )
        # Build merchant alias substitutions from config
        self._aliases = self.cfg.get("merchant_aliases", {})

    def scrub_pii(self) -> pd.DataFrame:
        self.df["Clean_Description"] = self.df["Narration"].apply(self._clean)
        return self.df

    def _clean(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""

        # Apply merchant aliases first (e.g. PTM* -> '', ONE97COMMUNICAT -> PAYTM)
        # Plain string replacement, case-insensitive — alias keys from config are
        # literal strings, not regex patterns. re.escape breaks keys with '*' etc.
        text_upper = text.upper()
        for alias, replacement in self._aliases.items():
            alias_upper = alias.upper()
            if alias_upper in text_upper:
                idx = text_upper.index(alias_upper)
                text = text[:idx] + replacement + text[idx + len(alias) :]
                text_upper = text.upper()

        # Dispatch to structural handler
        for pattern, handler in self.dispatch:
            if pattern.match(text):
                result = handler(text, self.cfg)
                break
        else:
            result = _handle_default(text, self.cfg)

        # Final normalisation: collapse punctuation runs and whitespace
        result = re.sub(r"[.\-_/]+", " ", result)
        result = _WHITESPACE.sub(" ", result).strip()
        return result
