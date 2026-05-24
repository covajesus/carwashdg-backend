from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import datetime_to_iso, business_now
from app.models.status import Status
from app.schemas.status import StatusCreate, StatusPublic, StatusUpdate


class StatusNotFoundError(Exception):
    pass


class StatusValidationError(Exception):
    pass


class StatusService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def to_public(row: Status) -> StatusPublic:
        return StatusPublic(
            id=str(row.id),
            status=row.status,
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_filter(self, stmt):
        return stmt.where(Status.deleted_date.is_(None))

    def _find_duplicate(self, status_text: str, except_id: int | None = None) -> Status | None:
        normalized = status_text.strip().lower()
        stmt = self._active_filter(select(Status)).where(
            func.lower(Status.status) == normalized,
        )
        if except_id is not None:
            stmt = stmt.where(Status.id != except_id)
        return self.db.scalars(stmt).first()

    def list_all(self) -> list[StatusPublic]:
        stmt = self._active_filter(select(Status)).order_by(Status.status)
        rows = self.db.scalars(stmt).all()
        return [self.to_public(row) for row in rows]

    def get_by_id(self, status_id: int) -> StatusPublic:
        stmt = self._active_filter(select(Status)).where(Status.id == status_id)
        row = self.db.scalars(stmt).first()
        if row is None:
            raise StatusNotFoundError()
        return self.to_public(row)

    def create(self, data: StatusCreate) -> StatusPublic:
        text = data.status.strip()
        if not text:
            raise StatusValidationError("El estatus es obligatorio")
        if self._find_duplicate(text):
            raise StatusValidationError("Ya existe un estatus con ese nombre")

        now = self._now()
        row = Status(
            status=text,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, status_id: int, data: StatusUpdate) -> StatusPublic:
        row = self.db.get(Status, status_id)
        if row is None or not row.is_active:
            raise StatusNotFoundError()

        if data.status is not None:
            text = data.status.strip()
            if not text:
                raise StatusValidationError("El estatus no puede quedar vacío")
            if self._find_duplicate(text, except_id=status_id):
                raise StatusValidationError("Ya existe un estatus con ese nombre")
            row.status = text

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, status_id: int) -> None:
        row = self.db.get(Status, status_id)
        if row is None or not row.is_active:
            raise StatusNotFoundError()

        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
