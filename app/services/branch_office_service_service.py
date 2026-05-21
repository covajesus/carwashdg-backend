from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch_office import BranchOffice
from app.models.branch_office_service import BranchOfficeService
from app.models.car_type import CarType
from app.models.service import Service
from app.schemas.branch_office_service import (
    BranchOfficeServiceCreate,
    BranchOfficeServicePublic,
    BranchOfficeServiceUpdate,
)


class BranchOfficeServiceNotFoundError(Exception):
    pass


class BranchOfficeServiceValidationError(Exception):
    pass


class BranchOfficeServiceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    @staticmethod
    def to_public(row: BranchOfficeService) -> BranchOfficeServicePublic:
        return BranchOfficeServicePublic(
            id=str(row.id),
            branch_office_id=str(row.branch_office_id or ""),
            service_id=str(row.service_id or ""),
            car_type_id=str(row.car_type_id or ""),
            added_date=row.added_date,
            updated_date=row.updated_date,
            deleted_date=row.deleted_date,
        )

    def _active_filter(self, stmt):
        return stmt.where(BranchOfficeService.deleted_date.is_(None))

    def _validate_refs(
        self,
        branch_office_id: int | None,
        service_id: int | None,
        car_type_id: int | None,
    ) -> None:
        if branch_office_id is not None and self.db.get(BranchOffice, branch_office_id) is None:
            raise BranchOfficeServiceValidationError("La sucursal no existe")
        if service_id is not None and self.db.get(Service, service_id) is None:
            raise BranchOfficeServiceValidationError("El servicio no existe")
        if car_type_id is not None:
            car = self.db.get(CarType, car_type_id)
            if car is None or not car.is_active:
                raise BranchOfficeServiceValidationError("El tipo de vehículo no existe")

    def _find_duplicate(
        self,
        *,
        branch_office_id: int,
        service_id: int,
        car_type_id: int,
        except_id: int | None = None,
    ) -> BranchOfficeService | None:
        stmt = self._active_filter(select(BranchOfficeService)).where(
            BranchOfficeService.branch_office_id == branch_office_id,
            BranchOfficeService.service_id == service_id,
            BranchOfficeService.car_type_id == car_type_id,
        )
        if except_id is not None:
            stmt = stmt.where(BranchOfficeService.id != except_id)
        return self.db.scalars(stmt).first()

    def list_all(
        self,
        *,
        branch_office_id: int | None = None,
        service_id: int | None = None,
        car_type_id: int | None = None,
    ) -> list[BranchOfficeServicePublic]:
        stmt = self._active_filter(select(BranchOfficeService))
        if branch_office_id is not None:
            stmt = stmt.where(BranchOfficeService.branch_office_id == branch_office_id)
        if service_id is not None:
            stmt = stmt.where(BranchOfficeService.service_id == service_id)
        if car_type_id is not None:
            stmt = stmt.where(BranchOfficeService.car_type_id == car_type_id)
        stmt = stmt.order_by(
            BranchOfficeService.branch_office_id,
            BranchOfficeService.car_type_id,
            BranchOfficeService.id,
        )
        return [self.to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, row_id: int) -> BranchOfficeServicePublic:
        stmt = self._active_filter(select(BranchOfficeService)).where(
            BranchOfficeService.id == row_id,
        )
        row = self.db.scalars(stmt).first()
        if row is None:
            raise BranchOfficeServiceNotFoundError()
        return self.to_public(row)

    def create(self, data: BranchOfficeServiceCreate) -> BranchOfficeServicePublic:
        self._validate_refs(data.branch_office_id, data.service_id, data.car_type_id)
        if self._find_duplicate(
            branch_office_id=data.branch_office_id,
            service_id=data.service_id,
            car_type_id=data.car_type_id,
        ):
            raise BranchOfficeServiceValidationError(
                "Ya existe esta combinación de sucursal, servicio y tipo de vehículo",
            )
        now = self._now()
        row = BranchOfficeService(
            branch_office_id=data.branch_office_id,
            service_id=data.service_id,
            car_type_id=data.car_type_id,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, row_id: int, data: BranchOfficeServiceUpdate) -> BranchOfficeServicePublic:
        row = self.db.get(BranchOfficeService, row_id)
        if row is None or not row.is_active:
            raise BranchOfficeServiceNotFoundError()

        branch_id = data.branch_office_id if data.branch_office_id is not None else row.branch_office_id
        service_id = data.service_id if data.service_id is not None else row.service_id
        car_type_id = data.car_type_id if data.car_type_id is not None else row.car_type_id
        self._validate_refs(branch_id, service_id, car_type_id)

        if branch_id is None or service_id is None or car_type_id is None:
            raise BranchOfficeServiceValidationError(
                "Sucursal, servicio y tipo de vehículo son obligatorios",
            )

        if self._find_duplicate(
            branch_office_id=branch_id,
            service_id=service_id,
            car_type_id=car_type_id,
            except_id=row_id,
        ):
            raise BranchOfficeServiceValidationError(
                "Ya existe esta combinación de sucursal, servicio y tipo de vehículo",
            )

        if data.branch_office_id is not None:
            row.branch_office_id = data.branch_office_id
        if data.service_id is not None:
            row.service_id = data.service_id
        if data.car_type_id is not None:
            row.car_type_id = data.car_type_id

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, row_id: int) -> None:
        row = self.db.get(BranchOfficeService, row_id)
        if row is None or not row.is_active:
            raise BranchOfficeServiceNotFoundError()
        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
