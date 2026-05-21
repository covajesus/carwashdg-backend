from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RaffleNumber(Base):
    __tablename__ = "raffles_numbers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raffle_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
