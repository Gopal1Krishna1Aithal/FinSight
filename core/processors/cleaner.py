import re
import pandas as pd

# Matches the statement date-range artifact that leaks into narrations on
# page-boundary rows, e.g. " To:31/03/2019" or " From:01/04/2018"
_DATE_RANGE_ARTIFACT = re.compile(
    r'\s*(From\s*:\s*\d{2}/\d{2}/\d{4}|To\s*:\s*\d{2}/\d{2}/\d{4})',
    flags=re.IGNORECASE,
)

# Matches the FEE row ref-number echo that appears twice in narration,
# e.g. "FEE-ATMCASH...AOR123 AOR123 388"  →  deduplicate the ref echo
_FEE_REF_ECHO = re.compile(r'(AOR\w+)\s+\1\s*\w*', flags=re.IGNORECASE)

# Matches split POS suffix artifacts like trailing " SDEBIT" or " EBIT"
# that weren't fully merged (safety net — extractor handles most of these)
_POS_SUFFIX = re.compile(r'\s+[SE]?DEBIT$', flags=re.IGNORECASE)


class HDFCDataCleaner:
    """
    Converts the list-of-dicts produced by HDFCPDFExtractor into a clean,
    typed Pandas DataFrame ready for validation and AI categorisation.

    Input columns  : Date, Narration, Ref_No, Value_Date, Debit, Credit, Balance
    Output columns : Date (datetime64), Narration (str), Debit (float),
                     Credit (float), Balance (float)
                     — Ref_No and Value_Date are retained internally but
                       not forwarded to downstream steps.
    """

    HEADERS = ['Date', 'Narration', 'Ref_No', 'Value_Date', 'Debit', 'Credit', 'Balance']

    def __init__(self, raw_data: list[dict]):
        self.raw_data = raw_data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(self) -> pd.DataFrame:
        df = self._build_dataframe()
        df = self._clean_narrations(df)
        df = self._coerce_numbers(df)
        df = self._parse_dates(df)
        return df

    # ------------------------------------------------------------------
    # Private steps
    # ------------------------------------------------------------------

    def _build_dataframe(self) -> pd.DataFrame:
        """
        Build a DataFrame from the list of dicts.  Every expected column is
        guaranteed to exist; missing keys default to an empty string.
        """
        rows = []
        for record in self.raw_data:
            row = {col: record.get(col, '').strip() for col in self.HEADERS}
            rows.append(row)
        return pd.DataFrame(rows, columns=self.HEADERS)

    def _clean_narrations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fix narration text issues introduced by PDF word-wrap:

        1. Strip the 'To:DD/MM/YYYY' / 'From:...' page-header artifact that
           leaks into the last narration on some pages.
        2. Deduplicate the echoed ATM fee reference codes
           (e.g. 'AOR1829583474AOR1829583474670 670').
        3. Collapse any leftover whitespace runs to a single space.
        """
        def _fix(text: str) -> str:
            text = _DATE_RANGE_ARTIFACT.sub('', text)
            text = _FEE_REF_ECHO.sub(r'\1', text)
            text = _POS_SUFFIX.sub(' POS DEBIT', text)   # normalise suffix
            return re.sub(r'\s+', ' ', text).strip()

        df = df.copy()
        df['Narration'] = df['Narration'].apply(_fix)
        return df

    def _coerce_numbers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert Debit, Credit, Balance from raw strings to float64.

        Handles:
        - Comma-formatted numbers  : '1,23,456.78'  →  123456.78
        - Empty strings            : ''              →  0.0
        - Negative balances        : '-1,662.58'     →  -1662.58
        """
        df = df.copy()
        for col in ('Debit', 'Credit', 'Balance'):
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(',', '', regex=False)   # remove thousand separators
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        return df

    def _parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parse the Date column (DD/MM/YY or DD/MM/YYYY) to datetime64[ns].
        Value_Date is parsed the same way but kept only for the validator.
        """
        df = df.copy()
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%y', errors='coerce')

        # Some rows use 4-digit years — try those where the first pass failed
        mask_failed = df['Date'].isna()
        if mask_failed.any():
            df.loc[mask_failed, 'Date'] = pd.to_datetime(
                df.loc[mask_failed, 'Date'], format='%d/%m/%Y', errors='coerce'
            )

        return df