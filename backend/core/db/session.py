import os

# Database path (lazily resolved)
def _get_db_config():
    out_dir = os.path.join("data", "output")
    db_path = os.path.join(out_dir, "finsight.db")
    return out_dir, f"sqlite:///{db_path}"

# Global engine/session cache
_ENGINE = None
_SESSION_FACTORY = None

def get_engine():
    global _ENGINE
    if _ENGINE is None:
        from sqlalchemy import create_engine
        out_dir, db_url = _get_db_config()
        # Only create directory when we actually need the engine
        os.makedirs(out_dir, exist_ok=True)
        _ENGINE = create_engine(
            db_url, 
            echo=False, 
            connect_args={"timeout": 30}
        )
    return _ENGINE

def SessionLocal():
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        from sqlalchemy.orm import sessionmaker
        engine = get_engine()
        _SESSION_FACTORY = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _SESSION_FACTORY()

def _migrate_add_column(conn, column_def: str) -> None:
    from sqlalchemy import text
    try:
        conn.execute(text(f"ALTER TABLE transactions ADD COLUMN {column_def}"))
        conn.commit()
    except Exception:
        pass

def init_db() -> None:
    from core.db.models import Base
    engine = get_engine()
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        _migrate_add_column(conn, "source_file  TEXT DEFAULT 'UNKNOWN'")
        _migrate_add_column(conn, "period_label TEXT DEFAULT 'FY2324'")
