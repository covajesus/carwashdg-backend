from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.core.datetime_utils import business_now
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pricing import TICKET_IVA_GROSS_FACTOR, round_money
from app.models.branch_office import BranchOffice
from app.models.service import Service
from app.models.ticket import Ticket
from app.models.ticket_branch_office_service import TicketBranchOfficeService
from app.models.user import User
from app.models.washer_daily_group import WasherDailyGroup
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
from app.services.washer_daily_group_service import WasherDailyGroupService


@dataclass
class _WasherPayLineContext:
    line: TicketBranchOfficeService
    ticket: Ticket
    attributed_net: int
    full_line_net: int
    group_id: int | None
    group_member_count: int
    group_name: str | None


class WasherPayValidationError(Exception):
    pass


class WasherPayService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._branch_washer = BranchOfficeWasherService(db)
        self._tickets = TicketService(db)
        self._lines = TicketLineService(db)
        self._washer_groups = WasherDailyGroupService(db)

    @staticmethod
    def _format_percentage_display(value: Decimal) -> str:
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text

    @staticmethod
    def _goal_percentage_boost_applies_on_day(day: date) -> bool:
        """Goal % boost stacks on the day rate: Monday–Saturday only (not Sunday)."""
        return day.weekday() != 6

    def _goal_percentage_boost(
        self,
        assignment,
        *,
        day: date,
        daily_sales: int,
    ) -> Decimal:
        goal_amount = self._parse_goal_amount(assignment.daily_goal if assignment else None)
        goal_pct = self._parse_percentage(
            assignment.daily_goal_percentage if assignment else None,
        )
        goal_met = goal_amount > 0 and daily_sales >= goal_amount
        if (
            self._goal_percentage_boost_applies_on_day(day)
            and goal_met
            and goal_pct > 0
        ):
            return goal_pct
        return Decimal("0")

    def _effective_percentage(
        self,
        assignment,
        *,
        day: date,
        daily_sales: int,
    ) -> Decimal:
        base = self._percentage_for_date(assignment, day=day)
        return base + self._goal_percentage_boost(
            assignment,
            day=day,
            daily_sales=daily_sales,
        )

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
                return max(0, round_money(Decimal(text.replace(",", "."))))
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
        now = business_now()
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

    @staticmethod
    def _line_attributed_washer_id(
        line: TicketBranchOfficeService,
        line_rows: list[TicketBranchOfficeService],
    ) -> int | None:
        """Washer credited for this line's net sales (not every line on the ticket)."""
        if line.washer_id is not None and line.washer_id > 0:
            return line.washer_id
        unique = {
            row.washer_id
            for row in line_rows
            if row.washer_id is not None and row.washer_id > 0
        }
        if len(unique) == 1:
            return next(iter(unique))
        return None

    @staticmethod
    def _is_payable_service_line(row: TicketBranchOfficeService) -> bool:
        if (row.additional_service or "").strip():
            return True
        if row.service_id is not None and row.service_id >= 0:
            return True
        return False

    def _payable_service_lines(
        self,
        ticket_rows: list[TicketBranchOfficeService],
    ) -> list[TicketBranchOfficeService]:
        return [row for row in ticket_rows if self._is_payable_service_line(row)]

    def _line_gross_amounts_for_ticket(
        self,
        ticket: Ticket,
        ticket_rows: list[TicketBranchOfficeService],
    ) -> dict[int, int]:
        """Gross per service line; avoids counting the full ticket on every line."""
        payable = self._payable_service_lines(ticket_rows)
        if not payable or ticket.id is None:
            return {}

        pricing = self._tickets._ticket_pricing(ticket.id, ticket)
        ticket_subtotal = max(0, pricing["subtotal"])
        ticket_total = max(0, pricing["total"])

        if len(payable) == 1:
            row = payable[0]
            line_id = row.id or 0
            gross = max(0, TicketLineService._resolved_line_total(row))
            if gross <= 0:
                gross = ticket_total
            return {line_id: gross}

        raw: dict[int, int] = {}
        for row in payable:
            raw[row.id or 0] = max(0, TicketLineService._resolved_line_total(row))

        total_raw = sum(raw.values())
        if total_raw <= 0:
            share = round_money(Decimal(ticket_subtotal) / Decimal(len(payable)))
            return {row.id or 0: share for row in payable}

        if total_raw > ticket_subtotal:
            share = round_money(Decimal(ticket_subtotal) / Decimal(len(payable)))
            return {row.id or 0: share for row in payable}

        return raw

    def _gross_to_net(self, gross: int, *, ticket: Ticket) -> int:
        """Net line amount (subtotal, sin IVA) for washer commission."""
        if gross <= 0 or ticket.id is None:
            return 0
        pricing = self._tickets._ticket_pricing(ticket.id, ticket)
        ticket_subtotal = pricing["subtotal"]
        ticket_total = pricing["total"]
        if ticket_subtotal <= 0:
            return 0
        if ticket_total <= 0:
            if pricing["iva"] > 0:
                return round_money(Decimal(gross) / TICKET_IVA_GROSS_FACTOR)
            return gross
        return round_money(Decimal(gross) * Decimal(ticket_subtotal) / Decimal(ticket_total))

    def _group_name(self, group_id: int) -> str:
        row = self.db.get(WasherDailyGroup, group_id)
        if row is None or not row.is_active:
            return f"Grupo #{group_id}"
        return row.name.strip() or f"Grupo #{group_id}"

    def _group_member_ids_for_pay_day(self, group_id: int, *, day: date) -> list[int]:
        return self._washer_groups.member_ids_for_group_on_date(group_id, day=day)

    def _iter_branch_payable_lines(
        self,
        *,
        branch_office_id: int,
        day: date,
    ):
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

            gross_by_line = self._line_gross_amounts_for_ticket(ticket, line_rows)
            for line in line_rows:
                if not self._is_payable_service_line(line):
                    continue
                gross = gross_by_line.get(line.id or 0, 0)
                if gross <= 0:
                    continue
                line_net = self._gross_to_net(gross, ticket=ticket)
                if line_net <= 0:
                    continue
                yield line, ticket, line_rows, line_net

    def _branch_washer_attributed_sales(
        self,
        *,
        branch_office_id: int,
        day: date,
    ) -> dict[int, int]:
        sales: dict[int, int] = defaultdict(int)
        for line, ticket, line_rows, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            del ticket
            group_id = line.washer_daily_group_id
            if group_id is not None and group_id > 0:
                member_ids = self._group_member_ids_for_pay_day(group_id, day=day)
                if member_ids:
                    base_avg = self._group_base_average_pct(member_ids, day=day)
                    credit = self._line_sales_credit(line_net, base_avg)
                    for member_id in member_ids:
                        sales[member_id] += credit
                    continue
            line_washer_id = self._line_attributed_washer_id(line, line_rows)
            if line_washer_id is not None:
                assignment = self._branch_washer.get_active_assignment_for_washer(line_washer_id)
                if assignment is not None:
                    pct = self._percentage_for_date(assignment, day=day)
                    sales[line_washer_id] += self._line_sales_credit(line_net, pct)
        return dict(sales)

    @staticmethod
    def _line_sales_credit(line_net: int, pct: Decimal) -> int:
        """Venta del día por línea: monto neto × % (del día o promedio del grupo)."""
        if line_net <= 0 or pct <= 0:
            return 0
        return round_money(Decimal(line_net) * pct / Decimal("100"))

    def _group_base_average_pct(self, member_ids: list[int], *, day: date) -> Decimal:
        """Promedio del % base (lun–sáb. / domingo) sin extra por meta."""
        if not member_ids:
            return Decimal("0")
        total = Decimal("0")
        count = 0
        for member_id in member_ids:
            assignment = self._branch_washer.get_active_assignment_for_washer(member_id)
            if assignment is None:
                continue
            total += self._percentage_for_date(assignment, day=day)
            count += 1
        if count == 0:
            return Decimal("0")
        return total / Decimal(count)

    def _group_average_effective_pct(
        self,
        *,
        member_ids: list[int],
        day: date,
        sales_map: dict[int, int],
    ) -> Decimal:
        if not member_ids:
            return Decimal("0")
        total = Decimal("0")
        for member_id in member_ids:
            assignment = self._branch_washer.get_active_assignment_for_washer(member_id)
            if assignment is None:
                continue
            daily_sales = sales_map.get(member_id, 0)
            total += self._effective_percentage(
                assignment,
                day=day,
                daily_sales=daily_sales,
            )
        return total / Decimal(len(member_ids))

    def _paid_line_contexts_for_washer(
        self,
        *,
        branch_office_id: int,
        washer_id: int,
        day: date,
    ) -> list[_WasherPayLineContext]:
        assignment = self._branch_washer.get_active_assignment_for_washer(washer_id)
        if assignment is None:
            return []

        contexts: list[_WasherPayLineContext] = []
        seen: set[tuple[int, int]] = set()

        for line, ticket, line_rows, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            group_id = line.washer_daily_group_id
            if group_id is not None and group_id > 0:
                member_ids = self._group_member_ids_for_pay_day(group_id, day=day)
                if member_ids:
                    if washer_id not in member_ids:
                        continue
                    member_count = len(member_ids)
                    key = (ticket.id or 0, line.id or 0)
                    if key in seen:
                        continue
                    seen.add(key)
                    attributed_net = round_money(Decimal(line_net) / Decimal(member_count))
                    contexts.append(
                        _WasherPayLineContext(
                            line=line,
                            ticket=ticket,
                            attributed_net=attributed_net,
                            full_line_net=line_net,
                            group_id=group_id,
                            group_member_count=member_count,
                            group_name=self._group_name(group_id),
                        ),
                    )
                    continue

            line_washer_id = self._line_attributed_washer_id(line, line_rows)
            if line_washer_id != washer_id:
                continue
            key = (ticket.id or 0, line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            contexts.append(
                _WasherPayLineContext(
                    line=line,
                    ticket=ticket,
                    attributed_net=line_net,
                    full_line_net=line_net,
                    group_id=None,
                    group_member_count=1,
                    group_name=None,
                ),
            )

        return contexts

    def _paid_lines_for_washer_on_date(
        self,
        *,
        branch_office_id: int,
        washer_id: int,
        day: date,
    ) -> list[tuple[TicketBranchOfficeService, Ticket, int]]:
        return [
            (ctx.line, ctx.ticket, ctx.attributed_net)
            for ctx in self._paid_line_contexts_for_washer(
                branch_office_id=branch_office_id,
                washer_id=washer_id,
                day=day,
            )
        ]

    def _compute_washer_pay(
        self,
        *,
        branch_office_id: int,
        washer_id: int,
        day: date,
    ) -> tuple[int, int, list[WasherPayDetailLine], int]:
        assignment = self._branch_washer.get_active_assignment_for_washer(washer_id)
        if assignment is None:
            return 0, 0, [], 0

        line_contexts = self._paid_line_contexts_for_washer(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            day=day,
        )
        sales_map = self._branch_washer_attributed_sales(
            branch_office_id=branch_office_id,
            day=day,
        )
        ticket_ids = {ctx.ticket.id for ctx in line_contexts if ctx.ticket.id is not None}

        base_pct = self._percentage_for_date(assignment, day=day)
        prelim_daily_sales = 0
        for ctx in line_contexts:
            if ctx.group_id is not None:
                member_ids = self._group_member_ids_for_pay_day(ctx.group_id, day=day)
                base_avg = self._group_base_average_pct(member_ids, day=day)
                prelim_daily_sales += self._line_sales_credit(ctx.full_line_net, base_avg)
            else:
                prelim_daily_sales += self._line_sales_credit(ctx.full_line_net, base_pct)

        boost_pct = self._goal_percentage_boost(
            assignment,
            day=day,
            daily_sales=prelim_daily_sales,
        )
        effective_pct = base_pct + boost_pct
        effective_pct_display = self._format_percentage_display(effective_pct)

        detail_lines: list[WasherPayDetailLine] = []
        daily_sales = 0
        for ctx in line_contexts:
            ticket_id = str(ctx.ticket.id) if ctx.ticket.id is not None else None
            plate = (ctx.ticket.license_plate_id or "").strip()
            service_label = self._line_service_label(ctx.line)
            description_parts = [f"T-{ctx.ticket.id}"]
            if plate:
                description_parts.append(plate)
            description_parts.append(service_label)
            if ctx.group_id is not None:
                member_ids = self._group_member_ids_for_pay_day(ctx.group_id, day=day)
                avg_pct = self._group_average_effective_pct(
                    member_ids=member_ids,
                    day=day,
                    sales_map=sales_map,
                )
                pct_display = self._format_percentage_display(avg_pct)
                sales_credit = self._line_sales_credit(ctx.full_line_net, avg_pct)
                commission = round_money(
                    Decimal(sales_credit) / Decimal(ctx.group_member_count),
                )
                daily_sales += sales_credit
                description_parts.append(
                    f"Grupo {ctx.group_name} ({ctx.group_member_count} lav.)",
                )
                detail_lines.append(
                    WasherPayDetailLine(
                        kind="ticket",
                        ticket_id=ticket_id,
                        label=service_label,
                        description=" · ".join(description_parts),
                        base_amount=sales_credit,
                        line_gross_net=ctx.full_line_net,
                        group_member_count=ctx.group_member_count,
                        percentage=pct_display,
                        percentage_scope="group_average",
                        percentage_label="% promedio del grupo",
                        day_percentage=effective_pct_display or None,
                        amount=commission,
                    ),
                )
                continue

            sales_credit = self._line_sales_credit(ctx.full_line_net, effective_pct)
            daily_sales += sales_credit
            detail_lines.append(
                WasherPayDetailLine(
                    kind="ticket",
                    ticket_id=ticket_id,
                    label=service_label,
                    description=" · ".join(description_parts),
                    base_amount=sales_credit,
                    line_gross_net=ctx.full_line_net,
                    group_member_count=None,
                    percentage=effective_pct_display,
                    percentage_scope="day",
                    percentage_label="% del día",
                    day_percentage=None,
                    amount=sales_credit,
                ),
            )

        total = sum(line.amount for line in detail_lines)
        return total, len(ticket_ids), detail_lines, daily_sales

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
            amount, ticket_count, _, daily_sales = self._compute_washer_pay(
                branch_office_id=branch_office_id,
                washer_id=washer_id,
                day=day,
            )
            if ticket_count <= 0 and amount <= 0:
                continue
            assignment = self._branch_washer.get_active_assignment_for_washer(washer_id)
            applied_pct = (
                self._format_percentage_display(
                    self._effective_percentage(
                        assignment,
                        day=day,
                        daily_sales=daily_sales,
                    ),
                )
                if assignment is not None
                else None
            )
            items.append(
                WasherPaySummaryItem(
                    washer_id=str(washer_id),
                    full_name=self._washer_full_name(washer_id),
                    amount=amount,
                    ticket_count=ticket_count,
                    applied_percentage=applied_pct,
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
        amount, _, detail_lines, daily_sales = self._compute_washer_pay(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            day=day,
        )
        ticket_lines = [line for line in detail_lines if line.kind == "ticket"]
        line_contexts = self._paid_line_contexts_for_washer(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            day=day,
        )
        goal_amount = self._parse_goal_amount(
            assignment.daily_goal if assignment else None,
        )
        goal_met = goal_amount > 0 and daily_sales >= goal_amount

        is_sunday = day.weekday() == 6
        base_pct = self._percentage_for_date(assignment, day=day) if assignment else Decimal("0")
        boost_pct = self._goal_percentage_boost(
            assignment,
            day=day,
            daily_sales=daily_sales,
        )
        effective_pct = base_pct + boost_pct
        base_commission = 0
        for ctx in line_contexts:
            if ctx.group_id is not None:
                member_ids = self._group_member_ids_for_pay_day(ctx.group_id, day=day)
                base_avg = self._group_base_average_pct(member_ids, day=day)
                pool = self._line_sales_credit(ctx.full_line_net, base_avg)
                base_commission += round_money(
                    Decimal(pool) / Decimal(ctx.group_member_count),
                )
            else:
                base_commission += self._line_sales_credit(ctx.full_line_net, base_pct)
        goal_bonus = max(0, amount - base_commission)
        commission_total = base_commission

        applied_label = (
            "Porcentaje domingo (%)"
            if is_sunday
            else "Porcentaje aplicado hoy"
        )
        applied_raw = self._format_percentage_display(effective_pct)
        if boost_pct > 0 and not is_sunday:
            applied_label = "Porcentaje aplicado hoy (base + meta)"

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
            applied_percentage=applied_raw or None,
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
