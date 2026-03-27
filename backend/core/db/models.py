from sqlalchemy import Column, Integer, String, Float, Date, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    narration = Column(String, nullable=False)
    clean_description = Column(String, nullable=False)
    ref_no = Column(String, default="")
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    balance = Column(Float, default=0.0)
    coa_category = Column(String, nullable=False)

    __table_args__ = (
        # Unique constraint to prevent duplicate ingestion of the same bank statement lines
        UniqueConstraint(
            "date", "narration", "debit", "credit", "balance", name="_stmt_row_uc"
        ),
    )
