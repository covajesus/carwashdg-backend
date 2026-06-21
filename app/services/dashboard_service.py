from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.branch_scope import branch_scope_for_user
from app.core.datetime_utils import business_today
from app.core.pricing import ticket_totals_from_subtotal
from app.models.branch_office import BranchOffice
from app.schemas.dashboard import DashboardHomeSummaryResponse
from app.schemas.user import UserPublic
from app.services.collection_service import CollectionService
from app.services.expense_service import ExpenseService
from app.services.ticket_service import TicketService, TicketValidationError


class DashboardValidationError(Exception):
    pass


class DashboardForbiddenError(Exception):
    pass


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._tickets = TicketService(db)
        self._collections = CollectionService(db)
        self._expenses = ExpenseService(db)

    @staticmethod
    def _require_admin(user: UserPublic) -> None:
        if branch_scope_for_user(user) is not None:
            raise DashboardForbiddenError()

    @staticmethod
    def _validate_year_month(year: int, month: int) -> None:
        if month < 1 or month > 12:
            raise DashboardValidationError("Mes no válido")
        if year < 2000 or year > 2100:
            raise DashboardValidationError("Año no válido")

    def _month_revenue_subtotal(self, user: UserPublic, *, year: int, month: int) -> int:
        today = business_today()
        last_day = calendar.monthrange(year, month)[1]
        month_prefix = f"{year}-{month:02d}"
        total = 0

        branches = self.db.scalars(select(BranchOffice).order_by(BranchOffice.id)).all()
        for branch in branches:
            branch_id = int(branch.id)
            mgmt = int(branch.management_type_id or 1)

            if mgmt == 1:
                for day_num in range(1, last_day + 1):
                    day = date(year, month, day_num)
                    if day > today:
                        continue
                    try:
                        buckets = self._tickets.ticket_earnings_date_buckets(
                            user,
                            branch_id,
                            revenue_day=day,
                        )
                    except TicketValidationError:
                        continue
                    for totals in buckets.values():
                        total += totals["subtotal"]
                continue

            if mgmt == 2:
                for row in self._collections.list_manual_for_branch(branch_id):
                    if row.collection_date is None or row.gross_amount <= 0:
                        continue
                    day_key = row.collection_date.isoformat()
                    if not day_key.startswith(month_prefix):
                        continue
                    day = date.fromisoformat(day_key)
                    if day > today:
                        continue
                    pricing = ticket_totals_from_subtotal(int(row.gross_amount), apply_iva=False)
                    total += pricing["subtotal"]

        return total

    def build_home_summary(
        self,
        user: UserPublic,
        *,
        year: int,
        month: int,
    ) -> DashboardHomeSummaryResponse:
        self._require_admin(user)
        self._validate_year_month(year, month)

        revenue_subtotal = self._month_revenue_subtotal(user, year=year, month=month)
        expenses_total = self._expenses.month_total_for_user(user, year=year, month=month)

        return DashboardHomeSummaryResponse(
            year=year,
            month=month,
            revenue_subtotal=revenue_subtotal,
            expenses_total=expenses_total,
        )
