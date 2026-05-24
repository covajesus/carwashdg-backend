from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import datetime_to_iso, business_now
from app.models.car_type import CarType
from app.schemas.car_type import CarTypeCreate, CarTypePublic, CarTypeUpdate


class CarTypeNotFoundError(Exception):
    pass


class CarTypeValidationError(Exception):
    pass


class CarTypeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def to_public(row: CarType) -> CarTypePublic:
        return CarTypePublic(
            id=str(row.id),
            car_type=row.car_type,
            icon=row.icon,
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_filter(self, stmt):
        return stmt.where(CarType.deleted_date.is_(None))

    def _find_duplicate(self, car_type: str, except_id: int | None = None) -> CarType | None:
        normalized = car_type.strip().lower()
        stmt = self._active_filter(select(CarType)).where(
            func.lower(CarType.car_type) == normalized,
        )
        if except_id is not None:
            stmt = stmt.where(CarType.id != except_id)
        return self.db.scalars(stmt).first()

    def list_all(self) -> list[CarTypePublic]:
        stmt = (
            self._active_filter(select(CarType))
            .order_by(CarType.car_type)
        )
        rows = self.db.scalars(stmt).all()
        return [self.to_public(row) for row in rows]

    def get_by_id(self, car_type_id: int) -> CarTypePublic:
        stmt = self._active_filter(select(CarType)).where(CarType.id == car_type_id)
        row = self.db.scalars(stmt).first()
        if row is None:
            raise CarTypeNotFoundError()
        return self.to_public(row)

    def create(self, data: CarTypeCreate) -> CarTypePublic:
        name = data.car_type.strip()
        if not name:
            raise CarTypeValidationError("El tipo de vehículo es obligatorio")
        if self._find_duplicate(name):
            raise CarTypeValidationError("Ya existe un tipo con ese nombre")

        now = self._now()
        row = CarType(
            car_type=name,
            icon=(data.icon or "").strip(),
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, car_type_id: int, data: CarTypeUpdate) -> CarTypePublic:
        row = self.db.get(CarType, car_type_id)
        if row is None or not row.is_active:
            raise CarTypeNotFoundError()

        if data.car_type is not None:
            name = data.car_type.strip()
            if not name:
                raise CarTypeValidationError("El tipo no puede quedar vacío")
            if self._find_duplicate(name, except_id=car_type_id):
                raise CarTypeValidationError("Ya existe un tipo con ese nombre")
            row.car_type = name

        if data.icon is not None:
            row.icon = data.icon.strip()

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, car_type_id: int) -> None:
        row = self.db.get(CarType, car_type_id)
        if row is None or not row.is_active:
            raise CarTypeNotFoundError()

        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
