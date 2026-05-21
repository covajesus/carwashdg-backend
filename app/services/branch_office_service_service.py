from datetime import datetime

from sqlalchemy import select

from app.core.pricing import round_pesos
from sqlalchemy.orm import Session

from app.models.branch_office import BranchOffice
from app.models.branch_office_service import BranchOfficeService
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
        price = round_pesos(row.price or 0)
        return BranchOfficeServicePublic(
            id=str(row.id),
            branch_office_id=str(row.branch_office_id or ""),
            service_id=str(row.service_id or ""),
            price=price,
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
    ) -> None:
        if branch_office_id is not None and self.db.get(BranchOffice, branch_office_id) is None:
            raise BranchOfficeServiceValidationError("La sucursal no existe")
        if service_id is not None and self.db.get(Service, service_id) is None:
            raise BranchOfficeServiceValidationError("El servicio no existe")

    def list_all(
        self,
        *,
        branch_office_id: int | None = None,
        service_id: int | None = None,
    ) -> list[BranchOfficeServicePublic]:
        stmt = self._active_filter(select(BranchOfficeService))
        if branch_office_id is not None:
            stmt = stmt.where(BranchOfficeService.branch_office_id == branch_office_id)
        if service_id is not None:
            stmt = stmt.where(BranchOfficeService.service_id == service_id)
        stmt = stmt.order_by(BranchOfficeService.branch_office_id, BranchOfficeService.id)
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
        self._validate_refs(data.branch_office_id, data.service_id)
        now = self._now()
        row = BranchOfficeService(
            branch_office_id=data.branch_office_id,
            service_id=data.service_id,
            price=round_pesos(data.price),
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
        self._validate_refs(branch_id, service_id)

        if data.branch_office_id is not None:
            row.branch_office_id = data.branch_office_id
        if data.service_id is not None:
            row.service_id = data.service_id
        if data.price is not None:
            row.price = round_pesos(data.price)

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

    def get_price(self, row_id: int) -> int:
        row = self.db.get(BranchOfficeService, row_id)
        if row is None or not row.is_active:
            return 0
        return round_pesos(row.price or 0)
