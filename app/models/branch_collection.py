from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BranchCollection(Base):
    __tablename__ = "branch_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_office_id: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
