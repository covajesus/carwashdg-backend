from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BranchOfficeWasher(Base):
    __tablename__ = "branch_offices_washers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_office_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    washer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sunday_percentage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    week_percentage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    daily_goal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    daily_goal_percentage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
