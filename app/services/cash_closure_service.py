from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import business_now, business_today
from app.core.roles import MANAGER_ROL_ID
from app.models.manager_cash_closure import (
    CASH_CLOSURE_STATUS_CLOSED,
    CASH_CLOSURE_STATUS_OPEN,
    ManagerCashClosure,
)
from app.schemas.cash_closure import CashClosureConfirmResponse, CashClosureTodayResponse
from app.schemas.user import UserPublic


class CashClosureValidationError(Exception):
    pass


class CashClosureService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def _today() -> date:
        return business_today()

    @staticmethod
    def _require_manager(user: UserPublic) -> int:
        if user.role != "manager":
            raise CashClosureValidationError("Solo encargados pueden cerrar caja")
        try:
            manager_id = int(user.id)
        except (TypeError, ValueError) as exc:
            raise CashClosureValidationError("Usuario no válido") from exc
        if manager_id < 1:
            raise CashClosureValidationError("Usuario no válido")
        return manager_id

    def _get_row(self, manager_id: int, closure_date: date) -> ManagerCashClosure | None:
        return self.db.scalars(
            select(ManagerCashClosure).where(
                ManagerCashClosure.manager_id == manager_id,
                ManagerCashClosure.closure_date == closure_date,
            ),
        ).first()

    def today_status(self, user: UserPublic) -> CashClosureTodayResponse:
        manager_id = self._require_manager(user)
        today = self._today()
        row = self._get_row(manager_id, today)
        if row is None:
            return CashClosureTodayResponse(
                date=today,
                status_id=None,
                already_closed=False,
                needs_confirmation=True,
            )
        closed = int(row.status_id) == CASH_CLOSURE_STATUS_CLOSED
        return CashClosureTodayResponse(
            date=today,
            status_id=int(row.status_id),
            already_closed=closed,
            needs_confirmation=not closed,
        )

    def confirm_close(self, user: UserPublic) -> CashClosureConfirmResponse:
        manager_id = self._require_manager(user)
        today = self._today()
        row = self._get_row(manager_id, today)
        now = self._now()

        if row is not None and int(row.status_id) == CASH_CLOSURE_STATUS_CLOSED:
            raise CashClosureValidationError("La caja ya ha sido cerrada hoy")

        if row is None:
            row = ManagerCashClosure(
                manager_id=manager_id,
                closure_date=today,
                status_id=CASH_CLOSURE_STATUS_CLOSED,
                added_date=now,
                updated_date=now,
            )
            self.db.add(row)
        else:
            row.status_id = CASH_CLOSURE_STATUS_CLOSED
            row.updated_date = now

        self.db.commit()
        self.db.refresh(row)
        return CashClosureConfirmResponse(
            date=today,
            status_id=int(row.status_id),
        )

    @staticmethod
    def manager_role_id() -> int:
        return MANAGER_ROL_ID
