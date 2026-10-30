import base64
import hashlib
import re
from datetime import datetime

from app.core.datetime_utils import business_now
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.configuration import Configuration
from app.schemas.configuration import ConfigurationPublic, ConfigurationRead, ConfigurationUpdate

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_BENEFIT_IMAGE_FIELDS = (
    "benefit_ecological_image",
    "benefit_fast_image",
    "benefit_professional_image",
    "benefit_premium_image",
)

_BENEFIT_SLOTS: dict[str, str] = {
    "ecological": "benefit_ecological_image",
    "fast": "benefit_fast_image",
    "professional": "benefit_professional_image",
    "premium": "benefit_premium_image",
}

_BENEFIT_IMAGE_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
}

_MAX_BENEFIT_IMAGE_BYTES = 2 * 1024 * 1024

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
            raffle_status_id=1 if int(getattr(row, "raffle_status_id", 1) or 0) == 1 else 0,
            benefit_ecological_image=ConfigurationService._published_benefit_image(
                row.benefit_ecological_image,
                "ecological",
            ),
            benefit_fast_image=ConfigurationService._published_benefit_image(
                row.benefit_fast_image,
                "fast",
            ),
            benefit_professional_image=ConfigurationService._published_benefit_image(
                row.benefit_professional_image,
                "professional",
            ),
            benefit_premium_image=ConfigurationService._published_benefit_image(
                row.benefit_premium_image,
                "premium",
            ),
            updated_date=updated_date,
        )

    @staticmethod
    def to_admin_settings(row: Configuration, *, updated_date: datetime | None = None) -> ConfigurationRead:
        return ConfigurationRead(
            id=row.id,
            phone=row.phone,
            email=row.email,
            address=row.address,
            facebook_url=row.facebook_url,
            twitter_url=row.twitter_url,
            tiktok_url=row.tiktok_url,
            instagram_url=row.instagram_url,
            coin_round_status_id=int(row.coin_round_status_id or 0),
            raffle_status_id=1 if int(getattr(row, "raffle_status_id", 1) or 0) == 1 else 0,
            benefit_ecological_image=ConfigurationService._published_benefit_image(
                row.benefit_ecological_image,
                "ecological",
            ),
            benefit_fast_image=ConfigurationService._published_benefit_image(
                row.benefit_fast_image,
                "fast",
            ),
            benefit_professional_image=ConfigurationService._published_benefit_image(
                row.benefit_professional_image,
                "professional",
            ),
            benefit_premium_image=ConfigurationService._published_benefit_image(
                row.benefit_premium_image,
                "premium",
            ),
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
            coin_round_status_id=0,
            raffle_status_id=1,
            benefit_ecological_image="",
            benefit_fast_image="",
            benefit_professional_image="",
            benefit_premium_image="",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_admin_settings(self) -> ConfigurationRead:
        row = self._get_or_create_row()
        return self.to_admin_settings(row)

    def get_settings(self) -> ConfigurationPublic:
        row = self._get_or_create_row()
        return self.to_public(row)

    def update_settings(self, data: ConfigurationUpdate) -> ConfigurationRead:
        row = self._get_or_create_row()
        patch = data.model_dump(exclude_unset=True)

        if "coin_round_status_id" in patch:
            value = patch["coin_round_status_id"]
            row.coin_round_status_id = 1 if int(value or 0) == 1 else 0

        if "raffle_status_id" in patch:
            value = patch["raffle_status_id"]
            row.raffle_status_id = 1 if int(value or 0) == 1 else 0

        if "email" in patch:
            email = (patch["email"] or "").strip()
            if email and not _EMAIL_RE.match(email):
                raise ConfigurationValidationError("El correo electrónico no es válido")
            row.email = email

        if "phone" in patch:
            row.phone = (patch["phone"] or "").strip()

        if "address" in patch:
            row.address = (patch["address"] or "").strip()

        for key in _BENEFIT_IMAGE_FIELDS:
            if key not in patch:
                continue
            value = (patch[key] or "").strip()
            if value and not value.startswith("/") and not self._is_valid_url(value):
                raise ConfigurationValidationError("La imagen debe ser una URL http o https")
            setattr(row, key, value)

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
        return self.to_admin_settings(row, updated_date=self._now())

    @staticmethod
    def _published_benefit_image(raw: str | None, slot: str) -> str:
        value = (raw or "").strip()
        if not value.startswith("data:image/"):
            return value
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        return f"configurations/benefit-images/{slot}?v={digest}"

    def read_benefit_image(self, slot: str) -> tuple[bytes, str]:
        column = _BENEFIT_SLOTS.get(slot)
        if column is None:
            raise ConfigurationValidationError("Imagen no encontrada")
        row = self._get_or_create_row()
        raw = (getattr(row, column) or "").strip()
        if not raw.startswith("data:image/") or "," not in raw:
            raise ConfigurationValidationError("Imagen no encontrada")
        header, encoded = raw.split(",", 1)
        media_type = header[5:].split(";")[0].strip().lower() or "application/octet-stream"
        try:
            content = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ConfigurationValidationError("Imagen no encontrada") from exc
        if not content:
            raise ConfigurationValidationError("Imagen no encontrada")
        return content, media_type

    def save_benefit_image(self, slot: str, content_type: str, content: bytes) -> ConfigurationRead:
        column = _BENEFIT_SLOTS.get(slot)
        if column is None:
            raise ConfigurationValidationError("Imagen no encontrada")
        media_type = _BENEFIT_IMAGE_TYPES.get((content_type or "").split(";")[0].strip().lower())
        if media_type is None:
            raise ConfigurationValidationError("La imagen debe ser JPG, PNG o WebP")
        if not content:
            raise ConfigurationValidationError("Seleccione una imagen")
        if len(content) > _MAX_BENEFIT_IMAGE_BYTES:
            raise ConfigurationValidationError("La imagen no puede superar 2 MB")
        encoded = base64.b64encode(content).decode("ascii")
        row = self._get_or_create_row()
        setattr(row, column, f"data:{media_type};base64,{encoded}")
        self.db.commit()
        self.db.refresh(row)
        return self.to_admin_settings(row, updated_date=self._now())
