from __future__ import annotations

import calendar
from copy import deepcopy
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.branch_scope import branch_scope_for_user
from app.core.datetime_utils import business_today
from app.models.branch_office import BranchOffice
from app.schemas.comparison import (
    ComparisonDailyPoint,
    ComparisonMonthlyPoint,
    ComparisonResponse,
    ComparisonYearlyPoint,
)
from app.schemas.user import UserPublic
from app.services.collection_service import (
    CollectionService,
    apply_manual_breakdown_to_bucket,
    empty_earnings_bucket,
)
from app.services.ticket_service import TicketService, TicketValidationError


class ComparisonValidationError(Exception):
    pass


class ComparisonForbiddenError(Exception):
    pass


def _merge_day_bucket(target: dict[str, dict[str, int]], day_key: str, source: dict[str, int]) -> None:
    if day_key not in target:
        target[day_key] = empty_earnings_bucket()
    bucket = target[day_key]
    bucket["ticket_count"] += source.get("ticket_count", 0)
    bucket["subtotal"] += source.get("subtotal", 0)
    bucket["iva"] += source.get("iva", 0)
    bucket["total"] += source.get("total", 0)


class ComparisonService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._tickets = TicketService(db)
        self._collections = CollectionService(db)

    @staticmethod
    def _require_admin(user: UserPublic) -> None:
        if branch_scope_for_user(user) is not None:
            raise ComparisonForbiddenError()

    def _resolve_branches(
        self,
        branch_office_id: int | None,
    ) -> list[BranchOffice]:
        stmt = (
            select(BranchOffice)
            .where(BranchOffice.deleted_date.is_(None))
            .order_by(BranchOffice.branch_office.asc())
        )
        if branch_office_id is not None and branch_office_id >= 1:
            stmt = stmt.where(BranchOffice.id == branch_office_id)
        branches = list(self.db.scalars(stmt).all())
        if branch_office_id is not None and branch_office_id >= 1 and not branches:
            raise ComparisonValidationError("Branch not found")
        return branches

    def _merged_revenue_buckets(
        self,
        user: UserPublic,
        *,
        branch_office_id: int | None,
    ) -> tuple[dict[str, dict[str, int]], str, str]:
        branches = self._resolve_branches(branch_office_id)
        merged: dict[str, dict[str, int]] = {}

        for branch in branches:
            if branch.id is None:
                continue
            branch_id = int(branch.id)
            try:
                ticket_buckets = self._tickets.ticket_earnings_date_buckets(user, branch_id)
            except TicketValidationError as exc:
                raise ComparisonValidationError(str(exc)) from exc

            manual_by_day = self._collections._manual_breakdown_by_day_key(branch_id)
            day_keys = set(ticket_buckets.keys()) | set(manual_by_day.keys())
            for day_key in day_keys:
                if len(day_key) < 10 or day_key[4] != "-":
                    continue
                try:
                    day = date.fromisoformat(day_key[:10])
                except ValueError:
                    continue
                tickets = self._collections.tickets_bucket_for_date(ticket_buckets, day)
                manual = manual_by_day.get(
                    day.isoformat(),
                    {"cash_amount": 0, "card_gross": 0, "card_tax": 0, "gross_amount": 0},
                )
                combined = deepcopy(tickets)
                apply_manual_breakdown_to_bucket(
                    combined,
                    cash_amount=manual["cash_amount"],
                    card_gross=manual["card_gross"],
                    card_tax=manual["card_tax"],
                )
                if combined["subtotal"] <= 0 and combined["total"] <= 0:
                    continue
                _merge_day_bucket(merged, day.isoformat(), combined)

        if branch_office_id is not None and branch_office_id >= 1 and branches:
            branch = branches[0]
            branch_id_str = str(branch.id)
            branch_name = (branch.branch_office or "").strip() or f"Branch #{branch.id}"
        else:
            branch_id_str = "0"
            branch_name = "Todas las sucursales"

        return merged, branch_id_str, branch_name

    @staticmethod
    def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
        total = year * 12 + (month - 1) + delta
        return total // 12, total % 12 + 1

    @staticmethod
    def _day_point_amounts(
        buckets: dict[str, dict[str, int]],
        *,
        year: int,
        month: int,
        day_num: int,
        today: date,
    ) -> tuple[int | None, int | None]:
        last_day = calendar.monthrange(year, month)[1]
        if day_num < 1 or day_num > last_day:
            return None, None
        day = date(year, month, day_num)
        if day > today:
            return None, None
        bucket = buckets.get(day.isoformat())
        if not bucket:
            return 0, 0
        return int(bucket.get("subtotal", 0)), int(bucket.get("total", 0))

    @staticmethod
    def _month_totals(
        buckets: dict[str, dict[str, int]],
        *,
        year: int,
        month: int,
        today: date,
    ) -> tuple[int, int]:
        last_day = calendar.monthrange(year, month)[1]
        net = 0
        gross = 0
        for day_num in range(1, last_day + 1):
            day = date(year, month, day_num)
            if day > today:
                break
            bucket = buckets.get(day.isoformat())
            if not bucket:
                continue
            net += int(bucket.get("subtotal", 0))
            gross += int(bucket.get("total", 0))
        return net, gross

    @staticmethod
    def _year_totals(
        buckets: dict[str, dict[str, int]],
        *,
        year: int,
        today: date,
    ) -> tuple[int, int]:
        net = 0
        gross = 0
        prefix = f"{year:04d}-"
        for day_key, bucket in buckets.items():
            if not day_key.startswith(prefix):
                continue
            try:
                day = date.fromisoformat(day_key[:10])
            except ValueError:
                continue
            if day > today:
                continue
            net += int(bucket.get("subtotal", 0))
            gross += int(bucket.get("total", 0))
        return net, gross

    def build(
        self,
        user: UserPublic,
        *,
        year: int,
        month: int,
        branch_office_id: int | None = None,
    ) -> ComparisonResponse:
        self._require_admin(user)
        if month < 1 or month > 12:
            raise ComparisonValidationError("Invalid month")
        if year < 2000 or year > 2100:
            raise ComparisonValidationError("Invalid year")

        today = business_today()
        prev_month_year, prev_month = self._shift_month(year, month, -1)
        previous_year = year - 1

        buckets, branch_id_str, branch_name = self._merged_revenue_buckets(
            user,
            branch_office_id=branch_office_id,
        )

        current_last = calendar.monthrange(year, month)[1]
        previous_last = calendar.monthrange(prev_month_year, prev_month)[1]
        axis_days = max(current_last, previous_last)

        daily: list[ComparisonDailyPoint] = []
        for day_num in range(1, axis_days + 1):
            cur_net, cur_gross = self._day_point_amounts(
                buckets,
                year=year,
                month=month,
                day_num=day_num,
                today=today,
            )
            prev_net, prev_gross = self._day_point_amounts(
                buckets,
                year=prev_month_year,
                month=prev_month,
                day_num=day_num,
                today=today,
            )
            daily.append(
                ComparisonDailyPoint(
                    day=day_num,
                    current_net=cur_net,
                    current_gross=cur_gross,
                    previous_net=prev_net,
                    previous_gross=prev_gross,
                ),
            )

        monthly: list[ComparisonMonthlyPoint] = []
        for month_num in range(1, 13):
            cur_net, cur_gross = self._month_totals(
                buckets,
                year=year,
                month=month_num,
                today=today,
            )
            prev_net, prev_gross = self._month_totals(
                buckets,
                year=previous_year,
                month=month_num,
                today=today,
            )
            monthly.append(
                ComparisonMonthlyPoint(
                    month=month_num,
                    current_net=cur_net,
                    current_gross=cur_gross,
                    previous_net=prev_net,
                    previous_gross=prev_gross,
                ),
            )

        years_in_data: set[int] = set()
        for day_key in buckets:
            try:
                years_in_data.add(int(day_key[:4]))
            except ValueError:
                continue
        years_in_data.add(today.year)
        if years_in_data:
            min_year = min(min(years_in_data), today.year - 4)
            max_year = today.year
        else:
            min_year = today.year - 4
            max_year = today.year

        yearly: list[ComparisonYearlyPoint] = []
        for y in range(min_year, max_year + 1):
            net, gross = self._year_totals(buckets, year=y, today=today)
            yearly.append(ComparisonYearlyPoint(year=y, net=net, gross=gross))

        return ComparisonResponse(
            year=year,
            month=month,
            branch_office_id=branch_id_str,
            branch_name=branch_name,
            previous_year=previous_year,
            previous_month=prev_month,
            previous_month_year=prev_month_year,
            daily=daily,
            monthly=monthly,
            yearly=yearly,
        )
