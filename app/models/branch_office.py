from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BranchOffice(Base):
    __tablename__ = "branch_offices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_office: Mapped[str] = mapped_column(String(255), nullable=False)
    management_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
