import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.db.models import Base

# Database path
OUT_DIR = os.path.join("data", "output")
os.makedirs(OUT_DIR, exist_ok=True)
DB_PATH = os.path.join(OUT_DIR, "finsight.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine and session maker
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create tables if they don't exist."""
    Base.metadata.create_all(engine)
