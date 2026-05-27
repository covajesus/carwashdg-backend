from datetime import datetime

from app.core.datetime_utils import business_now

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch_office import BranchOffice
from app.schemas.branch_office import BranchOfficeCreate, BranchOfficePublic, BranchOfficeUpdate


class BranchOfficeNotFoundError(Exception):
    pass


class BranchOfficeValidationError(Exception):
    pass


class BranchOfficeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def _management_type_id(row: BranchOffice) -> int:
        value = getattr(row, "management_type_id", None)
        if value in (1, 2):
            return int(value)
        return 1

    @staticmethod
    def _validate_management_type(management_type_id: int) -> None:
        if management_type_id not in (1, 2):
            raise BranchOfficeValidationError(
                "Tipo de gestión inválido (use 1 Administrada o 2 Subarriendo)",
            )

    @staticmethod
    def to_public(row: BranchOffice) -> BranchOfficePublic:
        return BranchOfficePublic(
            id=str(row.id),
            name=row.branch_office,
            active=row.is_active,
            managementTypeId=BranchOfficeService._management_type_id(row),
        )

    def list_all(self) -> list[BranchOfficePublic]:
        stmt = select(BranchOffice).order_by(BranchOffice.id)
        rows = self.db.scalars(stmt).all()
        return [self.to_public(row) for row in rows]

    def get_by_id(self, branch_id: int) -> BranchOfficePublic:
        row = self.db.get(BranchOffice, branch_id)
        if row is None:
            raise BranchOfficeNotFoundError()
        return self.to_public(row)

    def create(self, data: BranchOfficeCreate) -> BranchOfficePublic:
        name = data.name.strip()
        if not name:
            raise BranchOfficeValidationError("La sucursal es obligatoria")
        self._validate_management_type(data.managementTypeId)

        now = self._now()
        row = BranchOffice(
            branch_office=name,
            management_type_id=data.managementTypeId,
            added_date=now,
            updated_date=now,
            deleted_date=None if data.active else now,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, branch_id: int, data: BranchOfficeUpdate) -> BranchOfficePublic:
        row = self.db.get(BranchOffice, branch_id)
        if row is None:
            raise BranchOfficeNotFoundError()

        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise BranchOfficeValidationError("La sucursal no puede quedar vacía")
            row.branch_office = name

        if data.active is not None:
            row.deleted_date = None if data.active else self._now()

        if data.managementTypeId is not None:
            self._validate_management_type(data.managementTypeId)
            row.management_type_id = data.managementTypeId

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, branch_id: int) -> None:
        row = self.db.get(BranchOffice, branch_id)
        if row is None:
            raise BranchOfficeNotFoundError()

        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
