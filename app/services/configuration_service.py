import re
from datetime import datetime

from app.core.datetime_utils import business_now
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.configuration import Configuration
from app.schemas.configuration import ConfigurationPublic, ConfigurationUpdate

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_URL_LABELS: dict[str, str] = {
    "facebook_url": "Facebook",
    "twitter_url": "Twitter",
    "tiktok_url": "TikTok",
    "instagram_url": "Instagram",
}


class ConfigurationValidationError(Exception):
    pass


class ConfigurationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def _is_valid_url(value: str) -> bool:
        if not value.strip():
            return True
        try:
            parsed = urlparse(value.strip())
            return parsed.scheme in ("http", "https")
        except ValueError:
            return False

    @staticmethod
    def to_public(row: Configuration, *, updated_date: datetime | None = None) -> ConfigurationPublic:
        return ConfigurationPublic(
            phone=row.phone,
            email=row.email,
            address=row.address,
            facebook_url=row.facebook_url,
            twitter_url=row.twitter_url,
            tiktok_url=row.tiktok_url,
            instagram_url=row.instagram_url,
            updated_date=updated_date,
        )

    def _get_or_create_row(self) -> Configuration:
        row = self.db.get(Configuration, 1)
        if row is not None:
            return row

        row = self.db.scalars(select(Configuration).limit(1)).first()
        if row is not None:
            return row

        row = Configuration(
            id=1,
            phone="",
            email="",
            address="",
            tiktok_url="",
            facebook_url="",
            twitter_url="",
            instagram_url="",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_settings(self) -> ConfigurationPublic:
        row = self._get_or_create_row()
        return self.to_public(row)

    def update_settings(self, data: ConfigurationUpdate) -> ConfigurationPublic:
        row = self._get_or_create_row()
        patch = data.model_dump(exclude_unset=True)

        if "email" in patch:
            email = (patch["email"] or "").strip()
            if email and not _EMAIL_RE.match(email):
                raise ConfigurationValidationError("El correo electrónico no es válido")
            row.email = email

        if "phone" in patch:
            row.phone = (patch["phone"] or "").strip()

        if "address" in patch:
            row.address = (patch["address"] or "").strip()

        for key in _URL_LABELS:
            if key in patch:
                value = (patch[key] or "").strip()
                if not self._is_valid_url(value):
                    raise ConfigurationValidationError(
                        f"La URL de {_URL_LABELS[key]} no es válida",
                    )
                setattr(row, key, value)

        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row, updated_date=self._now())
