from datetime import datetime

from app.core.datetime_utils import business_now

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch_office import BranchOffice
from app.models.branch_office_washer import BranchOfficeWasher


class BranchOfficeWasherValidationError(Exception):
    pass


class BranchOfficeWasherService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def _normalize_required_text(value: str | None, *, label: str) -> str:
        text = (value or "").strip()
        if not text:
            raise BranchOfficeWasherValidationError(f"Indique {label}")
        if len(text) > 255:
            raise BranchOfficeWasherValidationError(f"{label} es demasiado largo")
        return text

    @staticmethod
    def _normalize_optional_text(value: str | None, *, label: str) -> str | None:
        text = (value or "").strip()
        if not text:
            return None
        if len(text) > 255:
            raise BranchOfficeWasherValidationError(f"{label} es demasiado largo")
        return text

    def _active_filter(self, stmt):
        return stmt.where(BranchOfficeWasher.deleted_date.is_(None))

    def list_washer_ids_for_branch(self, branch_office_id: int) -> list[int]:
        if branch_office_id <= 0:
            return []
        rows = self.db.scalars(
            self._active_filter(select(BranchOfficeWasher)).where(
                BranchOfficeWasher.branch_office_id == branch_office_id,
            ),
        ).all()
        ids: list[int] = []
        for row in rows:
            if row.washer_id is not None and row.washer_id > 0:
                ids.append(row.washer_id)
        return ids

    def get_branch_office_id_for_washer(self, washer_id: int) -> int | None:
        row = self.get_active_assignment_for_washer(washer_id)
        if row is None or row.branch_office_id is None:
            return None
        return row.branch_office_id

    def get_active_assignment_for_washer(
        self,
        washer_id: int,
    ) -> BranchOfficeWasher | None:
        if washer_id <= 0:
            return None
        return self.db.scalars(
            self._active_filter(select(BranchOfficeWasher))
            .where(BranchOfficeWasher.washer_id == washer_id)
            .limit(1),
        ).first()

    def assign_washer_to_branch(
        self,
        washer_id: int,
        branch_office_id: int,
        *,
        week_percentage: str | None = None,
        sunday_percentage: str | None = None,
        daily_goal: str | None = None,
        daily_goal_percentage: str | None = None,
        commit: bool = True,
    ) -> None:
        if washer_id <= 0:
            raise BranchOfficeWasherValidationError("Lavador no válido")
        if branch_office_id <= 0:
            raise BranchOfficeWasherValidationError("Seleccione una sucursal")

        branch = self.db.get(BranchOffice, branch_office_id)
        if branch is None or not branch.is_active:
            raise BranchOfficeWasherValidationError("La sucursal no existe")

        week = self._normalize_required_text(
            week_percentage,
            label="el porcentaje por día (lunes a sábado)",
        )
        sunday = self._normalize_required_text(
            sunday_percentage,
            label="el porcentaje domingo",
        )
        goal = self._normalize_optional_text(daily_goal, label="la meta diaria")
        goal_pct = self._normalize_optional_text(
            daily_goal_percentage,
            label="el porcentaje de meta diario",
        )

        now = self._now()
        active_rows = self.db.scalars(
            self._active_filter(select(BranchOfficeWasher)).where(
                BranchOfficeWasher.washer_id == washer_id,
            ),
        ).all()
        for row in active_rows:
            row.deleted_date = now
            row.updated_date = now

        self.db.add(
            BranchOfficeWasher(
                branch_office_id=branch_office_id,
                washer_id=washer_id,
                week_percentage=week,
                sunday_percentage=sunday,
                daily_goal=goal,
                daily_goal_percentage=goal_pct,
                added_date=now,
                updated_date=now,
                deleted_date=None,
            ),
        )
        if commit:
            self.db.commit()

    def update_washer_percentages(
        self,
        washer_id: int,
        *,
        week_percentage: str | None = None,
        sunday_percentage: str | None = None,
        daily_goal: str | None = None,
        daily_goal_percentage: str | None = None,
        commit: bool = True,
    ) -> None:
        row = self.get_active_assignment_for_washer(washer_id)
        if row is None:
            raise BranchOfficeWasherValidationError(
                "El lavador no tiene sucursal asignada",
            )
        now = self._now()
        if week_percentage is not None:
            row.week_percentage = self._normalize_required_text(
                week_percentage,
                label="el porcentaje por día (lunes a sábado)",
            )
        if sunday_percentage is not None:
            row.sunday_percentage = self._normalize_required_text(
                sunday_percentage,
                label="el porcentaje domingo",
            )
        if daily_goal is not None:
            row.daily_goal = self._normalize_optional_text(
                daily_goal,
                label="la meta diaria",
            )
        if daily_goal_percentage is not None:
            row.daily_goal_percentage = self._normalize_optional_text(
                daily_goal_percentage,
                label="el porcentaje de meta diario",
            )
        row.updated_date = now
        if commit:
            self.db.commit()

    def soft_delete_for_washer(self, washer_id: int, *, commit: bool = True) -> None:
        if washer_id <= 0:
            return
        now = self._now()
        rows = self.db.scalars(
            self._active_filter(select(BranchOfficeWasher)).where(
                BranchOfficeWasher.washer_id == washer_id,
            ),
        ).all()
        for row in rows:
            row.deleted_date = now
            row.updated_date = now
        if commit and rows:
            self.db.commit()
