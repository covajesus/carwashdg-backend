from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExpenseType(Base):
    __tablename__ = "expense_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    classification: Mapped[str] = mapped_column(String(16), nullable=False, default="bank")
    admin_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
