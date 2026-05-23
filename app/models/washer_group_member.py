from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WasherGroupMember(Base):
    __tablename__ = "washer_group_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    washer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.deleted_date is None
