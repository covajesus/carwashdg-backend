from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WasherPaySettlement(Base):
    __tablename__ = "washer_pay_settlements"
    __table_args__ = (
        UniqueConstraint(
            "branch_office_id",
            "washer_id",
            "pay_date",
            name="uq_washer_pay_settlement",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_office_id: Mapped[int] = mapped_column(Integer, nullable=False)
    washer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
