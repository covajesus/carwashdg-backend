from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import datetime_to_iso, business_now
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServicePublic, ServiceUpdate


class ServiceNotFoundError(Exception):
    pass


class ServiceValidationError(Exception):
    pass


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def to_public(row: Service) -> ServicePublic:
        return ServicePublic(
            id=str(row.id),
            name=row.service,
            description=(row.description or "").strip(),
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_filter(self, stmt):
        return stmt.where(Service.deleted_date.is_(None))

    def _find_duplicate(self, name: str, except_id: int | None = None) -> Service | None:
        normalized = name.strip().lower()
        stmt = self._active_filter(select(Service)).where(
            func.lower(Service.service) == normalized,
        )
        if except_id is not None:
            stmt = stmt.where(Service.id != except_id)
        return self.db.scalars(stmt).first()

    def list_all(self) -> list[ServicePublic]:
        stmt = self._active_filter(select(Service)).order_by(Service.service)
        return [self.to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, service_id: int) -> ServicePublic:
        stmt = self._active_filter(select(Service)).where(Service.id == service_id)
        row = self.db.scalars(stmt).first()
        if row is None:
            raise ServiceNotFoundError()
        return self.to_public(row)

    def create(self, data: ServiceCreate) -> ServicePublic:
        name = data.name.strip()
        if not name:
            raise ServiceValidationError("El servicio es obligatorio")
        if self._find_duplicate(name):
            raise ServiceValidationError("Ya existe un servicio con ese nombre")

        now = self._now()
        row = Service(
            service=name,
            description=(data.description or "").strip() or None,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, service_id: int, data: ServiceUpdate) -> ServicePublic:
        row = self.db.get(Service, service_id)
        if row is None or not row.is_active:
            raise ServiceNotFoundError()

        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise ServiceValidationError("El servicio no puede quedar vacío")
            if self._find_duplicate(name, except_id=service_id):
                raise ServiceValidationError("Ya existe un servicio con ese nombre")
            row.service = name

        if data.description is not None:
            row.description = data.description.strip() or None

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, service_id: int) -> None:
        row = self.db.get(Service, service_id)
        if row is None or not row.is_active:
            raise ServiceNotFoundError()
        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
