from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pricing import round_pesos
from app.models.branch_office import BranchOffice
from app.models.service import Service
from app.models.ticket import Ticket
from app.models.ticket_branch_office_service import TicketBranchOfficeService
from app.models.user import User
from app.models.washer_pay_settlement import WasherPaySettlement
from app.schemas.user import UserPublic
from app.schemas.washer_pay import (
    WasherPayDetailLine,
    WasherPayDetailResponse,
    WasherPayPaymentStatus,
    WasherPayStatusResponse,
    WasherPaySummaryItem,
    WasherPaySummaryResponse,
)
from app.services.branch_office_washer_service import BranchOfficeWasherService
from app.services.ticket_line_service import TicketLineService
from app.services.ticket_service import TicketService


class WasherPayValidationError(Exception):
    pass


@dataclass
class _LinePayContext:
    line: TicketBranchOfficeService
    ticket: Ticket
    line_total: int
    percentage: Decimal
    commission: int


class WasherPayService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._branch_washer = BranchOfficeWasherService(db)
        self._tickets = TicketService(db)
        self._lines = TicketLineService(db)

    @staticmethod
    def _parse_percentage(value: str | None, *, fallback: Decimal = Decimal("0")) -> Decimal:
        text = (value or "").strip().replace("%", "").replace(",", ".")
        if not text:
            return fallback
        try:
            return Decimal(text)
        except Exception:
            return fallback

    @staticmethod
    def _parse_goal_amount(value: str | None) -> int:
        text = (value or "").strip().replace(".", "").replace(",", "")
        if not text:
            return 0
        try:
            return max(0, int(text))
        except ValueError:
            try:
                return max(0, round_pesos(Decimal(text.replace(",", "."))))
            except Exception:
                return 0

    @staticmethod
    def _parse_date(value: str) -> date:
        text = value.strip()
        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise WasherPayValidationError("Fecha no válida (use AAAA-MM-DD)") from exc

    def _ensure_branch_access(self, user: UserPublic, branch_office_id: int) -> BranchOffice:
        scope = TicketService._branch_scope_for_user(user)
        if scope == 0:
            raise WasherPayValidationError("No tiene permiso para consultar pagos")
        if scope is not None and scope != branch_office_id:
            raise WasherPayValidationError("No puede consultar otra sucursal")
        branch = self.db.get(BranchOffice, branch_office_id)
        if branch is None or not branch.is_active:
            raise WasherPayValidationError("La sucursal no existe")
        return branch

    def _applied_percentage_raw(
        self,
        assignment,
        *,
        day: date,
    ) -> str | None:
        if assignment is None:
            return None
        is_sunday = day.weekday() == 6
        raw = assignment.sunday_percentage if is_sunday else assignment.week_percentage
        text = (raw or "").strip()
        return text or None

    def _percentage_for_date(
        self,
        assignment,
        *,
        day: date,
    ) -> Decimal:
        is_sunday = day.weekday() == 6
        raw = assignment.sunday_percentage if is_sunday else assignment.week_percentage
        return self._parse_percentage(raw)

    def _line_service_label(self, line: TicketBranchOfficeService) -> str:
        additional = (line.additional_service or "").strip()
        if additional:
            return additional
        if line.service_id:
            svc = self.db.get(Service, line.service_id)
            if svc and (svc.service or "").strip():
                return svc.service.strip()
        return "Servicio"

    def _washer_full_name(self, washer_id: int) -> str:
        row = self.db.get(User, washer_id)
        if row is None or not row.is_active:
            return f"Lavador #{washer_id}"
        return row.full_name.strip() or f"Lavador #{washer_id}"

    @staticmethod
    def _status_from_paid(is_paid: bool) -> WasherPayPaymentStatus:
        return "paid" if is_paid else "unpaid"

    def _payment_status_map(
        self,
        *,
        branch_office_id: int,
        day: date,
        washer_ids: list[int],
    ) -> dict[int, WasherPayPaymentStatus]:
        if not washer_ids:
            return {}
        rows = self.db.scalars(
            select(WasherPaySettlement).where(
                WasherPaySettlement.branch_office_id == branch_office_id,
                WasherPaySettlement.pay_date == day,
                WasherPaySettlement.washer_id.in_(washer_ids),
            ),
        ).all()
        paid_by_washer = {row.washer_id: row.is_paid for row in rows}
        return {
            washer_id: self._status_from_paid(paid_by_washer.get(washer_id, False))
            for washer_id in washer_ids
        }

    def _get_payment_status(
        self,
        *,
        branch_office_id: int,
        day: date,
        washer_id: int,
    ) -> WasherPayPaymentStatus:
        row = self.db.scalars(
            select(WasherPaySettlement).where(
                WasherPaySettlement.branch_office_id == branch_office_id,
                WasherPaySettlement.pay_date == day,
                WasherPaySettlement.washer_id == washer_id,
            ).limit(1),
        ).first()
        if row is None:
            return "unpaid"
        return self._status_from_paid(row.is_paid)

    def set_payment_status(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
        date_value: str,
        washer_id: int,
        payment_status: WasherPayPaymentStatus,
    ) -> WasherPayStatusResponse:
        self._ensure_branch_access(user, branch_office_id)
        day = self._parse_date(date_value)
        if washer_id not in self._branch_washer.list_washer_ids_for_branch(branch_office_id):
            raise WasherPayValidationError("El lavador no pertenece a esta sucursal")

        is_paid = payment_status == "paid"
        now = datetime.now()
        row = self.db.scalars(
            select(WasherPaySettlement).where(
                WasherPaySettlement.branch_office_id == branch_office_id,
                WasherPaySettlement.pay_date == day,
                WasherPaySettlement.washer_id == washer_id,
            ).limit(1),
        ).first()
        if row is None:
            self.db.add(
                WasherPaySettlement(
                    branch_office_id=branch_office_id,
                    washer_id=washer_id,
                    pay_date=day,
                    is_paid=is_paid,
                    added_date=now,
                    updated_date=now,
                ),
            )
        else:
            row.is_paid = is_paid
            row.updated_date = now
        self.db.commit()

        return WasherPayStatusResponse(
            washer_id=str(washer_id),
            branch_office_id=str(branch_office_id),
            date=day.isoformat(),
            payment_status=payment_status,
        )

    def _ticket_washer_id(self, ticket_id: int, rows: list[TicketBranchOfficeService]) -> int | None:
        for row in rows:
            if row.washer_id is not None and row.washer_id > 0:
                return row.washer_id
        return self._lines.washer_id_for_ticket(ticket_id)

    @staticmethod
    def _is_payable_service_line(row: TicketBranchOfficeService) -> bool:
        if (row.additional_service or "").strip():
            return True
        if row.service_id is not None and row.service_id >= 0:
            return True
        return False

    def _line_pay_base(
        self,
        row: TicketBranchOfficeService,
        *,
        ticket: Ticket,
        ticket_rows: list[TicketBranchOfficeService],
    ) -> int:
        amount = TicketLineService._resolved_line_total(row)
        if amount > 0:
            return amount
        payable = [r for r in ticket_rows if self._is_payable_service_line(r)]
        if len(payable) != 1 or payable[0].id != row.id:
            return 0
        pricing = self._tickets._ticket_pricing(ticket.id, ticket)
        return max(0, pricing["total"])

    def _paid_lines_for_washer_on_date(
        self,
        *,
        branch_office_id: int,
        washer_id: int,
        day: date,
    ) -> list[_LinePayContext]:
        assignment = self._branch_washer.get_active_assignment_for_washer(washer_id)
        if assignment is None:
            return []

        pct = self._percentage_for_date(assignment, day=day)
        contexts: list[_LinePayContext] = []
        seen: set[tuple[int, int]] = set()

        branch_ticket_ids = self._tickets._ticket_ids_for_branch_subquery(branch_office_id)
        ticket_rows = self.db.scalars(
            select(Ticket)
            .where(
                Ticket.deleted_date.is_(None),
                Ticket.id.in_(branch_ticket_ids),
            )
            .order_by(Ticket.id.asc()),
        ).all()

        for ticket in ticket_rows:
            if ticket.id is None:
                continue
            if not self._tickets.ticket_eligible_for_washer_pay(ticket):
                continue
            if self._tickets.ticket_revenue_day(ticket) != day:
                continue
            if not self._tickets._ticket_matches_branch(ticket.id, branch_office_id):
                continue

            line_rows = self.db.scalars(
                select(TicketBranchOfficeService)
                .where(
                    TicketBranchOfficeService.ticket_id == ticket.id,
                    TicketBranchOfficeService.deleted_date.is_(None),
                )
                .order_by(TicketBranchOfficeService.id.asc()),
            ).all()
            if not line_rows:
                continue

            ticket_washer_id = self._ticket_washer_id(ticket.id, line_rows)
            for line in line_rows:
                if not self._is_payable_service_line(line):
                    continue
                line_washer_id = line.washer_id if line.washer_id and line.washer_id > 0 else ticket_washer_id
                if line_washer_id != washer_id:
                    continue
                line_total = self._line_pay_base(line, ticket=ticket, ticket_rows=line_rows)
                if line_total <= 0:
                    continue
                key = (ticket.id, line.id or 0)
                if key in seen:
                    continue
                seen.add(key)
                commission = round_pesos(Decimal(line_total) * pct / Decimal("100"))
                contexts.append(
                    _LinePayContext(
                        line=line,
                        ticket=ticket,
                        line_total=line_total,
                        percentage=pct,
                        commission=commission,
                    ),
                )

        return contexts

    def _compute_washer_pay(
        self,
        *,
        branch_office_id: int,
        washer_id: int,
        day: date,
    ) -> tuple[int, int, list[WasherPayDetailLine]]:
        assignment = self._branch_washer.get_active_assignment_for_washer(washer_id)
        if assignment is None:
            return 0, 0, []

        line_contexts = self._paid_lines_for_washer_on_date(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            day=day,
        )
        daily_sales = sum(ctx.line_total for ctx in line_contexts)
        ticket_ids = {ctx.ticket.id for ctx in line_contexts if ctx.ticket.id is not None}

        detail_lines: list[WasherPayDetailLine] = []
        for ctx in line_contexts:
            ticket_id = str(ctx.ticket.id) if ctx.ticket.id is not None else None
            plate = (ctx.ticket.license_plate_id or "").strip()
            service_label = self._line_service_label(ctx.line)
            description_parts = [f"T-{ctx.ticket.id}"]
            if plate:
                description_parts.append(plate)
            description_parts.append(service_label)
            pct_display = format(ctx.percentage.normalize()).rstrip("0").rstrip(".")
            detail_lines.append(
                WasherPayDetailLine(
                    kind="ticket",
                    ticket_id=ticket_id,
                    label=service_label,
                    description=" · ".join(description_parts),
                    base_amount=ctx.line_total,
                    percentage=pct_display,
                    amount=ctx.commission,
                ),
            )

        base_total = sum(line.amount for line in detail_lines)
        goal_amount = self._parse_goal_amount(assignment.daily_goal)
        goal_pct = self._parse_percentage(assignment.daily_goal_percentage)
        goal_met = goal_amount > 0 and daily_sales >= goal_amount
        bonus = 0
        if goal_met and goal_pct > 0:
            bonus = round_pesos(Decimal(daily_sales) * goal_pct / Decimal("100"))
            goal_pct_display = format(goal_pct.normalize()).rstrip("0").rstrip(".")
            detail_lines.append(
                WasherPayDetailLine(
                    kind="goal_bonus",
                    ticket_id=None,
                    label="Bono por meta diaria",
                    description=(
                        f"Ventas del día {daily_sales} ≥ meta {goal_amount} "
                        f"({goal_pct_display}% sobre ventas)"
                    ),
                    base_amount=daily_sales,
                    percentage=goal_pct_display,
                    amount=bonus,
                ),
            )

        return base_total + bonus, len(ticket_ids), detail_lines

    def summary_by_branch_and_date(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
        date_value: str,
    ) -> WasherPaySummaryResponse:
        branch = self._ensure_branch_access(user, branch_office_id)
        day = self._parse_date(date_value)

        washer_ids = self._branch_washer.list_washer_ids_for_branch(branch_office_id)
        status_map = self._payment_status_map(
            branch_office_id=branch_office_id,
            day=day,
            washer_ids=washer_ids,
        )
        items: list[WasherPaySummaryItem] = []
        for washer_id in washer_ids:
            amount, ticket_count, _ = self._compute_washer_pay(
                branch_office_id=branch_office_id,
                washer_id=washer_id,
                day=day,
            )
            assignment = self._branch_washer.get_active_assignment_for_washer(washer_id)
            items.append(
                WasherPaySummaryItem(
                    washer_id=str(washer_id),
                    full_name=self._washer_full_name(washer_id),
                    amount=amount,
                    ticket_count=ticket_count,
                    applied_percentage=self._applied_percentage_raw(assignment, day=day),
                    payment_status=status_map.get(washer_id, "unpaid"),
                ),
            )

        items.sort(key=lambda row: row.full_name.lower())
        return WasherPaySummaryResponse(
            branch_office_id=str(branch_office_id),
            branch_name=branch.branch_office,
            date=day.isoformat(),
            items=items,
            amount=sum(row.amount for row in items),
        )

    def detail_for_washer(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
        date_value: str,
        washer_id: int,
    ) -> WasherPayDetailResponse:
        branch = self._ensure_branch_access(user, branch_office_id)
        day = self._parse_date(date_value)
        if washer_id not in self._branch_washer.list_washer_ids_for_branch(branch_office_id):
            raise WasherPayValidationError("El lavador no pertenece a esta sucursal")

        assignment = self._branch_washer.get_active_assignment_for_washer(washer_id)
        amount, _, detail_lines = self._compute_washer_pay(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            day=day,
        )
        ticket_lines = [line for line in detail_lines if line.kind == "ticket"]
        bonus_lines = [line for line in detail_lines if line.kind == "goal_bonus"]
        daily_sales = sum(line.base_amount for line in ticket_lines)
        commission_total = sum(line.amount for line in ticket_lines)
        goal_bonus = sum(line.amount for line in bonus_lines)
        goal_amount = self._parse_goal_amount(
            assignment.daily_goal if assignment else None,
        )
        goal_met = goal_amount > 0 and daily_sales >= goal_amount

        is_sunday = day.weekday() == 6
        applied_raw = (
            assignment.sunday_percentage
            if is_sunday and assignment
            else assignment.week_percentage if assignment else None
        )
        applied_label = (
            "Porcentaje domingo (%)"
            if is_sunday
            else "Porcentaje lun.–sáb. (%)"
        )

        return WasherPayDetailResponse(
            washer_id=str(washer_id),
            full_name=self._washer_full_name(washer_id),
            branch_office_id=str(branch_office_id),
            branch_name=branch.branch_office,
            date=day.isoformat(),
            daily_sales=daily_sales,
            daily_goal=assignment.daily_goal if assignment else None,
            daily_goal_percentage=(
                assignment.daily_goal_percentage if assignment else None
            ),
            week_percentage=assignment.week_percentage if assignment else None,
            sunday_percentage=assignment.sunday_percentage if assignment else None,
            applied_percentage=(applied_raw or "").strip() or None,
            applied_percentage_label=applied_label,
            goal_met=goal_met,
            commission_total=commission_total,
            goal_bonus=goal_bonus,
            items=detail_lines,
            amount=amount,
            payment_status=self._get_payment_status(
                branch_office_id=branch_office_id,
                day=day,
                washer_id=washer_id,
            ),
        )
