import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.db.models import Base

# Database path
OUT_DIR = os.path.join("data", "output")
os.makedirs(OUT_DIR, exist_ok=True)
DB_PATH      = os.path.join(OUT_DIR, "finsight.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine       = create_engine(
    DATABASE_URL, 
    echo=False, 
    connect_args={"timeout": 30}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _migrate_add_column(conn, column_def: str) -> None:
    """
    Safely add a column to the transactions table.
    SQLite has no 'ADD COLUMN IF NOT EXISTS', so we catch OperationalError.
    """
    try:
        conn.execute(text(f"ALTER TABLE transactions ADD COLUMN {column_def}"))
        conn.commit()
    except Exception:
        pass  # Column already exists — silently continue


def init_db() -> None:
    """Create tables if they don't exist, then run additive migrations."""
    Base.metadata.create_all(engine)

    # Additive migration — zero data loss for existing 361 rows
    with engine.connect() as conn:
        _migrate_add_column(conn, "source_file  TEXT DEFAULT 'UNKNOWN'")
        _migrate_add_column(conn, "period_label TEXT DEFAULT 'FY2324'")
