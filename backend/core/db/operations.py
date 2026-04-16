from core.db.session import SessionLocal

def upsert_transactions(
    df: object, # pd.DataFrame
    source_file: str = "UNKNOWN",
    period_label: str = "FY2324",
) -> int:
    """
    Insert rows from a clean DataFrame into the DB.
    """
    import pandas as pd
    from sqlalchemy.exc import IntegrityError
    from core.db.models import Transaction

    session = SessionLocal()
    new_rows_count = 0

    print(f"      [DB] Batch upserting {len(df)} transactions into '{period_label}'...")

    try:
        # Fast path
        for _, row in df.iterrows():
            txn = Transaction(
                date              = row["Date"].date() if pd.notnull(row["Date"]) else None,
                narration         = str(row.get("Narration",         "")),
                clean_description = str(row.get("Clean_Description", "")),
                ref_no            = str(row.get("Ref_No",            "")),
                debit             = float(row.get("Debit",   0.0)),
                credit            = float(row.get("Credit",  0.0)),
                balance           = float(row.get("Balance", 0.0)),
                coa_category      = str(row.get("CoA_Category", "Uncategorized")),
                source_file       = source_file,
                period_label      = period_label,
            )
            session.add(txn)
        
        try:
            session.commit()
            new_rows_count = len(df)
        except IntegrityError:
            session.rollback()
            print("      [DB] Partial duplicates detected. Falling back to fine-grained merge...")
            for _, row in df.iterrows():
                try:
                    txn = Transaction(
                        date              = row["Date"].date() if pd.notnull(row["Date"]) else None,
                        narration         = str(row.get("Narration",         "")),
                        clean_description = str(row.get("Clean_Description", "")),
                        ref_no            = str(row.get("Ref_No",            "")),
                        debit             = float(row.get("Debit",   0.0)),
                        credit            = float(row.get("Credit",  0.0)),
                        balance           = float(row.get("Balance", 0.0)),
                        coa_category      = str(row.get("CoA_Category", "Uncategorized")),
                        source_file       = source_file,
                        period_label      = period_label,
                    )
                    session.add(txn)
                    session.commit()
                    new_rows_count += 1
                except IntegrityError:
                    session.rollback()
                    continue

    except Exception as e:
        session.rollback()
        print(f"      [DB] Error during upsert: {e}")
    finally:
        session.close()

    return new_rows_count
