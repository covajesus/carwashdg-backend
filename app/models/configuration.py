from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Configuration(Base):
    __tablename__ = "configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    tiktok_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    facebook_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    twitter_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    instagram_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
