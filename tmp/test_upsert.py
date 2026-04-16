import pandas as pd
from datetime import datetime
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.db.session import init_db
from core.db.operations import upsert_transactions

def test_upsert():
    print("Initializing test DB...")
    init_db()
    
    # Create sample data
    df = pd.DataFrame([
        {
            "Date": datetime(2023, 4, 1),
            "Narration": "Test Transaction 1",
            "Clean_Description": "Test 1",
            "Ref_No": "REF001",
            "Debit": 100.0,
            "Credit": 0.0,
            "Balance": 900.0,
            "CoA_Category": "Travel & Transport"
        },
        {
            "Date": datetime(2023, 4, 2),
            "Narration": "Test Transaction 2",
            "Clean_Description": "Test 2",
            "Ref_No": "REF002",
            "Debit": 0.0,
            "Credit": 500.0,
            "Balance": 1400.0,
            "CoA_Category": "Income"
        }
    ])
    
    print("Performing first upsert (batch mode)...")
    count = upsert_transactions(df, source_file="test_file.pdf", period_label="TEST_Q1")
    print(f"Inserted: {count}")
    
    print("Performing second upsert (duplicates)...")
    count = upsert_transactions(df, source_file="test_file.pdf", period_label="TEST_Q1")
    print(f"Inserted (should be 0): {count}")

if __name__ == "__main__":
    test_upsert()
