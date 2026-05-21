from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BranchOfficeService(Base):
    __tablename__ = "branch_offices_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_office_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
