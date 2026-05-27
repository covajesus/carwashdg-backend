from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    car_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license_plate_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_efectivo_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_transbank_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tip: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subtotal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total: Mapped[str | None] = mapped_column(String(255), nullable=True)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(
        "update_date",
        DateTime,
        nullable=True,
    )
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
