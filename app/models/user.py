from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rol_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    password: Mapped[str] = mapped_column(Text, nullable=False, default="")
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(
        "deletedd_date",
        DateTime,
        nullable=True,
    )

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
