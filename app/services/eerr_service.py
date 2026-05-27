from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.branch_scope import branch_scope_for_user
from app.core.datetime_utils import business_today
from app.models.branch_office import BranchOffice
from app.schemas.eerr import EerrAccountLine, EerrDetailItem, EerrMonthResponse
from app.services.collection_service import empty_earnings_bucket
from app.schemas.user import UserPublic
from app.services.collection_service import CollectionService
from app.services.expense_service import ADMIN_ONLY_EXPENSE_TYPES, EXPENSE_TYPE_LABELS, ExpenseService
from app.services.ticket_service import TicketService, TicketValidationError
from app.services.washer_pay_service import WasherPayService, WasherPayValidationError


class EerrValidationError(Exception):
    pass


class EerrForbiddenError(Exception):
    pass


def _merge_date_buckets(
    target: dict[str, dict[str, int]],
    source: dict[str, dict[str, int]],
) -> None:
    for day_key, totals in source.items():
        if day_key not in target:
            target[day_key] = empty_earnings_bucket()
        bucket = target[day_key]
        bucket["ticket_count"] += totals["ticket_count"]
        bucket["subtotal"] += totals["subtotal"]
        bucket["iva"] += totals["iva"]
        bucket["total"] += totals["total"]


def _expense_date_key(expense_date, added_date) -> str | None:
    if expense_date is not None:
        if isinstance(expense_date, date):
            return expense_date.isoformat()
        text = str(expense_date).strip()
        if len(text) >= 10:
            return text[:10]
    if added_date is not None:
        text = str(added_date).strip()
        if len(text) >= 10:
            return text[:10]
    return None


class EerrService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._tickets = TicketService(db)
        self._collections = CollectionService(db)
        self._washer_pay = WasherPayService(db)
        self._expenses = ExpenseService(db)

    @staticmethod
    def _require_admin(user: UserPublic) -> None:
        if branch_scope_for_user(user) is not None:
            raise EerrForbiddenError()

    def _revenue_buckets_all_branches(
        self,
        user: UserPublic,
    ) -> dict[str, dict[str, int]]:
        branches = self.db.scalars(select(BranchOffice).order_by(BranchOffice.id)).all()
        buckets: dict[str, dict[str, int]] = {}

        for branch in branches:
            branch_id = int(branch.id)
            mgmt = int(branch.management_type_id or 1)
            try:
                if mgmt == 1:
                    branch_buckets = self._tickets.ticket_earnings_date_buckets(user, branch_id)
                    _merge_date_buckets(buckets, branch_buckets)
                elif mgmt == 2:
                    branch_buckets: dict[str, dict[str, int]] = {}
                    self._collections.merge_into_date_buckets(branch_buckets, branch_id)
                    _merge_date_buckets(buckets, branch_buckets)
            except TicketValidationError as exc:
                raise EerrValidationError(str(exc)) from exc

        return buckets

    def build_month(
        self,
        user: UserPublic,
        *,
        year: int,
        month: int,
    ) -> EerrMonthResponse:
        self._require_admin(user)
        if month < 1 or month > 12:
            raise EerrValidationError("Mes no válido")
        if year < 2000 or year > 2100:
            raise EerrValidationError("Año no válido")

        month_prefix = f"{year}-{month:02d}"
        today = business_today()
        last_day = calendar.monthrange(year, month)[1]

        buckets = self._revenue_buckets_all_branches(user)

        revenue_subtotal = 0
        revenue_iva = 0
        revenue_total = 0
        revenue_items: list[EerrDetailItem] = []
        for day_key in sorted(buckets.keys()):
            if not day_key.startswith(month_prefix):
                continue
            totals = buckets[day_key]
            if totals["subtotal"] <= 0 and totals["total"] <= 0:
                continue
            revenue_subtotal += totals["subtotal"]
            revenue_iva += totals["iva"]
            revenue_total += totals["total"]
            revenue_items.append(
                EerrDetailItem(
                    id=f"day:{day_key}",
                    date=day_key,
                    description=f"Recaudación {day_key}",
                    amount=totals["subtotal"],
                ),
            )

        branches = self.db.scalars(select(BranchOffice).order_by(BranchOffice.id)).all()
        branch_ids = [int(b.id) for b in branches]

        washer_pay_total = 0
        washer_items: list[EerrDetailItem] = []
        for day_num in range(1, last_day + 1):
            day = date(year, month, day_num)
            if day > today:
                continue
            day_key = day.isoformat()
            day_total = 0
            for branch_id in branch_ids:
                try:
                    summary = self._washer_pay.summary_by_branch_and_date(
                        user,
                        branch_office_id=branch_id,
                        date_value=day_key,
                    )
                except WasherPayValidationError:
                    continue
                day_total += summary.amount
            if day_total <= 0:
                continue
            washer_pay_total += day_total
            washer_items.append(
                EerrDetailItem(
                    id=f"washer:{day_key}",
                    date=day_key,
                    description=f"Pago lavadores {day_key}",
                    amount=day_total,
                ),
            )

        expense_rows = self._expenses.list_for_user(user)
        by_type: dict[str, list] = defaultdict(list)
        for row in expense_rows:
            date_key = _expense_date_key(row.expense_date, row.added_date)
            if date_key is None or not date_key.startswith(month_prefix):
                continue
            by_type[row.expense_type.strip()].append(row)

        accounts: list[EerrAccountLine] = []
        expenses_operational_total = 0
        arriendo_total = 0

        accounts.append(
            EerrAccountLine(
                id="recaudacion",
                kind="income",
                label="Recaudación (ingresos netos)",
                amount=revenue_subtotal,
                items=revenue_items,
            ),
        )

        for type_id, label in EXPENSE_TYPE_LABELS.items():
            rows = by_type.get(type_id, [])
            amount = sum(int(r.amount or 0) for r in rows)
            if amount <= 0:
                continue
            if type_id in ADMIN_ONLY_EXPENSE_TYPES:
                arriendo_total += amount
            else:
                expenses_operational_total += amount
            items = [
                EerrDetailItem(
                    id=str(r.id),
                    date=_expense_date_key(r.expense_date, r.added_date),
                    description=r.expense_type_label or label,
                    amount=int(r.amount or 0),
                )
                for r in rows
            ]
            accounts.append(
                EerrAccountLine(
                    id=type_id,
                    kind="expense",
                    label=label,
                    amount=amount,
                    items=items,
                ),
            )

        if washer_pay_total > 0:
            accounts.append(
                EerrAccountLine(
                    id="washer_pay",
                    kind="cost",
                    label="Pago a lavadores",
                    amount=washer_pay_total,
                    items=washer_items,
                ),
            )

        expenses_total = expenses_operational_total + arriendo_total
        net_profit = revenue_subtotal - washer_pay_total - expenses_operational_total

        return EerrMonthResponse(
            branch_office_id="0",
            branch_name="General",
            year=year,
            month=month,
            revenue_subtotal=revenue_subtotal,
            revenue_iva=revenue_iva,
            revenue_total=revenue_total,
            washer_pay_total=washer_pay_total,
            expenses_operational_total=expenses_operational_total,
            arriendo_total=arriendo_total,
            expenses_total=expenses_total,
            net_profit=net_profit,
            accounts=accounts,
        )
