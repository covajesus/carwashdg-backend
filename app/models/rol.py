from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Rol(Base):
    __tablename__ = "rols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rol: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
