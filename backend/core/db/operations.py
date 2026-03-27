import pandas as pd
from sqlalchemy.exc import IntegrityError
from core.db.session import SessionLocal
from core.db.models import Transaction


def upsert_transactions(df: pd.DataFrame) -> int:
    """
    Takes a clean Pandas DataFrame containing CoA_Category and inserts it
    into the database. Returns the number of successfully inserted new rows.
    Duplicate rows (same date, narration, debit, credit, balance) are skipped.
    """
    session = SessionLocal()
    new_rows_count = 0

    try:
        for _, row in df.iterrows():
            txn = Transaction(
                date=row["Date"].date() if pd.notnull(row["Date"]) else None,
                narration=str(row.get("Narration", "")),
                clean_description=str(row.get("Clean_Description", "")),
                ref_no=str(row.get("Ref_No", "")),
                debit=float(row.get("Debit", 0.0)),
                credit=float(row.get("Credit", 0.0)),
                balance=float(row.get("Balance", 0.0)),
                coa_category=str(row.get("CoA_Category", "Uncategorized")),
            )

            session.add(txn)
            try:
                session.commit()
                new_rows_count += 1
            except IntegrityError:
                # This transaction already exists per the UniqueConstraint
                session.rollback()

    except Exception as e:
        session.rollback()
        print(f"      [DB] Error during upsert: {e}")
    finally:
        session.close()

    return new_rows_count
