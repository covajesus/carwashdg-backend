import calendar
from copy import deepcopy
from datetime import date, timedelta

from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.branch_scope import branch_scope_for_user
from app.core.datetime_utils import business_now, business_today
from app.models.branch_collection import BranchCollection
from app.models.branch_office import BranchOffice
from app.schemas.collection import (
    CollectionBranchSummaryItem,
    CollectionBranchesSummaryResponse,
    CollectionCalendarDay,
    CollectionCalendarResponse,
    CollectionDayResponse,
    CollectionUpsert,
)
from app.schemas.user import UserPublic


class CollectionValidationError(Exception):
    pass


class CollectionForbiddenError(Exception):
    pass


def empty_earnings_bucket() -> dict[str, int]:
    return {
        "ticket_count": 0,
        "subtotal": 0,
        "iva": 0,
        "total": 0,
        "cash_total": 0,
        "transbank_gross": 0,
        "cash_plain_net": 0,
        "cash_receipt_gross": 0,
        "cash_receipt_net": 0,
        "cash_receipt_iva": 0,
    }


def apply_manual_gross_to_bucket(bucket: dict[str, int], gross_amount: int) -> None:
    """Legacy: treat entire manual amount as cash without VAT."""
    apply_manual_breakdown_to_bucket(bucket, cash_amount=gross_amount, card_gross=0, card_tax=0)


def apply_manual_breakdown_to_bucket(
    bucket: dict[str, int],
    *,
    cash_amount: int,
    card_gross: int,
    card_tax: int,
) -> None:
    cash = max(0, int(cash_amount))
    card = max(0, int(card_gross))
    tax = max(0, int(card_tax))
    if card <= 0:
        card = 0
        tax = 0
    if tax > card:
        tax = card
    if cash <= 0 and card <= 0:
        return

    if bucket["ticket_count"] == 0:
        bucket["ticket_count"] = 1

    card_net = card - tax
    bucket["subtotal"] += cash + card_net
    bucket["iva"] += tax
    bucket["total"] += cash + card
    bucket["cash_total"] += cash
    bucket["cash_plain_net"] += cash
    bucket["transbank_gross"] += card


def manual_breakdown_from_row(row: BranchCollection) -> dict[str, int]:
    cash = int(getattr(row, "cash_amount", 0) or 0)
    card = int(getattr(row, "card_gross", 0) or 0)
    tax = int(getattr(row, "card_tax", 0) or 0)
    gross = int(row.gross_amount or 0)
    if cash <= 0 and card <= 0 and gross > 0:
        cash = gross
    if card <= 0:
        tax = 0
    return {
        "cash_amount": cash,
        "card_gross": card,
        "card_tax": tax,
        "gross_amount": cash + card,
    }


class CollectionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now():
        return business_now()

    @staticmethod
    def _require_admin(user: UserPublic) -> None:
        if branch_scope_for_user(user) is not None:
            raise CollectionForbiddenError()

    def _assert_branch_access(self, user: UserPublic, branch_office_id: int) -> None:
        scope = branch_scope_for_user(user)
        if scope == 0:
            raise CollectionValidationError("You have no branch assigned")
        if scope is not None and scope != branch_office_id:
            raise CollectionForbiddenError()

    def _validate_branch(self, branch_office_id: int) -> BranchOffice:
        if branch_office_id < 1:
            raise CollectionValidationError("Invalid branch")
        branch = self.db.get(BranchOffice, branch_office_id)
        if branch is None or not branch.is_active:
            raise CollectionValidationError("Branch not found")
        return branch

    def _active_stmt(self):
        return select(BranchCollection).where(BranchCollection.deleted_date.is_(None))

    @staticmethod
    def _day_key(value: date | str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value.isoformat()
        text_value = str(value).strip()
        return text_value[:10] if len(text_value) >= 10 else None

    def _legacy_manual_by_day(
        self,
        branch_office_id: int | None = None,
    ) -> dict[str, int]:
        """Filas en branch_recaudacion (nombre legacy) si aún no migraron la tabla."""
        sql = """
            SELECT collection_date, gross_amount
            FROM branch_recaudacion
            WHERE deleted_date IS NULL AND gross_amount > 0
        """
        params: dict[str, int] = {}
        if branch_office_id is not None:
            sql += " AND branch_office_id = :branch_office_id"
            params["branch_office_id"] = branch_office_id
        try:
            rows = self.db.execute(text(sql), params).all()
        except (ProgrammingError, SQLAlchemyError):
            self.db.rollback()
            return {}

        amounts: dict[str, int] = {}
        for collection_date, gross_amount in rows:
            day_key = self._day_key(collection_date)
            if day_key is None:
                continue
            amounts[day_key] = max(0, int(gross_amount or 0))
        return amounts

    def _manual_breakdown_by_day_key(
        self,
        branch_office_id: int,
    ) -> dict[str, dict[str, int]]:
        by_day: dict[str, dict[str, int]] = {}
        for day_key, gross in self._legacy_manual_by_day(branch_office_id).items():
            amount = max(0, int(gross))
            by_day[day_key] = {
                "cash_amount": amount,
                "card_gross": 0,
                "card_tax": 0,
                "gross_amount": amount,
            }
        for row in self.db.scalars(
            self._active_stmt().where(
                BranchCollection.branch_office_id == branch_office_id,
            ),
        ).all():
            if row.collection_date is None:
                continue
            day_key = self._day_key(row.collection_date)
            if day_key is None:
                continue
            breakdown = manual_breakdown_from_row(row)
            if breakdown["gross_amount"] <= 0:
                continue
            by_day[day_key] = breakdown
        return by_day

    def _manual_gross_by_day_key(self, branch_office_id: int) -> dict[str, int]:
        return {
            day_key: int(row["gross_amount"])
            for day_key, row in self._manual_breakdown_by_day_key(branch_office_id).items()
        }

    def get_manual_breakdown(
        self,
        branch_office_id: int,
        collection_date: date,
    ) -> dict[str, int]:
        day_key = self._day_key(collection_date)
        empty = {"cash_amount": 0, "card_gross": 0, "card_tax": 0, "gross_amount": 0}
        if day_key is None:
            return empty
        return self._manual_breakdown_by_day_key(branch_office_id).get(day_key, empty)

    def get_manual_gross(self, branch_office_id: int, collection_date: date) -> int:
        return int(self.get_manual_breakdown(branch_office_id, collection_date)["gross_amount"])

    def list_manual_for_branch(self, branch_office_id: int) -> list[BranchCollection]:
        rows = list(
            self.db.scalars(
                self._active_stmt().where(
                    BranchCollection.branch_office_id == branch_office_id,
                ),
            ).all(),
        )
        covered = {
            self._day_key(row.collection_date)
            for row in rows
            if row.collection_date is not None
        }
        for day_key, gross in self._legacy_manual_by_day(branch_office_id).items():
            if day_key in covered or gross <= 0:
                continue
            rows.append(
                BranchCollection(
                    branch_office_id=branch_office_id,
                    collection_date=date.fromisoformat(day_key),
                    gross_amount=gross,
                ),
            )
        return rows

    def list_manual_all(self) -> list[BranchCollection]:
        rows = list(self.db.scalars(self._active_stmt()).all())
        covered = {
            (int(row.branch_office_id), self._day_key(row.collection_date))
            for row in rows
            if row.collection_date is not None
        }
        try:
            legacy_rows = self.db.execute(
                text(
                    """
                    SELECT branch_office_id, collection_date, gross_amount
                    FROM branch_recaudacion
                    WHERE deleted_date IS NULL AND gross_amount > 0
                    """,
                ),
            ).all()
        except (ProgrammingError, SQLAlchemyError):
            self.db.rollback()
            return rows

        for branch_id, collection_date, gross_amount in legacy_rows:
            day_key = self._day_key(collection_date)
            if day_key is None:
                continue
            key = (int(branch_id), day_key)
            if key in covered:
                continue
            gross = max(0, int(gross_amount or 0))
            if gross <= 0:
                continue
            rows.append(
                BranchCollection(
                    branch_office_id=int(branch_id),
                    collection_date=date.fromisoformat(day_key),
                    gross_amount=gross,
                ),
            )
        return rows

    def merge_into_date_buckets(
        self,
        buckets: dict[str, dict[str, int]],
        branch_office_id: int,
        *,
        revenue_day: date | None = None,
    ) -> None:
        for row in self.list_manual_for_branch(branch_office_id):
            if row.collection_date is None:
                continue
            breakdown = manual_breakdown_from_row(row)
            if breakdown["gross_amount"] <= 0:
                continue
            if revenue_day is not None and row.collection_date != revenue_day:
                continue
            day_key = row.collection_date.isoformat()
            if day_key not in buckets:
                buckets[day_key] = empty_earnings_bucket()
            apply_manual_breakdown_to_bucket(
                buckets[day_key],
                cash_amount=breakdown["cash_amount"],
                card_gross=breakdown["card_gross"],
                card_tax=breakdown["card_tax"],
            )

    def merge_into_branch_buckets(
        self,
        buckets: dict[int, dict[str, int]],
        *,
        branch_office_id: int | None = None,
    ) -> None:
        for row in self.list_manual_all():
            breakdown = manual_breakdown_from_row(row)
            if breakdown["gross_amount"] <= 0:
                continue
            key = int(row.branch_office_id)
            if branch_office_id is not None and key != branch_office_id:
                continue
            if key not in buckets:
                buckets[key] = empty_earnings_bucket()
            apply_manual_breakdown_to_bucket(
                buckets[key],
                cash_amount=breakdown["cash_amount"],
                card_gross=breakdown["card_gross"],
                card_tax=breakdown["card_tax"],
            )

    def upsert(
        self,
        user: UserPublic,
        branch_office_id: int,
        collection_date: date,
        data: CollectionUpsert,
    ) -> None:
        self._require_admin(user)
        self._validate_branch(branch_office_id)
        self._assert_branch_access(user, branch_office_id)

        cash = int(data.cash_amount or 0)
        card = int(data.card_gross or 0)
        card_tax = int(data.card_tax or 0)
        if card <= 0:
            card = 0
            card_tax = 0
        gross = cash + card
        now = self._now()
        row = self.db.scalars(
            select(BranchCollection).where(
                BranchCollection.branch_office_id == branch_office_id,
                BranchCollection.collection_date == collection_date,
            ),
        ).first()

        if gross <= 0:
            if row is not None and row.deleted_date is None:
                row.deleted_date = now
                row.updated_date = now
                self.db.commit()
        elif row is None:
            self.db.add(
                BranchCollection(
                    branch_office_id=branch_office_id,
                    collection_date=collection_date,
                    gross_amount=gross,
                    cash_amount=cash,
                    card_gross=card,
                    card_tax=card_tax,
                    added_date=now,
                    updated_date=now,
                    deleted_date=None,
                ),
            )
            self.db.commit()
        else:
            row.gross_amount = gross
            row.cash_amount = cash
            row.card_gross = card
            row.card_tax = card_tax
            row.updated_date = now
            row.deleted_date = None
            self.db.commit()

    def build_day_response(
        self,
        user: UserPublic,
        branch_office_id: int,
        collection_date: date,
        *,
        branch_name: str | None = None,
        tickets_bucket: dict[str, int] | None = None,
    ) -> CollectionDayResponse:
        self._require_admin(user)
        self._assert_branch_access(user, branch_office_id)
        if branch_name is None:
            branch = self._validate_branch(branch_office_id)
            branch_name = branch.branch_office

        tickets = deepcopy(tickets_bucket or empty_earnings_bucket())
        manual = self.get_manual_breakdown(branch_office_id, collection_date)
        combined = deepcopy(tickets)
        apply_manual_breakdown_to_bucket(
            combined,
            cash_amount=manual["cash_amount"],
            card_gross=manual["card_gross"],
            card_tax=manual["card_tax"],
        )

        return CollectionDayResponse(
            branch_office_id=str(branch_office_id),
            branch_name=branch_name,
            collection_date=collection_date,
            manual_gross_amount=manual["gross_amount"],
            manual_cash_amount=manual["cash_amount"],
            manual_card_gross=manual["card_gross"],
            manual_card_tax=manual["card_tax"],
            tickets_ticket_count=tickets["ticket_count"],
            tickets_subtotal=tickets["subtotal"],
            tickets_iva=tickets["iva"],
            tickets_total=tickets["total"],
            ticket_count=combined["ticket_count"],
            subtotal=combined["subtotal"],
            iva=combined["iva"],
            total=combined["total"],
        )

    @staticmethod
    def tickets_bucket_for_date(
        date_buckets: dict[str, dict[str, int]],
        collection_date: date,
    ) -> dict[str, int]:
        return deepcopy(date_buckets.get(collection_date.isoformat(), empty_earnings_bucket()))

    @staticmethod
    def day_is_recorded(tickets: dict[str, int], manual_gross: int) -> bool:
        combined = deepcopy(tickets)
        apply_manual_gross_to_bucket(combined, manual_gross)
        return combined["ticket_count"] > 0 or combined["total"] > 0

    def build_calendar_month(
        self,
        user: UserPublic,
        branch_office_id: int,
        *,
        year: int,
        month: int,
        tickets_date_buckets: dict[str, dict[str, int]],
    ) -> CollectionCalendarResponse:
        self._require_admin(user)
        if month < 1 or month > 12:
            raise CollectionValidationError("Mes no válido")
        if year < 2000 or year > 2100:
            raise CollectionValidationError("Año no válido")

        branch = self._validate_branch(branch_office_id)
        self._assert_branch_access(user, branch_office_id)

        last_day = calendar.monthrange(year, month)[1]
        today = business_today()

        manual_by_day = self._manual_breakdown_by_day_key(branch_office_id)

        days: list[CollectionCalendarDay] = []
        for day_num in range(1, last_day + 1):
            day = date(year, month, day_num)
            day_key = day.isoformat()
            tickets = self.tickets_bucket_for_date(tickets_date_buckets, day)
            manual = manual_by_day.get(
                day_key,
                {"cash_amount": 0, "card_gross": 0, "card_tax": 0, "gross_amount": 0},
            )
            combined = deepcopy(tickets)
            apply_manual_breakdown_to_bucket(
                combined,
                cash_amount=manual["cash_amount"],
                card_gross=manual["card_gross"],
                card_tax=manual["card_tax"],
            )
            manual_gross = int(manual["gross_amount"])

            if day > today:
                status = "future"
            elif self.day_is_recorded(tickets, manual_gross):
                status = "ok"
            else:
                status = "missing"

            days.append(
                CollectionCalendarDay(
                    date=day,
                    status=status,
                    has_tickets=tickets["ticket_count"] > 0,
                    has_manual=manual_gross > 0,
                    tickets_total=tickets["total"],
                    manual_gross_amount=manual_gross,
                    total=combined["total"],
                ),
            )

        return CollectionCalendarResponse(
            branch_office_id=str(branch_office_id),
            branch_name=branch.branch_office,
            year=year,
            month=month,
            days=days,
        )

    def build_branches_summary(
        self,
        user: UserPublic,
        ticket_service,
        *,
        date_from: date,
        date_to: date,
    ) -> CollectionBranchesSummaryResponse:
        if date_to < date_from:
            raise CollectionValidationError("La fecha final no puede ser anterior a la inicial")

        scope = branch_scope_for_user(user)
        if scope == 0:
            return CollectionBranchesSummaryResponse(
                date_from=date_from,
                date_to=date_to,
                items=[],
                subtotal=0,
                iva=0,
                total=0,
                ticket_count=0,
            )

        if scope is not None:
            branch_rows = [self.db.get(BranchOffice, scope)]
            if branch_rows[0] is None or not branch_rows[0].is_active:
                raise CollectionValidationError("La sucursal no existe")
        else:
            branch_rows = list(
                self.db.scalars(
                    select(BranchOffice)
                    .where(BranchOffice.deleted_date.is_(None))
                    .order_by(BranchOffice.branch_office.asc()),
                ).all(),
            )

        items: list[CollectionBranchSummaryItem] = []
        today = business_today()
        for branch in branch_rows:
            if branch.id is None:
                continue
            branch_id = int(branch.id)
            try:
                buckets = ticket_service.ticket_earnings_date_buckets(user, branch_id)
            except Exception:
                continue
            manual_by_day = self._manual_breakdown_by_day_key(branch_id)

            subtotal = 0
            iva = 0
            total = 0
            ticket_count = 0
            missing_dates: list[date] = []
            current = date_from
            while current <= date_to:
                day_key = current.isoformat()
                tickets = self.tickets_bucket_for_date(buckets, current)
                manual = manual_by_day.get(
                    day_key,
                    {"cash_amount": 0, "card_gross": 0, "card_tax": 0, "gross_amount": 0},
                )
                combined = deepcopy(tickets)
                apply_manual_breakdown_to_bucket(
                    combined,
                    cash_amount=manual["cash_amount"],
                    card_gross=manual["card_gross"],
                    card_tax=manual["card_tax"],
                )
                subtotal += combined["subtotal"]
                iva += combined["iva"]
                total += combined["total"]
                ticket_count += combined["ticket_count"]
                if current <= today and not self.day_is_recorded(
                    tickets, int(manual["gross_amount"])
                ):
                    missing_dates.append(current)
                current += timedelta(days=1)

            items.append(
                CollectionBranchSummaryItem(
                    branch_office_id=str(branch_id),
                    branch_name=branch.branch_office.strip() or f"Sucursal #{branch_id}",
                    ticket_count=ticket_count,
                    subtotal=subtotal,
                    iva=iva,
                    total=total,
                    has_collection=ticket_count > 0 or total > 0,
                    missing_day_count=len(missing_dates),
                    missing_dates=missing_dates,
                ),
            )

        return CollectionBranchesSummaryResponse(
            date_from=date_from,
            date_to=date_to,
            items=items,
            subtotal=sum(row.subtotal for row in items),
            iva=sum(row.iva for row in items),
            total=sum(row.total for row in items),
            ticket_count=sum(row.ticket_count for row in items),
            missing_day_count=sum(row.missing_day_count for row in items),
        )
