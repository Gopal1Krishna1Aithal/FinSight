import re
import pandas as pd

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Card numbers: 6 digits + 1-6 X/* mask + 4 digits
_CARD_NUMBER = re.compile(r'\d{6}[Xx*]{1,6}\d{4}')

# UPI VPA handles: person@bank
_UPI_HANDLE = re.compile(r'[\w.\-]+@[\w.\-]+')

# Pure-digit runs of 7+ chars (ref numbers, account numbers, txn IDs)
_LONG_DIGITS = re.compile(r'\b\d{7,}\b')

# ATM terminal codes: mixed alpha+digit tokens 5-9 chars
# e.g. S1AWDE11  SPCND016  APN2685A  D3619800  DECN1263
_TERMINAL_CODE = re.compile(r'\b(?=[A-Z0-9]*[0-9])(?=[A-Z0-9]*[A-Z])[A-Z0-9]{5,9}\b')

# Collapse whitespace
_WHITESPACE = re.compile(r'\s+')

# ---------------------------------------------------------------------------
# Per-prefix handlers
# ---------------------------------------------------------------------------

def _handle_pos(text):
    """POS / POSREF / CRV POS — extract merchant name after card number."""
    text = re.sub(r'^(?:CRV\s*)?POS\s*(?:REF)?\s*', '', text, flags=re.IGNORECASE)
    text = _CARD_NUMBER.sub('', text)
    # Remove date fragment like -04/04
    text = re.sub(r'-?\d{2}/\d{2}\s*', '', text)
    # Remove trailing DEBIT variants and split-word artifacts
    text = re.sub(r'\s*(?:POS\s*)?(?:DE?BIT|S\s*DEBIT|EBIT)$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+T$', '', text)          # trailing "T" from "DEBI T"
    text = re.sub(r'\bPTM\*', '', text, flags=re.IGNORECASE)  # Paytm prefix
    text = re.sub(r'\bAIP\*', '', text, flags=re.IGNORECASE)  # Airtel prefix
    return text.strip(' -_.')


def _handle_atm(text):
    """ATW / NWD / EAW — keep location, drop card + terminal code."""
    text = re.sub(r'^(?:ATW|NWD|EAW)-', '', text, flags=re.IGNORECASE)
    text = _CARD_NUMBER.sub('', text)
    text = _TERMINAL_CODE.sub('', text)
    location = text.strip(' -_.')
    return ('ATM WITHDRAWAL ' + location).strip()


def _handle_upi(text):
    """UPI — extract payee name from description after the VPA."""
    # Remove UPI-<digits>- prefix
    text = re.sub(r'^UPI-[\d]+-?', '', text, flags=re.IGNORECASE)
    # Remove UPI VPA handle
    text = _UPI_HANDLE.sub('', text)
    # Remove long digit runs
    text = _LONG_DIGITS.sub('', text)
    # Remove PAYMENT FROM PHONEPE and similar boilerplate
    text = re.sub(r'-?PAYMENT\s*FROM\s*PHONEPE', '', text, flags=re.IGNORECASE)
    text = re.sub(r'-?PAY-[\d]*-?UPI', '', text, flags=re.IGNORECASE)
    # Remove leading digits/dashes left over
    text = re.sub(r'^[\d\s\-]+', '', text)
    result = text.strip(' -_.')
    return result if result else 'UPI TRANSFER'


def _handle_imps(text):
    """IMPS — extract beneficiary name."""
    # Remove IMPS-<txnid>- prefix
    text = re.sub(r'^IMPS-\d+-?', '', text, flags=re.IGNORECASE)
    # Remove -HDFC-XXX... masked account suffix
    text = re.sub(r'-?HDFC-[X\d]+', '', text, flags=re.IGNORECASE)
    # Remove X-strings (masked account numbers like XXXXXXXXXXX0)
    text = re.sub(r'X{3,}\d*', '', text)
    # Remove boilerplate
    text = re.sub(r'-?\d+-?COMMENTS', '', text, flags=re.IGNORECASE)
    text = re.sub(r'IMPSTXN|IMPSTRANSACTION\w*|ONBEHALFOF\w*|BENEFICIARYVERIFICATION\w*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'MER\w+', '', text)   # "MERSIWANALAMM" artefact
    text = _LONG_DIGITS.sub('', text)
    result = text.strip(' -_.')
    return result if result else 'IMPS TRANSFER'


def _handle_cc(text):
    """CC — credit card autopay."""
    text = re.sub(r'^CC\s*', '', text, flags=re.IGNORECASE)
    text = _CARD_NUMBER.sub('', text)
    # Remove leftover leading zeros after card number removal e.g. "000AUTOPAY"
    text = re.sub(r'^0+', '', text)
    text = re.sub(r'AUTOPAY\s*SI-(?:TAD|MAD)', 'AUTOPAY', text, flags=re.IGNORECASE)
    return ('CREDIT CARD ' + text.strip(' -_.')).strip()


def _handle_fund(text):
    """FUND TRF — inter-account fund transfer."""
    text = re.sub(r'^FUND\s*TRF\s*DM?-?', '', text, flags=re.IGNORECASE)
    text = _CARD_NUMBER.sub('', text)
    return ('FUND TRANSFER ' + text.strip(' -_.')).strip()


def _handle_fee(text):
    """FEE — ATM or service charge."""
    text = re.sub(r'^FEE-', '', text, flags=re.IGNORECASE)
    # Remove AOR reference codes
    text = re.sub(r'AOR\w+', '', text, flags=re.IGNORECASE)
    text = _LONG_DIGITS.sub('', text)
    # Simplify: keep ATM CASH / ATM NON CASH label
    text = re.sub(r'\(1TXN\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d{2}/\d{2}/\d{2}', '', text)  # remove embedded date
    return ('BANK FEE ' + text.strip(' -_.()')).strip()


def _handle_cd(text):
    """CD — cash deposit."""
    text = re.sub(r'^CD-', '', text, flags=re.IGNORECASE)
    text = _LONG_DIGITS.sub('', text)
    return ('CASH DEPOSIT ' + text.strip(' -_.')).strip()


def _handle_salary(text):
    """UKAR HEALTHCAR-SAL... — payroll credit."""
    text = re.sub(r'^UKARHEALTHCAR-', '', text, flags=re.IGNORECASE)
    return ('SALARY ' + text.strip(' -_.')).strip()


def _handle_salary_advance(text):
    """UKAR HEALTHCAR-SIZWAN_ADVANCE — salary advance."""
    return 'SALARY ADVANCE'


def _handle_default(text):
    """Fallback: strip card numbers, long digits, UPI handles."""
    text = _CARD_NUMBER.sub('', text)
    text = _UPI_HANDLE.sub('', text)
    text = _LONG_DIGITS.sub('', text)
    return text.strip(' -_.')


# ---------------------------------------------------------------------------
# Dispatch table — first match wins
# ---------------------------------------------------------------------------

_DISPATCH = [
    (re.compile(r'^(?:CRV\s*)?POS',              re.IGNORECASE), _handle_pos),
    (re.compile(r'^(?:ATW|NWD|EAW)-',            re.IGNORECASE), _handle_atm),
    (re.compile(r'^UPI-',                         re.IGNORECASE), _handle_upi),
    (re.compile(r'^IMPS-',                        re.IGNORECASE), _handle_imps),
    (re.compile(r'^CC\s*\d',                      re.IGNORECASE), _handle_cc),
    (re.compile(r'^FUND\s*TRF',                   re.IGNORECASE), _handle_fund),
    (re.compile(r'^FEE-',                         re.IGNORECASE), _handle_fee),
    (re.compile(r'^CD-',                          re.IGNORECASE), _handle_cd),
    (re.compile(r'^UKARHEALTHCAR-SIZWAN_ADVANCE', re.IGNORECASE), _handle_salary_advance),
    (re.compile(r'^UKARHEALTHCAR-SAL',            re.IGNORECASE), _handle_salary),
]


class DataSanitizer:
    """
    Scrubs PII and bank-noise from narrations, producing a 'Clean_Description'
    column suitable for LLM categorisation.

    The original 'Narration' column is preserved untouched for audit purposes.
    Downstream code should use 'Clean_Description' as the LLM input.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def scrub_pii(self) -> pd.DataFrame:
        self.df['Clean_Description'] = self.df['Narration'].apply(self._clean)
        return self.df

    def _clean(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            return ''

        for pattern, handler in _DISPATCH:
            if pattern.match(text):
                result = handler(text)
                break
        else:
            result = _handle_default(text)

        # Final normalisation
        result = re.sub(r'[.\-_/]+', ' ', result)
        result = _WHITESPACE.sub(' ', result).strip()
        return result