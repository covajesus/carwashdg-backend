from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketBranchOfficeService(Base):
    __tablename__ = "tickets_branch_offices_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    washer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    washer_daily_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    additional_service: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
