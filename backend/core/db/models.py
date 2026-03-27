from sqlalchemy import Column, Integer, String, Float, Date, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    date              = Column(Date,   nullable=False)
    narration         = Column(String, nullable=False)
    clean_description = Column(String, nullable=False)
    ref_no            = Column(String, default="")
    debit             = Column(Float,  default=0.0)
    credit            = Column(Float,  default=0.0)
    balance           = Column(Float,  default=0.0)
    coa_category      = Column(String, nullable=False)
    # Provenance columns — added additively; existing rows get safe defaults
    source_file       = Column(String, default="UNKNOWN")
    period_label      = Column(String, default="FY2324")

    __table_args__ = (
        UniqueConstraint(
            "date", "narration", "debit", "credit", "balance",
            name="_stmt_row_uc"
        ),
    )
