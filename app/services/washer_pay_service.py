from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.core.datetime_utils import business_now, business_today
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.pricing import (
    TICKET_IVA_GROSS_FACTOR,
    round_coins_to_nearest_thousand,
    round_money,
    split_mixed_payment_totals,
)
from app.models.branch_office import BranchOffice
from app.models.configuration import Configuration
from app.models.service import Service
from app.models.ticket import Ticket
from app.models.ticket_branch_office_service import TicketBranchOfficeService
from app.models.user import User
from app.models.washer_daily_group import WasherDailyGroup
from app.models.washer_pay_settlement import WasherPaySettlement
from app.schemas.user import UserPublic
from app.schemas.washer_pay import (
    WasherPayBreakdownRow,
    WasherPayDetailLine,
    WasherPayDetailResponse,
    WasherPayGroupMemberItem,
    WasherPayManualGoalMetResponse,
    WasherPayManualGoalMetUpdate,
    WasherPayMonthDayItem,
    WasherPayMonthResponse,
    WasherPayMonthWorkerItem,
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
    full_line_gross: int
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
        self._payable_line_entries_cache: dict[
            tuple[int, date],
            list[tuple[
                TicketBranchOfficeService,
                Ticket,
                list[TicketBranchOfficeService],
                int,
                int,
            ]],
        ] = {}
        self._assignment_cache: dict[int, object | None] = {}
        self._branch_washer_ids_cache: dict[int, list[int]] = {}

    def _assignment_for_washer(self, washer_id: int):
        """Cached branch assignment lookup (read-only reporting path)."""
        if washer_id in self._assignment_cache:
            return self._assignment_cache[washer_id]
        assignment = self._branch_washer.get_active_assignment_for_washer(washer_id)
        self._assignment_cache[washer_id] = assignment
        return assignment

    def _branch_washer_ids(self, branch_office_id: int) -> list[int]:
        cached = self._branch_washer_ids_cache.get(branch_office_id)
        if cached is None:
            cached = self._branch_washer.list_washer_ids_for_branch(branch_office_id)
            self._branch_washer_ids_cache[branch_office_id] = cached
        return cached

    def _coin_round_enabled(self) -> bool:
        row = self.db.get(Configuration, 1)
        if row is None:
            row = self.db.scalars(select(Configuration).limit(1)).first()
        if row is None:
            return False
        return int(row.coin_round_status_id or 0) == 1

    def _apply_coin_round(self, amount: int) -> int:
        if not self._coin_round_enabled():
            return amount
        return round_coins_to_nearest_thousand(amount)

    @staticmethod
    def _format_percentage_display(value: Decimal) -> str:
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        if not text:
            return "0%"
        return f"{text}%"

    @staticmethod
    def _goal_percentage_boost_applies_on_day(day: date) -> bool:
        """Goal % boost stacks on the day rate: Monday–Saturday only (not Sunday)."""
        return day.weekday() != 6

    def _goal_percentage_boost(
        self,
        assignment,
        *,
        day: date,
        goal_met: bool,
    ) -> Decimal:
        goal_pct = self._parse_percentage(
            assignment.daily_goal_percentage if assignment else None,
        )
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
        goal_met: bool,
    ) -> Decimal:
        base = self._percentage_for_date(assignment, day=day)
        return base + self._goal_percentage_boost(
            assignment,
            day=day,
            goal_met=goal_met,
        )

    def _member_goal_amount(self, assignment) -> int:
        return self._parse_goal_amount(assignment.daily_goal if assignment else None)

    def _combined_group_goal_amount(self, member_ids: list[int]) -> int:
        total = 0
        for member_id in member_ids:
            assignment = self._assignment_for_washer(member_id)
            if assignment is not None:
                total += self._member_goal_amount(assignment)
        return total

    @staticmethod
    def _is_goal_met(*, sales_volume: int, goal_amount: int) -> bool:
        return goal_amount > 0 and sales_volume >= goal_amount

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

    def _service_washer_percentage(self, line: TicketBranchOfficeService) -> Decimal:
        """Configured service override %; 0 means fall back to washer/group day %."""
        if not line.service_id:
            return Decimal("0")
        svc = self.db.get(Service, line.service_id)
        if svc is None:
            return Decimal("0")
        return self._parse_percentage(svc.washer_percentage)

    def _commission_percentage_for_line(
        self,
        line: TicketBranchOfficeService,
        *,
        day: date,
        goal_met: bool,
        assignment=None,
        group_member_ids: list[int] | None = None,
    ) -> tuple[Decimal, str, str]:
        """
        Resolve commission % for a ticket line.

        If the service has washer_percentage > 0, that value wins (no goal boost).
        Otherwise use the washer day/Sunday % (+ goal boost) or group average.
        """
        service_pct = self._service_washer_percentage(line)
        if service_pct > 0:
            return service_pct, "service", "% del servicio"
        if group_member_ids is not None:
            avg = self._group_average_effective_pct(
                member_ids=group_member_ids,
                day=day,
                goal_met=goal_met,
            )
            return avg, "group_average", "% promedio del grupo"
        if assignment is None:
            return Decimal("0"), "day", "% del día"
        pct = self._effective_percentage(assignment, day=day, goal_met=goal_met)
        return pct, "day", "% del día"

    def _base_commission_percentage_for_line(
        self,
        line: TicketBranchOfficeService,
        *,
        day: date,
        assignment=None,
        group_member_ids: list[int] | None = None,
    ) -> Decimal:
        """Base % without goal boost; service override still applies when set."""
        service_pct = self._service_washer_percentage(line)
        if service_pct > 0:
            return service_pct
        if group_member_ids is not None:
            return self._group_base_average_pct(group_member_ids, day=day)
        if assignment is None:
            return Decimal("0")
        return self._percentage_for_date(assignment, day=day)

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

    def _manual_goal_met_map(
        self,
        *,
        branch_office_id: int,
        day: date,
        washer_ids: list[int],
    ) -> dict[int, bool]:
        if not washer_ids:
            return {}
        rows = self.db.scalars(
            select(WasherPaySettlement).where(
                WasherPaySettlement.branch_office_id == branch_office_id,
                WasherPaySettlement.pay_date == day,
                WasherPaySettlement.washer_id.in_(washer_ids),
            ),
        ).all()
        return {
            washer_id: False
            for washer_id in washer_ids
        } | {
            row.washer_id: bool(row.manual_goal_met)
            for row in rows
            if row.manual_goal_met
        }

    def _get_manual_goal_met(
        self,
        *,
        branch_office_id: int,
        day: date,
        washer_id: int,
    ) -> bool:
        row = self.db.scalars(
            select(WasherPaySettlement).where(
                WasherPaySettlement.branch_office_id == branch_office_id,
                WasherPaySettlement.pay_date == day,
                WasherPaySettlement.washer_id == washer_id,
            ).limit(1),
        ).first()
        return bool(row and row.manual_goal_met)

    def _upsert_settlement_row(
        self,
        *,
        branch_office_id: int,
        day: date,
        washer_id: int,
    ) -> WasherPaySettlement:
        row = self.db.scalars(
            select(WasherPaySettlement).where(
                WasherPaySettlement.branch_office_id == branch_office_id,
                WasherPaySettlement.pay_date == day,
                WasherPaySettlement.washer_id == washer_id,
            ).limit(1),
        ).first()
        if row is not None:
            return row
        now = business_now()
        row = WasherPaySettlement(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            pay_date=day,
            is_paid=False,
            manual_goal_met=False,
            added_date=now,
            updated_date=now,
        )
        self.db.add(row)
        return row

    def set_manual_goal_met(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
        date_value: str,
        washer_id: int,
        manual_goal_met: bool,
    ) -> WasherPayManualGoalMetResponse:
        self._ensure_branch_access(user, branch_office_id)
        day = self._parse_date(date_value)
        if washer_id not in self._branch_washer.list_washer_ids_for_branch(branch_office_id):
            raise WasherPayValidationError("El lavador no pertenece a esta sucursal")

        now = business_now()
        row = self._upsert_settlement_row(
            branch_office_id=branch_office_id,
            day=day,
            washer_id=washer_id,
        )
        row.manual_goal_met = manual_goal_met
        row.updated_date = now
        self.db.commit()

        return WasherPayManualGoalMetResponse(
            washer_id=str(washer_id),
            branch_office_id=str(branch_office_id),
            date=day.isoformat(),
            manual_goal_met=manual_goal_met,
        )

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
        row = self._upsert_settlement_row(
            branch_office_id=branch_office_id,
            day=day,
            washer_id=washer_id,
        )
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
        """Bruto cobrado por línea; reparte ticket.total (igual que la columna TOTAL del ticket)."""
        payable = self._payable_service_lines(ticket_rows)
        if not payable or ticket.id is None:
            return {}

        pricing = self._tickets._ticket_pricing(ticket.id, ticket)
        ticket_total = max(0, pricing["total"])
        if ticket_total <= 0:
            return {}

        if len(payable) == 1:
            row = payable[0]
            return {row.id or 0: ticket_total}

        raw: dict[int, int] = {}
        for row in payable:
            raw[row.id or 0] = max(0, TicketLineService._resolved_line_total(row))

        total_raw = sum(raw.values())
        if total_raw <= 0:
            share = round_money(Decimal(ticket_total) / Decimal(len(payable)))
            return {row.id or 0: share for row in payable}

        line_ids = list(raw.keys())
        scaled: dict[int, int] = {}
        allocated = 0
        for index, line_id in enumerate(line_ids):
            if index == len(line_ids) - 1:
                scaled[line_id] = max(0, ticket_total - allocated)
                continue
            part = round_money(
                Decimal(raw[line_id]) * Decimal(ticket_total) / Decimal(total_raw),
            )
            scaled[line_id] = part
            allocated += part
        return scaled

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

    def _line_gross_payment_split(self, ticket: Ticket, line_gross: int) -> tuple[int, int]:
        """Reparte el bruto de la línea entre efectivo y tarjeta."""
        if line_gross <= 0 or ticket.id is None:
            return 0, 0

        efectivo_gross, transbank_gross = TicketService._payment_split_amounts(ticket)
        if transbank_gross <= 0:
            return line_gross, 0
        if efectivo_gross <= 0:
            return 0, line_gross

        ticket_gross = efectivo_gross + transbank_gross
        if ticket_gross <= 0:
            return line_gross, 0

        efectivo_part = round_money(
            Decimal(line_gross) * Decimal(efectivo_gross) / Decimal(ticket_gross),
        )
        return efectivo_part, line_gross - efectivo_part

    def _line_net_payment_split(self, ticket: Ticket, line_net: int) -> tuple[int, int]:
        """Reparte el neto de la línea entre efectivo y tarjeta (Transbank/boleta/factura)."""
        if line_net <= 0 or ticket.id is None:
            return 0, 0

        efectivo_gross, transbank_gross = TicketService._payment_split_amounts(ticket)
        if transbank_gross <= 0:
            return line_net, 0
        if efectivo_gross <= 0:
            return 0, line_net

        mixed = split_mixed_payment_totals(efectivo_gross, transbank_gross)
        subtotal_total = mixed["subtotal"]
        if subtotal_total <= 0:
            return line_net, 0

        efectivo_part = round_money(
            Decimal(line_net) * Decimal(efectivo_gross) / Decimal(subtotal_total),
        )
        card_part = line_net - efectivo_part
        return efectivo_part, card_part

    def _line_pay_payment_split(
        self,
        ticket: Ticket,
        line_net: int,
        commission: int,
    ) -> tuple[int, int]:
        """Reparte la comisión de la línea entre efectivo y tarjeta."""
        if commission <= 0 or line_net <= 0:
            return 0, 0
        efectivo_net, card_net = self._line_net_payment_split(ticket, line_net)
        efectivo_pay = round_money(
            Decimal(commission) * Decimal(efectivo_net) / Decimal(line_net),
        )
        return efectivo_pay, commission - efectivo_pay

    def _washer_pay_by_payment(
        self,
        line_contexts: list[_WasherPayLineContext],
        ticket_detail_lines: list[WasherPayDetailLine],
    ) -> tuple[int, int, int]:
        efectivo_total = 0
        card_total = 0
        for ctx, detail_line in zip(line_contexts, ticket_detail_lines, strict=False):
            if detail_line.kind != "ticket":
                continue
            commission = detail_line.amount
            efectivo_part, card_part = self._line_pay_payment_split(
                ctx.ticket,
                ctx.full_line_net,
                commission,
            )
            efectivo_total += efectivo_part
            card_total += card_part
        return efectivo_total, card_total, efectivo_total + card_total

    def _group_pay_by_payment(
        self,
        *,
        branch_office_id: int,
        group_id: int,
        day: date,
    ) -> tuple[int, int, int]:
        member_ids = self._washer_groups.member_ids_for_group_on_date(group_id, day=day)
        if not member_ids:
            return 0, 0, 0
        _ef_gross, _card_gross, group_gross = self._group_sales_gross_by_payment(
            branch_office_id=branch_office_id,
            group_id=group_id,
            day=day,
        )
        group_goal_met = self._is_goal_met(
            sales_volume=group_gross,
            goal_amount=self._combined_group_goal_amount(member_ids),
        )
        efectivo_total = 0
        card_total = 0
        seen: set[tuple[int, int]] = set()
        for line, ticket, _line_rows, _line_gross, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            if line.washer_daily_group_id != group_id:
                continue
            key = (ticket.id or 0, line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            pct, _, _ = self._commission_percentage_for_line(
                line,
                day=day,
                goal_met=group_goal_met,
                group_member_ids=member_ids,
            )
            commission = self._line_sales_credit(line_net, pct)
            efectivo_part, card_part = self._line_pay_payment_split(
                ticket,
                line_net,
                commission,
            )
            efectivo_total += efectivo_part
            card_total += card_part
        return efectivo_total, card_total, efectivo_total + card_total

    def _group_total_pay_amount(
        self,
        *,
        branch_office_id: int,
        group_id: int,
        day: date,
    ) -> int:
        """Group commission: waterfall when all lines use washer %, else per-line sum."""
        member_ids = self._washer_groups.member_ids_for_group_on_date(group_id, day=day)
        if not member_ids:
            return 0
        _ef_gross, card_gross, gross_total = self._group_sales_gross_by_payment(
            branch_office_id=branch_office_id,
            group_id=group_id,
            day=day,
        )
        group_goal_met = self._is_goal_met(
            sales_volume=gross_total,
            goal_amount=self._combined_group_goal_amount(member_ids),
        )
        line_entries: list[tuple[TicketBranchOfficeService, int]] = []
        seen: set[tuple[int, int]] = set()
        for line, ticket, _line_rows, _line_gross, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            if line.washer_daily_group_id != group_id:
                continue
            key = (ticket.id or 0, line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            line_entries.append((line, line_net))

        has_service_override = any(
            self._service_washer_percentage(line) > 0 for line, _net in line_entries
        )
        if not has_service_override:
            avg_pct = self._group_average_effective_pct(
                member_ids=member_ids,
                day=day,
                goal_met=group_goal_met,
            )
            *_, _, _, final_amount = self._waterfall_pay_steps(
                gross_total,
                card_gross,
                avg_pct,
            )
            return final_amount

        total = 0
        for line, line_net in line_entries:
            pct, _, _ = self._commission_percentage_for_line(
                line,
                day=day,
                goal_met=group_goal_met,
                group_member_ids=member_ids,
            )
            total += self._line_sales_credit(line_net, pct)
        return self._apply_coin_round(total)

    @staticmethod
    def _reconcile_pay_split_to_target(
        efectivo: int,
        card: int,
        target: int,
    ) -> tuple[int, int, int]:
        total = efectivo + card
        if target <= 0:
            return 0, 0, 0
        if total == target:
            return efectivo, card, target
        if total <= 0:
            return target, 0, target
        delta = target - total
        efectivo = max(0, efectivo + delta)
        return efectivo, card, target

    def _line_bruto_from_net(self, ticket: Ticket, line_net: int) -> int:
        """Bruto (con IVA) proporcional a partir del neto de línea."""
        if line_net <= 0 or ticket.id is None:
            return 0
        pricing = self._tickets._ticket_pricing(ticket.id, ticket)
        subtotal = pricing["subtotal"]
        total = pricing["total"]
        if subtotal <= 0:
            return line_net
        if total <= subtotal:
            return line_net
        return round_money(Decimal(line_net) * Decimal(total) / Decimal(subtotal))

    def _washer_sales_gross_by_payment(
        self,
        line_contexts: list[_WasherPayLineContext],
    ) -> tuple[int, int, int]:
        """Venta bruta por medio de pago, sin aplicar % del lavador."""
        efectivo = 0
        card = 0
        seen: set[tuple[int, int]] = set()
        for ctx in line_contexts:
            key = (ctx.ticket.id or 0, ctx.line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            efectivo_part, card_part = self._line_gross_payment_split(
                ctx.ticket,
                ctx.full_line_gross,
            )
            efectivo += efectivo_part
            card += card_part
        return efectivo, card, efectivo + card

    def _group_sales_gross_by_payment(
        self,
        *,
        branch_office_id: int,
        group_id: int,
        day: date,
    ) -> tuple[int, int, int]:
        efectivo = 0
        card = 0
        seen: set[tuple[int, int]] = set()
        for line, ticket, _line_rows, line_gross, _line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            if line.washer_daily_group_id != group_id:
                continue
            key = (ticket.id or 0, line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            efectivo_part, card_part = self._line_gross_payment_split(ticket, line_gross)
            efectivo += efectivo_part
            card += card_part
        return efectivo, card, efectivo + card

    def _waterfall_pay_steps(
        self,
        gross_total: int,
        card_gross: int,
        effective_pct: Decimal,
    ) -> tuple[int, int, int, int]:
        """Card VAT only, net total (gross − card VAT), commission %, coin-rounded pay."""
        card_tax = self._card_tax_from_gross(card_gross)
        total_calculado = max(0, gross_total - card_tax)
        commission_before = round_money(
            Decimal(total_calculado) * effective_pct / Decimal("100"),
        )
        final_amount = self._apply_coin_round(commission_before)
        return card_tax, total_calculado, commission_before, final_amount

    def _card_tax_from_gross(self, card_gross: int) -> int:
        """VAT embedded in card gross (not coin-rounded)."""
        if card_gross <= 0:
            return 0
        return card_gross - round_money(Decimal(card_gross) / TICKET_IVA_GROSS_FACTOR)

    def _build_pay_breakdown(
        self,
        *,
        gross_total: int,
        card_gross: int,
        effective_pct: Decimal,
        is_group: bool = False,
    ) -> tuple[list[WasherPayBreakdownRow], int]:
        card_tax, total_calculado, commission_before, final_amount = (
            self._waterfall_pay_steps(gross_total, card_gross, effective_pct)
        )
        pct_label = self._format_percentage_display(effective_pct)
        if is_group:
            commission_label = f"Comisión ({pct_label} promedio del grupo)"
        else:
            commission_label = f"Comisión ({pct_label})"
        first_label = "Total del Grupo" if is_group else "Total cobrado (bruto)"
        final_label = "Total a pagar por el grupo" if is_group else "Total a pagar"
        rows: list[WasherPayBreakdownRow] = [
            WasherPayBreakdownRow(label=first_label, amount=gross_total),
            WasherPayBreakdownRow(label="Tarjeta (bruto)", amount=card_gross),
            WasherPayBreakdownRow(label="− IVA solo tarjeta (19%)", amount=card_tax),
            WasherPayBreakdownRow(label="Total neto (efectivo + tarjeta)", amount=total_calculado),
            WasherPayBreakdownRow(
                label=commission_label,
                amount=commission_before,
            ),
        ]
        if commission_before != final_amount:
            rows.append(
                WasherPayBreakdownRow(
                    label=f"{final_label} (redondeo)",
                    amount=final_amount,
                    emphasis=True,
                ),
            )
        else:
            rows.append(
                WasherPayBreakdownRow(
                    label=final_label,
                    amount=final_amount,
                    emphasis=True,
                ),
            )
        return rows, final_amount

    def _washer_sales_liquid_by_payment(
        self,
        line_contexts: list[_WasherPayLineContext],
    ) -> tuple[int, int, int]:
        """Venta líquida (neto) por medio de pago, sin aplicar % del lavador."""
        efectivo = 0
        card = 0
        seen: set[tuple[int, int]] = set()
        for ctx in line_contexts:
            key = (ctx.ticket.id or 0, ctx.line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            efectivo_part, card_part = self._line_net_payment_split(
                ctx.ticket,
                ctx.full_line_net,
            )
            efectivo += efectivo_part
            card += card_part
        return efectivo, card, efectivo + card

    def _group_sales_liquid_by_payment(
        self,
        *,
        branch_office_id: int,
        group_id: int,
        day: date,
    ) -> tuple[int, int, int]:
        """Venta líquida (neto) del grupo por medio de pago, sin aplicar %."""
        efectivo = 0
        card = 0
        seen: set[tuple[int, int]] = set()
        for line, ticket, _line_rows, _line_gross, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            if line.washer_daily_group_id != group_id:
                continue
            key = (ticket.id or 0, line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            efectivo_part, card_part = self._line_net_payment_split(ticket, line_net)
            efectivo += efectivo_part
            card += card_part
        return efectivo, card, efectivo + card

    def _washer_sales_volume(
        self,
        line_contexts: list[_WasherPayLineContext],
    ) -> int:
        """Total vendido (bruto) atribuido al lavador, sin aplicar %."""
        total = 0
        seen: set[tuple[int, int]] = set()
        for ctx in line_contexts:
            key = (ctx.ticket.id or 0, ctx.line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            total += self._line_bruto_from_net(ctx.ticket, ctx.full_line_net)
        return total

    def _group_sales_volume(
        self,
        *,
        branch_office_id: int,
        group_id: int,
        day: date,
    ) -> int:
        """Total vendido (bruto) del grupo, sin aplicar %."""
        total = 0
        seen: set[tuple[int, int]] = set()
        for line, ticket, _line_rows, _line_gross, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            if line.washer_daily_group_id != group_id:
                continue
            key = (ticket.id or 0, line.id or 0)
            if key in seen:
                continue
            seen.add(key)
            total += self._line_bruto_from_net(ticket, line_net)
        return total

    def _group_name(self, group_id: int) -> str:
        row = self.db.get(WasherDailyGroup, group_id)
        if row is None or not row.is_active:
            return f"Grupo #{group_id}"
        return row.name.strip() or f"Grupo #{group_id}"

    def _group_member_ids_for_pay_day(self, group_id: int, *, day: date) -> list[int]:
        return self._washer_groups.member_ids_for_group_on_date(group_id, day=day)

    def _lines_by_ticket_id(
        self,
        ticket_ids: list[int],
    ) -> dict[int, list[TicketBranchOfficeService]]:
        """Ticket lines for many tickets in batched queries (avoids one query per ticket)."""
        grouped: dict[int, list[TicketBranchOfficeService]] = defaultdict(list)
        chunk_size = 500
        for start in range(0, len(ticket_ids), chunk_size):
            chunk = ticket_ids[start:start + chunk_size]
            if not chunk:
                continue
            rows = self.db.scalars(
                select(TicketBranchOfficeService)
                .where(
                    TicketBranchOfficeService.ticket_id.in_(chunk),
                    TicketBranchOfficeService.deleted_date.is_(None),
                )
                .order_by(TicketBranchOfficeService.id.asc()),
            ).all()
            for row in rows:
                if row.ticket_id is not None:
                    grouped[int(row.ticket_id)].append(row)
        return grouped

    def _payable_entries_by_day(
        self,
        *,
        branch_office_id: int,
        start_day: date,
        end_day: date,
    ) -> dict[
        date,
        list[
            tuple[
                TicketBranchOfficeService,
                Ticket,
                list[TicketBranchOfficeService],
                int,
                int,
            ]
        ],
    ]:
        """Payable lines grouped by revenue day, filtering candidate tickets in SQL."""
        window_start = datetime.combine(start_day, time.min)
        window_end = datetime.combine(end_day, time.max)
        branch_ticket_ids = self._tickets._ticket_ids_for_branch_subquery(branch_office_id)
        ticket_rows = self.db.scalars(
            select(Ticket)
            .where(
                Ticket.deleted_date.is_(None),
                Ticket.id.in_(branch_ticket_ids),
                or_(
                    and_(
                        Ticket.updated_date.isnot(None),
                        Ticket.updated_date >= window_start,
                        Ticket.updated_date <= window_end,
                    ),
                    and_(
                        Ticket.added_date.isnot(None),
                        Ticket.added_date >= window_start,
                        Ticket.added_date <= window_end,
                    ),
                ),
            )
            .order_by(Ticket.id.asc()),
        ).all()

        # Branch membership is already enforced by the ticket-id subquery above, so no
        # per-ticket re-check is needed here.
        candidates: list[tuple[Ticket, date]] = []
        for ticket in ticket_rows:
            if ticket.id is None:
                continue
            if not self._tickets.ticket_eligible_for_washer_pay(ticket):
                continue
            revenue_day = self._tickets.ticket_revenue_day(ticket)
            if revenue_day is None or revenue_day < start_day or revenue_day > end_day:
                continue
            candidates.append((ticket, revenue_day))

        lines_by_ticket = self._lines_by_ticket_id(
            [int(ticket.id) for ticket, _day in candidates if ticket.id is not None],
        )

        by_day: dict[
            date,
            list[
                tuple[
                    TicketBranchOfficeService,
                    Ticket,
                    list[TicketBranchOfficeService],
                    int,
                    int,
                ]
            ],
        ] = {}
        cursor = start_day
        while cursor <= end_day:
            by_day[cursor] = []
            cursor += timedelta(days=1)

        for ticket, revenue_day in candidates:
            line_rows = lines_by_ticket.get(int(ticket.id or 0), [])
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
                by_day[revenue_day].append((line, ticket, line_rows, gross, line_net))

        return by_day

    def prefetch_payable_lines_for_range(
        self,
        *,
        branch_office_id: int,
        start_day: date,
        end_day: date,
    ) -> None:
        """Warm the per-day cache for a whole range with a single ticket query."""
        if end_day < start_day:
            return
        pending = False
        cursor = start_day
        while cursor <= end_day:
            if (branch_office_id, cursor) not in self._payable_line_entries_cache:
                pending = True
                break
            cursor += timedelta(days=1)
        if not pending:
            return

        by_day = self._payable_entries_by_day(
            branch_office_id=branch_office_id,
            start_day=start_day,
            end_day=end_day,
        )
        for day, entries in by_day.items():
            self._payable_line_entries_cache[(branch_office_id, day)] = entries

    def _branch_payable_line_entries(
        self,
        *,
        branch_office_id: int,
        day: date,
    ) -> list[
        tuple[
            TicketBranchOfficeService,
            Ticket,
            list[TicketBranchOfficeService],
            int,
            int,
        ]
    ]:
        cache_key = (branch_office_id, day)
        cached = self._payable_line_entries_cache.get(cache_key)
        if cached is not None:
            return cached

        by_day = self._payable_entries_by_day(
            branch_office_id=branch_office_id,
            start_day=day,
            end_day=day,
        )
        entries = by_day.get(day, [])
        self._payable_line_entries_cache[cache_key] = entries
        return entries

    def _iter_branch_payable_lines(
        self,
        *,
        branch_office_id: int,
        day: date,
    ):
        for entry in self._branch_payable_line_entries(
            branch_office_id=branch_office_id,
            day=day,
        ):
            yield entry

    def _branch_washer_attributed_sales(
        self,
        *,
        branch_office_id: int,
        day: date,
    ) -> dict[int, int]:
        sales: dict[int, int] = defaultdict(int)
        for line, ticket, line_rows, _line_gross, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            del ticket
            group_id = line.washer_daily_group_id
            if group_id is not None and group_id > 0:
                member_ids = self._group_member_ids_for_pay_day(group_id, day=day)
                if member_ids:
                    base_pct = self._base_commission_percentage_for_line(
                        line,
                        day=day,
                        group_member_ids=member_ids,
                    )
                    credit = self._line_sales_credit(line_net, base_pct)
                    for member_id in member_ids:
                        sales[member_id] += credit
                    continue
            line_washer_id = self._line_attributed_washer_id(line, line_rows)
            if line_washer_id is not None:
                assignment = self._assignment_for_washer(line_washer_id)
                if assignment is not None:
                    pct = self._base_commission_percentage_for_line(
                        line,
                        day=day,
                        assignment=assignment,
                    )
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
            assignment = self._assignment_for_washer(member_id)
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
        goal_met: bool,
    ) -> Decimal:
        if not member_ids:
            return Decimal("0")
        total = Decimal("0")
        for member_id in member_ids:
            assignment = self._assignment_for_washer(member_id)
            if assignment is None:
                continue
            total += self._effective_percentage(
                assignment,
                day=day,
                goal_met=goal_met,
            )
        return total / Decimal(len(member_ids))

    def _paid_solo_line_contexts_for_washer(
        self,
        *,
        branch_office_id: int,
        washer_id: int,
        day: date,
    ) -> list[_WasherPayLineContext]:
        """Tickets cobrados asignados al lavador sin grupo (trabajo individual)."""
        assignment = self._assignment_for_washer(washer_id)
        if assignment is None:
            return []

        contexts: list[_WasherPayLineContext] = []
        seen: set[tuple[int, int]] = set()

        for line, ticket, line_rows, line_gross, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            group_id = line.washer_daily_group_id
            if group_id is not None and group_id > 0:
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
                    full_line_gross=line_gross,
                    full_line_net=line_net,
                    group_id=None,
                    group_member_count=1,
                    group_name=None,
                ),
            )

        return contexts

    def _paid_line_contexts_for_group(
        self,
        *,
        branch_office_id: int,
        group_id: int,
        day: date,
    ) -> list[_WasherPayLineContext]:
        """Tickets cobrados asignados al grupo (trabajo grupal)."""
        member_ids = self._group_member_ids_for_pay_day(group_id, day=day)
        if not member_ids:
            return []

        member_count = len(member_ids)
        contexts: list[_WasherPayLineContext] = []
        seen: set[tuple[int, int]] = set()

        for line, ticket, line_rows, line_gross, line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            del line_rows
            if line.washer_daily_group_id != group_id:
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
                    full_line_gross=line_gross,
                    full_line_net=line_net,
                    group_id=group_id,
                    group_member_count=member_count,
                    group_name=self._group_name(group_id),
                ),
            )

        return contexts

    def _paid_line_contexts_for_washer(
        self,
        *,
        branch_office_id: int,
        washer_id: int,
        day: date,
    ) -> list[_WasherPayLineContext]:
        return self._paid_solo_line_contexts_for_washer(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            day=day,
        )

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
        force_goal_met: bool = False,
    ) -> tuple[int, int, list[WasherPayDetailLine], int]:
        assignment = self._assignment_for_washer(washer_id)
        if assignment is None:
            return 0, 0, [], 0

        line_contexts = self._paid_line_contexts_for_washer(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            day=day,
        )
        ticket_ids = {ctx.ticket.id for ctx in line_contexts if ctx.ticket.id is not None}

        base_pct = self._percentage_for_date(assignment, day=day)
        solo_sales_gross = self._washer_sales_volume(line_contexts)
        solo_goal_met = self._is_goal_met(
            sales_volume=solo_sales_gross,
            goal_amount=self._member_goal_amount(assignment),
        ) or force_goal_met
        boost_pct = self._goal_percentage_boost(
            assignment,
            day=day,
            goal_met=solo_goal_met,
        )
        effective_pct = base_pct + boost_pct

        detail_lines: list[WasherPayDetailLine] = []
        for ctx in line_contexts:
            ticket_id = str(ctx.ticket.id) if ctx.ticket.id is not None else None
            plate = (ctx.ticket.license_plate_id or "").strip()
            service_label = self._line_service_label(ctx.line)
            description_parts = [f"T-{ctx.ticket.id}"]
            if plate:
                description_parts.append(plate)
            description_parts.append(service_label)

            line_pct, pct_scope, pct_label = self._commission_percentage_for_line(
                ctx.line,
                day=day,
                goal_met=solo_goal_met,
                assignment=assignment,
            )
            sales_credit = self._line_sales_credit(ctx.full_line_net, line_pct)
            detail_lines.append(
                WasherPayDetailLine(
                    kind="ticket",
                    ticket_id=ticket_id,
                    label=service_label,
                    description=" · ".join(description_parts),
                    base_amount=sales_credit,
                    line_gross_net=ctx.full_line_net,
                    group_member_count=None,
                    percentage=self._format_percentage_display(line_pct),
                    percentage_scope=pct_scope,  # type: ignore[arg-type]
                    percentage_label=pct_label,
                    day_percentage=(
                        self._format_percentage_display(effective_pct)
                        if pct_scope == "service"
                        else None
                    ),
                    amount=sales_credit,
                ),
            )

        total = sum(line.amount for line in detail_lines)
        total = self._apply_coin_round(total)
        return total, len(ticket_ids), detail_lines, solo_sales_gross

    def _detail_lines_for_group_contexts(
        self,
        *,
        line_contexts: list[_WasherPayLineContext],
        day: date,
        goal_met: bool,
    ) -> list[WasherPayDetailLine]:
        detail_lines: list[WasherPayDetailLine] = []
        for ctx in line_contexts:
            if ctx.group_id is None:
                continue
            member_ids = self._group_member_ids_for_pay_day(ctx.group_id, day=day)
            line_pct, pct_scope, pct_label = self._commission_percentage_for_line(
                ctx.line,
                day=day,
                goal_met=goal_met,
                group_member_ids=member_ids,
            )
            pct_display = self._format_percentage_display(line_pct)
            sales_credit = self._line_sales_credit(ctx.full_line_net, line_pct)
            ticket_id = str(ctx.ticket.id) if ctx.ticket.id is not None else None
            plate = (ctx.ticket.license_plate_id or "").strip()
            service_label = self._line_service_label(ctx.line)
            description_parts = [f"T-{ctx.ticket.id}"]
            if plate:
                description_parts.append(plate)
            description_parts.append(service_label)
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
                    percentage_scope=pct_scope,  # type: ignore[arg-type]
                    percentage_label=pct_label,
                    day_percentage=None,
                    amount=sales_credit,
                ),
            )
        return detail_lines

    def _group_ticket_ids_for_day(
        self,
        *,
        branch_office_id: int,
        group_id: int,
        day: date,
    ) -> set[int]:
        ticket_ids: set[int] = set()
        for line, ticket, _line_rows, _line_gross, _line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            if line.washer_daily_group_id != group_id:
                continue
            if ticket.id is not None:
                ticket_ids.add(ticket.id)
        return ticket_ids

    def _format_group_applied_percentage(self, values: list[str]) -> str | None:
        parsed = [
            self._parse_percentage(value)
            for value in values
            if (value or "").strip()
        ]
        if not parsed:
            return None
        avg = sum(parsed, Decimal("0")) / Decimal(len(parsed))
        return self._format_percentage_display(avg)

    def _pay_assignees_for_day(
        self,
        *,
        branch_office_id: int,
        day: date,
    ) -> tuple[set[int], set[int]]:
        """
        Lavadores y grupos con tickets cobrados ese día.
        - Línea con grupo → solo cuenta el grupo (no cada miembro).
        - Línea sin grupo → cuenta el lavador individual (aunque esté en un grupo ese día).
        """
        solo_washer_ids: set[int] = set()
        group_ids: set[int] = set()
        for line, _ticket, line_rows, _line_gross, _line_net in self._iter_branch_payable_lines(
            branch_office_id=branch_office_id,
            day=day,
        ):
            group_id = line.washer_daily_group_id
            if group_id is not None and group_id > 0:
                group_ids.add(group_id)
                continue
            washer_id = self._line_attributed_washer_id(line, line_rows)
            if washer_id is not None and washer_id > 0:
                solo_washer_ids.add(washer_id)
        return solo_washer_ids, group_ids

    def summary_by_branch_and_date(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
        date_value: str,
    ) -> WasherPaySummaryResponse:
        branch = self._ensure_branch_access(user, branch_office_id)
        day = self._parse_date(date_value)

        solo_washer_ids, active_group_ids = self._pay_assignees_for_day(
            branch_office_id=branch_office_id,
            day=day,
        )
        if not solo_washer_ids and not active_group_ids:
            return WasherPaySummaryResponse(
                branch_office_id=str(branch_office_id),
                branch_name=branch.branch_office,
                date=day.isoformat(),
                items=[],
                amount=0,
            )

        washer_ids = self._branch_washer_ids(branch_office_id)
        status_map = self._payment_status_map(
            branch_office_id=branch_office_id,
            day=day,
            washer_ids=washer_ids,
        )
        manual_goal_met_map = self._manual_goal_met_map(
            branch_office_id=branch_office_id,
            day=day,
            washer_ids=washer_ids,
        )
        washer_by_id: dict[int, dict[str, object]] = {}
        for washer_id in solo_washer_ids:
            manual_goal_met = manual_goal_met_map.get(washer_id, False)
            amount, ticket_count, _, solo_sales_gross = self._compute_washer_pay(
                branch_office_id=branch_office_id,
                washer_id=washer_id,
                day=day,
                force_goal_met=manual_goal_met,
            )
            if ticket_count <= 0 and amount <= 0:
                continue
            assignment = self._assignment_for_washer(washer_id)
            solo_goal_met = self._is_goal_met(
                sales_volume=solo_sales_gross,
                goal_amount=self._member_goal_amount(assignment),
            )
            effective_goal_met = solo_goal_met or manual_goal_met
            applied_pct = (
                self._format_percentage_display(
                    self._effective_percentage(
                        assignment,
                        day=day,
                        goal_met=effective_goal_met,
                    ),
                )
                if assignment is not None
                else None
            )
            washer_by_id[washer_id] = {
                "full_name": self._washer_full_name(washer_id),
                "amount": amount,
                "ticket_count": ticket_count,
                "applied_percentage": applied_pct,
                "payment_status": status_map.get(washer_id, "unpaid"),
            }

        assignees: list[tuple[str, int, str]] = []
        for group_id in sorted(active_group_ids, key=lambda gid: self._group_name(gid).lower()):
            assignees.append(("group", group_id, self._group_name(group_id)))
        for washer_id in sorted(
            solo_washer_ids,
            key=lambda wid: self._washer_full_name(wid).lower(),
        ):
            assignees.append(("washer", washer_id, self._washer_full_name(washer_id)))

        items: list[WasherPaySummaryItem] = []
        for kind, entity_id, display_name in assignees:
            if kind == "washer":
                data = washer_by_id.get(entity_id)
                if data is None:
                    continue
                items.append(
                    WasherPaySummaryItem(
                        kind="washer",
                        washer_id=str(entity_id),
                        full_name=str(data["full_name"]),
                        amount=int(data["amount"]),
                        ticket_count=int(data["ticket_count"]),
                        applied_percentage=(
                            str(data["applied_percentage"])
                            if data["applied_percentage"] is not None
                            else None
                        ),
                        payment_status=status_map.get(entity_id, "unpaid"),
                    ),
                )
                continue

            member_ids = self._washer_groups.member_ids_for_group_on_date(
                entity_id,
                day=day,
            )
            if not member_ids:
                continue
            group_ticket_ids = self._group_ticket_ids_for_day(
                branch_office_id=branch_office_id,
                group_id=entity_id,
                day=day,
            )
            group_amount = self._group_total_pay_amount(
                branch_office_id=branch_office_id,
                group_id=entity_id,
                day=day,
            )
            if group_amount <= 0 and not group_ticket_ids:
                continue
            group_sales_gross = self._group_sales_volume(
                branch_office_id=branch_office_id,
                group_id=entity_id,
                day=day,
            )
            group_goal_met = self._is_goal_met(
                sales_volume=group_sales_gross,
                goal_amount=self._combined_group_goal_amount(member_ids),
            )
            member_pcts = [
                self._format_percentage_display(
                    self._effective_percentage(
                        assignment_row,
                        day=day,
                        goal_met=group_goal_met,
                    ),
                )
                for member_id in member_ids
                if (assignment_row := self._assignment_for_washer(member_id)) is not None
            ]
            paying_members = list(member_ids) if group_amount > 0 else []
            group_status: WasherPayPaymentStatus = (
                "paid"
                if paying_members
                and all(
                    status_map.get(member_id, "unpaid") == "paid"
                    for member_id in paying_members
                )
                else "unpaid"
            )
            items.append(
                WasherPaySummaryItem(
                    kind="group",
                    group_id=str(entity_id),
                    member_washer_ids=[str(member_id) for member_id in member_ids],
                    full_name=display_name,
                    amount=group_amount,
                    ticket_count=len(group_ticket_ids),
                    applied_percentage=self._format_group_applied_percentage(member_pcts),
                    payment_status=group_status,
                ),
            )

        return WasherPaySummaryResponse(
            branch_office_id=str(branch_office_id),
            branch_name=branch.branch_office,
            date=day.isoformat(),
            items=items,
            amount=sum(row.amount for row in items),
        )

    @staticmethod
    def _split_amount_among(amount: int, member_ids: list[int]) -> dict[int, int]:
        ids = sorted({member_id for member_id in member_ids if member_id > 0})
        count = len(ids)
        if amount <= 0 or count == 0:
            return {}
        if count == 1:
            return {ids[0]: amount}
        per = round_money(Decimal(amount) / Decimal(count))
        shares: dict[int, int] = {}
        assigned = 0
        for index, member_id in enumerate(ids):
            if index == count - 1:
                shares[member_id] = max(0, amount - assigned)
            else:
                shares[member_id] = per
                assigned += per
        return shares

    def _resolve_month_report_branches(
        self,
        user: UserPublic,
        branch_office_id: int | None,
    ) -> list[BranchOffice]:
        scope = TicketService._branch_scope_for_user(user)
        if scope == 0:
            raise WasherPayValidationError("No tiene permiso para consultar pagos")
        if scope is not None:
            return [self._ensure_branch_access(user, scope)]
        if branch_office_id is not None and branch_office_id >= 1:
            return [self._ensure_branch_access(user, branch_office_id)]
        branches = self.db.scalars(
            select(BranchOffice)
            .where(BranchOffice.deleted_date.is_(None))
            .order_by(BranchOffice.branch_office.asc(), BranchOffice.id.asc()),
        ).all()
        return [branch for branch in branches if branch.is_active and branch.id is not None]

    def month_report(
        self,
        user: UserPublic,
        *,
        year: int,
        month: int,
        branch_office_id: int | None = None,
        washer_id: int | None = None,
    ) -> WasherPayMonthResponse:
        if month < 1 or month > 12:
            raise WasherPayValidationError("Mes no válido")
        if year < 2000 or year > 2100:
            raise WasherPayValidationError("Año no válido")
        if washer_id is not None and washer_id < 1:
            raise WasherPayValidationError("Lavador no válido")

        branches = self._resolve_month_report_branches(user, branch_office_id)
        last_day = calendar.monthrange(year, month)[1]
        today = business_today()
        range_start = date(year, month, 1)
        range_end = min(date(year, month, last_day), today)

        filter_washer_id = washer_id if washer_id is not None and washer_id >= 1 else None
        single_branch = branches[0] if len(branches) == 1 else None

        if range_end >= range_start:
            for branch in branches:
                if branch.id is None:
                    continue
                self.prefetch_payable_lines_for_range(
                    branch_office_id=int(branch.id),
                    start_day=range_start,
                    end_day=range_end,
                )

        totals: dict[tuple[int, int], dict[str, object]] = {}
        day_rows: dict[tuple[int, int], list[WasherPayMonthDayItem]] = defaultdict(list)

        if range_end >= range_start:
            for branch in branches:
                if branch.id is None:
                    continue
                branch_id = int(branch.id)
                branch_name = (branch.branch_office or "").strip() or f"Sucursal {branch_id}"
                for day_num in range(1, last_day + 1):
                    day = date(year, month, day_num)
                    if day > today:
                        break
                    try:
                        summary = self.summary_by_branch_and_date(
                            user,
                            branch_office_id=branch_id,
                            date_value=day.isoformat(),
                        )
                    except WasherPayValidationError:
                        continue

                    day_shares: dict[int, dict[str, int]] = defaultdict(
                        lambda: {"amount": 0, "tickets": 0, "paid": 0, "unpaid": 0},
                    )

                    def _add_day_share(
                        worker_id: int,
                        share_amount: int,
                        tickets: int,
                        payment_status: WasherPayPaymentStatus,
                    ) -> None:
                        if filter_washer_id is not None and worker_id != filter_washer_id:
                            return
                        day_shares[worker_id]["amount"] += share_amount
                        day_shares[worker_id]["tickets"] += tickets
                        if payment_status == "paid":
                            day_shares[worker_id]["paid"] += share_amount
                        else:
                            day_shares[worker_id]["unpaid"] += share_amount

                    for item in summary.items:
                        if item.kind == "group":
                            member_ids = [
                                int(member_id)
                                for member_id in item.member_washer_ids
                                if str(member_id).isdigit() and int(member_id) > 0
                            ]
                            shares = self._split_amount_among(item.amount, member_ids)
                            for member_id, share in shares.items():
                                _add_day_share(
                                    member_id,
                                    share,
                                    item.ticket_count,
                                    item.payment_status,
                                )
                            continue
                        if not item.washer_id or not str(item.washer_id).isdigit():
                            continue
                        solo_id = int(item.washer_id)
                        if solo_id < 1:
                            continue
                        _add_day_share(
                            solo_id,
                            item.amount,
                            item.ticket_count,
                            item.payment_status,
                        )

                    for worker_id, share in day_shares.items():
                        amount = int(share["amount"])
                        tickets = int(share["tickets"])
                        paid_amount = int(share["paid"])
                        unpaid_amount = int(share["unpaid"])
                        if amount <= 0 and tickets <= 0:
                            continue
                        status: WasherPayPaymentStatus = (
                            "paid" if unpaid_amount <= 0 and amount > 0 else "unpaid"
                        )
                        key = (worker_id, branch_id)
                        row = totals.get(key)
                        if row is None:
                            row = {
                                "full_name": self._washer_full_name(worker_id),
                                "branch_name": branch_name,
                                "amount": 0,
                                "paid_amount": 0,
                                "unpaid_amount": 0,
                                "ticket_count": 0,
                            }
                            totals[key] = row
                        row["amount"] = int(row["amount"]) + amount
                        row["ticket_count"] = int(row["ticket_count"]) + tickets
                        row["paid_amount"] = int(row["paid_amount"]) + paid_amount
                        row["unpaid_amount"] = int(row["unpaid_amount"]) + unpaid_amount
                        day_rows[key].append(
                            WasherPayMonthDayItem(
                                date=day.isoformat(),
                                amount=amount,
                                ticket_count=tickets,
                                payment_status=status,
                            ),
                        )

        items: list[WasherPayMonthWorkerItem] = []
        for (worker_id, branch_id), row in totals.items():
            days = sorted(day_rows.get((worker_id, branch_id), []), key=lambda d: d.date)
            items.append(
                WasherPayMonthWorkerItem(
                    washer_id=str(worker_id),
                    full_name=str(row["full_name"]),
                    branch_office_id=str(branch_id),
                    branch_name=str(row["branch_name"]),
                    amount=int(row["amount"]),
                    paid_amount=int(row["paid_amount"]),
                    unpaid_amount=int(row["unpaid_amount"]),
                    ticket_count=int(row["ticket_count"]),
                    days_worked=len(days),
                    days=days,
                ),
            )
        items.sort(key=lambda row: (row.full_name.lower(), row.branch_name.lower(), row.washer_id))

        return WasherPayMonthResponse(
            year=year,
            month=month,
            branch_office_id=str(single_branch.id) if single_branch and single_branch.id else "0",
            branch_name=(
                (single_branch.branch_office or "").strip() or f"Sucursal {single_branch.id}"
                if single_branch
                else "Todas las sucursales"
            ),
            washer_id=str(filter_washer_id) if filter_washer_id is not None else None,
            items=items,
            amount=sum(row.amount for row in items),
            paid_amount=sum(row.paid_amount for row in items),
            unpaid_amount=sum(row.unpaid_amount for row in items),
        )

    def detail_for_washer(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
        date_value: str,
        washer_id: int,
        group_id: int | None = None,
    ) -> WasherPayDetailResponse:
        branch = self._ensure_branch_access(user, branch_office_id)
        day = self._parse_date(date_value)
        if washer_id not in self._branch_washer.list_washer_ids_for_branch(branch_office_id):
            raise WasherPayValidationError("El lavador no pertenece a esta sucursal")

        assignment = self._assignment_for_washer(washer_id)
        is_solo_detail = group_id is None or group_id <= 0
        manual_goal_met = (
            self._get_manual_goal_met(
                branch_office_id=branch_office_id,
                day=day,
                washer_id=washer_id,
            )
            if is_solo_detail
            else False
        )
        amount, _, detail_lines, solo_sales_gross = self._compute_washer_pay(
            branch_office_id=branch_office_id,
            washer_id=washer_id,
            day=day,
            force_goal_met=manual_goal_met,
        )
        ticket_lines = [line for line in detail_lines if line.kind == "ticket"]
        member_ids: list[int] = []
        group_goal_met = False
        if group_id is not None and group_id > 0:
            member_ids = self._group_member_ids_for_pay_day(group_id, day=day)
            line_contexts = self._paid_line_contexts_for_group(
                branch_office_id=branch_office_id,
                group_id=group_id,
                day=day,
            )
            daily_sales_volume = self._group_sales_volume(
                branch_office_id=branch_office_id,
                group_id=group_id,
                day=day,
            )
            goal_amount = self._combined_group_goal_amount(member_ids)
            group_goal_met = self._is_goal_met(
                sales_volume=daily_sales_volume,
                goal_amount=goal_amount,
            )
            detail_lines = self._detail_lines_for_group_contexts(
                line_contexts=line_contexts,
                day=day,
                goal_met=group_goal_met,
            )
            ticket_lines = [line for line in detail_lines if line.kind == "ticket"]
        else:
            line_contexts = self._paid_line_contexts_for_washer(
                branch_office_id=branch_office_id,
                washer_id=washer_id,
                day=day,
            )
            daily_sales_volume = self._washer_sales_volume(line_contexts)
            goal_amount = self._member_goal_amount(assignment)
        solo_goal_met = self._is_goal_met(
            sales_volume=solo_sales_gross,
            goal_amount=self._member_goal_amount(assignment),
        )
        effective_solo_goal_met = solo_goal_met or manual_goal_met
        goal_met = (
            group_goal_met
            if group_id is not None and group_id > 0
            else self._is_goal_met(
                sales_volume=daily_sales_volume,
                goal_amount=goal_amount,
            )
            or manual_goal_met
        )

        is_sunday = day.weekday() == 6
        base_pct = self._percentage_for_date(assignment, day=day) if assignment else Decimal("0")
        boost_pct = self._goal_percentage_boost(
            assignment,
            day=day,
            goal_met=effective_solo_goal_met,
        )
        effective_pct = base_pct + boost_pct
        base_commission = 0
        boosted_commission = 0
        if group_id is not None and group_id > 0:
            seen_group_lines: set[tuple[int, int]] = set()
            for line, ticket, _line_rows, _line_gross, line_net in self._iter_branch_payable_lines(
                branch_office_id=branch_office_id,
                day=day,
            ):
                if line.washer_daily_group_id != group_id:
                    continue
                key = (ticket.id or 0, line.id or 0)
                if key in seen_group_lines:
                    continue
                seen_group_lines.add(key)
                base_pct_line = self._base_commission_percentage_for_line(
                    line,
                    day=day,
                    group_member_ids=member_ids,
                )
                avg_pct_line, _, _ = self._commission_percentage_for_line(
                    line,
                    day=day,
                    goal_met=group_goal_met,
                    group_member_ids=member_ids,
                )
                base_commission += self._line_sales_credit(line_net, base_pct_line)
                boosted_commission += self._line_sales_credit(line_net, avg_pct_line)
        else:
            for ctx in line_contexts:
                base_pct_line = self._base_commission_percentage_for_line(
                    ctx.line,
                    day=day,
                    assignment=assignment,
                )
                avg_pct_line, _, _ = self._commission_percentage_for_line(
                    ctx.line,
                    day=day,
                    goal_met=effective_solo_goal_met,
                    assignment=assignment,
                )
                base_commission += self._line_sales_credit(ctx.full_line_net, base_pct_line)
                boosted_commission += self._line_sales_credit(ctx.full_line_net, avg_pct_line)
        goal_bonus = (
            max(0, boosted_commission - base_commission)
            if goal_met and boosted_commission > base_commission
            else 0
        )
        commission_total = base_commission

        applied_label = (
            "Porcentaje domingo (%)"
            if is_sunday
            else "Porcentaje aplicado hoy"
        )
        applied_raw = self._format_percentage_display(effective_pct)
        if group_id is not None and group_id > 0:
            member_pcts = [
                self._format_percentage_display(
                    self._effective_percentage(
                        assignment_row,
                        day=day,
                        goal_met=group_goal_met,
                    ),
                )
                for member_id in member_ids
                if (assignment_row := self._assignment_for_washer(member_id)) is not None
            ]
            applied_raw = self._format_group_applied_percentage(member_pcts) or applied_raw
            if group_goal_met and not is_sunday:
                applied_label = "Porcentaje aplicado hoy (base + meta)"
        elif boost_pct > 0 and not is_sunday:
            applied_label = "Porcentaje aplicado hoy (base + meta)"

        if group_id is not None and group_id > 0:
            _ef_gross, card_gross, gross_total = self._group_sales_gross_by_payment(
                branch_office_id=branch_office_id,
                group_id=group_id,
                day=day,
            )
            breakdown_pct = self._group_average_effective_pct(
                member_ids=member_ids,
                day=day,
                goal_met=group_goal_met,
            )
            is_group_breakdown = True
            has_service_override = any(
                self._service_washer_percentage(ctx.line) > 0 for ctx in line_contexts
            )
        else:
            _ef_gross, card_gross, gross_total = self._washer_sales_gross_by_payment(
                line_contexts,
            )
            breakdown_pct = effective_pct
            is_group_breakdown = False
            has_service_override = any(
                self._service_washer_percentage(ctx.line) > 0 for ctx in line_contexts
            )

        if has_service_override:
            line_total = self._apply_coin_round(sum(line.amount for line in ticket_lines))
            pay_breakdown = [
                WasherPayBreakdownRow(
                    label="Total cobrado (bruto)" if not is_group_breakdown else "Total del Grupo",
                    amount=gross_total,
                ),
                WasherPayBreakdownRow(label="Tarjeta (bruto)", amount=card_gross),
                WasherPayBreakdownRow(
                    label="Comisión (por servicio / % del lavador)",
                    amount=line_total,
                ),
                WasherPayBreakdownRow(
                    label="Total a pagar por el grupo" if is_group_breakdown else "Total a pagar",
                    amount=line_total,
                    emphasis=True,
                ),
            ]
            breakdown_amount = line_total
        else:
            pay_breakdown, breakdown_amount = self._build_pay_breakdown(
                gross_total=gross_total,
                card_gross=card_gross,
                effective_pct=breakdown_pct,
                is_group=is_group_breakdown,
            )
        amount = breakdown_amount

        if has_service_override and any(
            line.percentage_scope == "service" for line in ticket_lines
        ):
            applied_label = "Porcentaje por servicio (y del lavador si aplica)"
            service_pcts = [
                (line.percentage or "").strip()
                for line in ticket_lines
                if line.percentage_scope == "service" and (line.percentage or "").strip()
            ]
            if len(set(service_pcts)) == 1:
                applied_raw = service_pcts[0]
            elif service_pcts:
                applied_raw = "varios"

        if group_id is not None and group_id > 0:
            pay_efectivo, pay_card, pay_total = self._group_pay_by_payment(
                branch_office_id=branch_office_id,
                group_id=group_id,
                day=day,
            )
        else:
            pay_efectivo, pay_card, pay_total = self._washer_pay_by_payment(
                line_contexts,
                ticket_lines,
            )
        pay_efectivo, pay_card, pay_total = self._reconcile_pay_split_to_target(
            pay_efectivo,
            pay_card,
            amount,
        )

        if group_id is not None and group_id > 0:
            _, _, daily_sales_net = self._group_sales_liquid_by_payment(
                branch_office_id=branch_office_id,
                group_id=group_id,
                day=day,
            )
        else:
            _, _, daily_sales_net = self._washer_sales_liquid_by_payment(
                line_contexts,
            )

        group_member_items: list[WasherPayGroupMemberItem] = []
        if group_id is not None and group_id > 0:
            member_ids = self._washer_groups.member_ids_for_group_on_date(
                group_id,
                day=day,
            )
            member_count = len(member_ids)
            if amount > 0 and member_count > 0:
                per_member = round_money(Decimal(amount) / Decimal(member_count))
                for member_id in member_ids:
                    group_member_items.append(
                        WasherPayGroupMemberItem(
                            washer_id=str(member_id),
                            full_name=self._washer_full_name(member_id),
                            amount=per_member,
                        ),
                    )

        return WasherPayDetailResponse(
            washer_id=str(washer_id),
            full_name=self._washer_full_name(washer_id),
            branch_office_id=str(branch_office_id),
            branch_name=branch.branch_office,
            date=day.isoformat(),
            daily_sales=daily_sales_volume,
            daily_sales_net=daily_sales_net,
            daily_goal=(
                str(goal_amount) if goal_amount > 0 else None
            )
            if group_id is not None and group_id > 0
            else (assignment.daily_goal if assignment else None),
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
            sales_efectivo_net=pay_efectivo,
            sales_card_net=pay_card,
            sales_total_net=pay_total,
            sales_liquid_total=pay_total,
            items=detail_lines,
            amount=amount,
            group_member_items=group_member_items,
            payment_status=self._get_payment_status(
                branch_office_id=branch_office_id,
                day=day,
                washer_id=washer_id,
            ),
            pay_breakdown=pay_breakdown,
            manual_goal_met=manual_goal_met,
        )
