from datetime import datetime

from app.core.datetime_utils import business_now

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch_office import BranchOffice
from app.models.branch_office_manager import BranchOfficeManager


class BranchOfficeManagerValidationError(Exception):
    pass


class BranchOfficeManagerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    def _active_filter(self, stmt):
        return stmt.where(BranchOfficeManager.deleted_date.is_(None))

    def get_branch_office_id_for_manager(self, manager_id: int) -> int | None:
        if manager_id <= 0:
            return None
        row = self.db.scalars(
            self._active_filter(select(BranchOfficeManager))
            .where(BranchOfficeManager.manager_id == manager_id)
            .limit(1),
        ).first()
        if row is None or row.branch_office_id is None:
            return None
        return row.branch_office_id

    def assign_manager_to_branch(
        self,
        manager_id: int,
        branch_office_id: int,
        *,
        commit: bool = True,
    ) -> None:
        if manager_id <= 0:
            raise BranchOfficeManagerValidationError("Gerente no válido")
        if branch_office_id <= 0:
            raise BranchOfficeManagerValidationError("Seleccione una sucursal")

        branch = self.db.get(BranchOffice, branch_office_id)
        if branch is None or not branch.is_active:
            raise BranchOfficeManagerValidationError("La sucursal no existe")

        now = self._now()
        active_rows = self.db.scalars(
            self._active_filter(select(BranchOfficeManager)).where(
                BranchOfficeManager.manager_id == manager_id,
            ),
        ).all()
        for row in active_rows:
            row.deleted_date = now
            row.updated_date = now

        self.db.add(
            BranchOfficeManager(
                branch_office_id=branch_office_id,
                manager_id=manager_id,
                added_date=now,
                updated_date=now,
                deleted_date=None,
            ),
        )
        if commit:
            self.db.commit()

    def soft_delete_for_manager(self, manager_id: int, *, commit: bool = True) -> None:
        if manager_id <= 0:
            return
        now = self._now()
        rows = self.db.scalars(
            self._active_filter(select(BranchOfficeManager)).where(
                BranchOfficeManager.manager_id == manager_id,
            ),
        ).all()
        for row in rows:
            row.deleted_date = now
            row.updated_date = now
        if commit and rows:
            self.db.commit()
