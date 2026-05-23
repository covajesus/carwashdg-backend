from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

CASH_CLOSURE_STATUS_OPEN = 0
CASH_CLOSURE_STATUS_CLOSED = 1


class ManagerCashClosure(Base):
    __tablename__ = "manager_cash_closures"
    __table_args__ = (
        UniqueConstraint(
            "manager_id",
            "closure_date",
            name="uq_manager_cash_closure_day",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    manager_id: Mapped[int] = mapped_column(Integer, nullable=False)
    closure_date: Mapped[date] = mapped_column(Date, nullable=False)
    status_id: Mapped[int] = mapped_column(Integer, nullable=False, default=CASH_CLOSURE_STATUS_OPEN)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
