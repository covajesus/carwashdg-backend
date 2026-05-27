from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import business_local_date, business_now, business_today, datetime_to_iso

from app.core.pricing import round_money, split_mixed_payment_totals, ticket_totals_from_subtotal
from app.core.ticket_total import parse_ticket_total, sync_ticket_total
from app.models.branch_office import BranchOffice
from app.models.customer import Customer
from app.models.status import Status
from app.models.ticket import Ticket
from app.schemas.ticket import (
    TicketCheckout,
    BranchEarningsByDateItem,
    BranchEarningsItem,
    TicketCreate,
    TicketCreateResponse,
    TicketDetailResponse,
    TicketEarningsByBranchDateResponse,
    TicketEarningsByBranchResponse,
    TicketListItem,
    TicketPublic,
    TicketSummaryResponse,
    TicketUpdate,
)
from app.schemas.user import UserPublic
from app.services.raffle_service import RaffleService, RaffleValidationError
from app.services.collection_service import CollectionService, empty_earnings_bucket
from app.services.ticket_line_service import TicketLineService, TicketLineValidationError
from app.core.branch_scope import branch_scope_for_user


class TicketNotFoundError(Exception):
    pass


class TicketValidationError(Exception):
    pass


PAYMENT_TYPE_EFECTIVO = 1
PAYMENT_TYPE_TRANSBANK = 2
PAYMENT_TYPE_MIXED = 3

PAID_PAYMENT_TYPE_IDS = frozenset(
    {PAYMENT_TYPE_EFECTIVO, PAYMENT_TYPE_TRANSBANK, PAYMENT_TYPE_MIXED},
)
TICKET_STATUS_PAID_ID = 1
TICKET_STATUS_NOT_PAID_ID = 3


class TicketService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._lines = TicketLineService(db)
        self._raffles = RaffleService(db)

    def _washer_groups_service(self):
        from app.services.washer_daily_group_service import WasherDailyGroupService

        return WasherDailyGroupService(self.db)

    def _validate_ticket_group(self, group_id: int) -> None:
        group = self._washer_groups_service().get_active_group(
            group_id,
            group_date=business_today(),
        )
        if group is None:
            raise TicketValidationError("El grupo no existe o no corresponde al día actual")
        members = self._washer_groups_service().member_ids_for_group(group_id)
        if not members:
            raise TicketValidationError("El grupo no tiene lavadores")

    @staticmethod
    def _now() -> datetime:
        return business_now()

    def to_public(self, row: Ticket) -> TicketPublic:
        return TicketPublic(
            id=str(row.id),
            customer_id=str(row.customer_id) if row.customer_id else None,
            car_type_id=str(row.car_type_id) if row.car_type_id else None,
            license_plate_id=row.license_plate_id,
            photo_url=row.photo_url,
            payment_type_id=str(row.payment_type_id) if row.payment_type_id else None,
            status_id=str(row.status_id) if row.status_id else None,
            tip=row.tip,
            added_date=row.added_date,
            updated_date=row.updated_date,
            deleted_date=row.deleted_date,
        )

    def _active_filter(self, stmt):
        return stmt.where(Ticket.deleted_date.is_(None))

    def _status_text(self, status_id: int | None) -> str:
        if status_id is None:
            return "—"
        row = self.db.get(Status, status_id)
        return row.status if row and row.is_active else "—"

    @staticmethod
    def _status_label_is_open(status_text: str) -> bool:
        normalized = status_text.strip().lower()
        if not normalized or normalized == "—":
            return True
        if any(x in normalized for x in ("no pagado", "no pagó", "no pago", "cancel")):
            return False
        if any(
            x in normalized
            for x in ("pagad", "cobrad", "cerrad", "complet", "finaliz")
        ):
            return False
        return True

    def _resolve_closed_status_id(self) -> int | None:
        paid = self.db.get(Status, TICKET_STATUS_PAID_ID)
        if paid is not None and paid.is_active:
            return TICKET_STATUS_PAID_ID
        rows = self.db.scalars(
            select(Status)
            .where(Status.deleted_date.is_(None))
            .order_by(Status.id.asc()),
        ).all()
        for row in rows:
            text = row.status.strip().lower()
            if any(x in text for x in ("no pagado", "no pagó", "no pago", "en proceso", "pendiente")):
                continue
            if any(
                x in text
                for x in ("pagad", "cobrad", "cerrad", "complet", "finaliz")
            ):
                return row.id
        return None

    def _list_status_for_ticket(self, row: Ticket) -> str:
        status_text = self._status_text(row.status_id)
        if row.status_id == TICKET_STATUS_PAID_ID:
            paid = self.db.get(Status, TICKET_STATUS_PAID_ID)
            if paid and paid.is_active:
                return paid.status
        if row.payment_type_id in PAID_PAYMENT_TYPE_IDS:
            if self._status_label_is_open(status_text):
                closed_id = self._resolve_closed_status_id()
                if closed_id is not None:
                    closed_row = self.db.get(Status, closed_id)
                    if closed_row and closed_row.is_active:
                        return closed_row.status
                return "Pagado"
        return status_text

    def ticket_is_collected(self, row: Ticket) -> bool:
        """Paid/collected ticket: checkout payment or catalog status Pagado (id=1)."""
        if row.payment_type_id in PAID_PAYMENT_TYPE_IDS:
            return True
        if row.status_id == TICKET_STATUS_PAID_ID:
            return True
        if row.status_id == TICKET_STATUS_NOT_PAID_ID:
            return False
        status_text = self._status_text(row.status_id).strip().lower()
        if any(x in status_text for x in ("no pagado", "no pagó", "no pago", "cancel")):
            return False
        return any(
            x in status_text
            for x in ("pagad", "cobrad", "cerrad", "complet", "finaliz")
        )

    def ticket_is_in_process(self, row: Ticket) -> bool:
        """Open ticket still being washed or awaiting payment (excludes paid and not-paid)."""
        if self.ticket_is_collected(row):
            return False
        if row.status_id == TICKET_STATUS_NOT_PAID_ID:
            return False
        status_text = self._status_text(row.status_id).strip().lower()
        if any(x in status_text for x in ("no pagado", "no pagó", "no pago", "cancel")):
            return False
        return self._status_label_is_open(status_text)

    def ticket_revenue_day(self, row: Ticket) -> date | None:
        """Business day for earnings and washer pay (checkout/payment day when collected)."""
        if row.payment_type_id in PAID_PAYMENT_TYPE_IDS:
            if row.updated_date is not None:
                return business_local_date(row.updated_date)
        if self.ticket_is_collected(row) and row.updated_date is not None:
            return business_local_date(row.updated_date)
        return business_local_date(row.added_date)

    def ticket_eligible_for_washer_pay(self, row: Ticket) -> bool:
        """Washer commission applies to collected/paid tickets only."""
        return self.ticket_is_collected(row)

    def _customer_name(self, ticket: Ticket) -> str:
        if ticket.customer_id:
            customer = self.db.get(Customer, ticket.customer_id)
            if customer and customer.is_active:
                return customer.full_name
        if ticket.license_plate_id:
            customer = self.db.scalars(
                select(Customer).where(
                    Customer.deleted_date.is_(None),
                    Customer.license_plate_id == ticket.license_plate_id,
                ),
            ).first()
            if customer:
                return customer.full_name
            return ticket.license_plate_id
        return "—"

    @staticmethod
    def _branch_scope_for_user(user: UserPublic) -> int | None:
        return branch_scope_for_user(user)

    def _ticket_ids_for_branch_subquery(self, branch_office_id: int):
        from app.models.branch_office_washer import BranchOfficeWasher
        from app.models.ticket_branch_office_service import TicketBranchOfficeService
        from app.models.washer_daily_group import WasherDailyGroup

        washer_ticket_ids = (
            select(TicketBranchOfficeService.ticket_id)
            .join(
                BranchOfficeWasher,
                TicketBranchOfficeService.washer_id == BranchOfficeWasher.washer_id,
            )
            .where(
                BranchOfficeWasher.branch_office_id == branch_office_id,
                BranchOfficeWasher.deleted_date.is_(None),
                TicketBranchOfficeService.deleted_date.is_(None),
                TicketBranchOfficeService.ticket_id.isnot(None),
                TicketBranchOfficeService.washer_id.isnot(None),
            )
        )
        group_ticket_ids = (
            select(TicketBranchOfficeService.ticket_id)
            .join(
                WasherDailyGroup,
                TicketBranchOfficeService.washer_daily_group_id == WasherDailyGroup.id,
            )
            .where(
                WasherDailyGroup.branch_office_id == branch_office_id,
                WasherDailyGroup.deleted_date.is_(None),
                TicketBranchOfficeService.deleted_date.is_(None),
                TicketBranchOfficeService.ticket_id.isnot(None),
                TicketBranchOfficeService.washer_daily_group_id.isnot(None),
            )
        )
        return washer_ticket_ids.union(group_ticket_ids)

    def _list_stmt_for_user(self, user: UserPublic):
        stmt = self._active_filter(select(Ticket)).order_by(Ticket.added_date.desc())
        branch_scope = self._branch_scope_for_user(user)
        if branch_scope is None:
            return stmt
        if branch_scope == 0:
            return stmt.where(Ticket.id < 0)
        return stmt.where(Ticket.id.in_(self._ticket_ids_for_branch_subquery(branch_scope)))

    def _ticket_matches_branch(self, ticket_id: int, branch_office_id: int) -> bool:
        if self._branch_id_for_ticket(ticket_id) == str(branch_office_id):
            return True
        from app.models.branch_office_washer import BranchOfficeWasher
        from app.models.ticket_branch_office_service import TicketBranchOfficeService

        stmt = (
            select(TicketBranchOfficeService.id)
            .join(
                BranchOfficeWasher,
                TicketBranchOfficeService.washer_id == BranchOfficeWasher.washer_id,
            )
            .where(
                TicketBranchOfficeService.ticket_id == ticket_id,
                TicketBranchOfficeService.deleted_date.is_(None),
                BranchOfficeWasher.branch_office_id == branch_office_id,
                BranchOfficeWasher.deleted_date.is_(None),
            )
            .limit(1)
        )
        if self.db.scalars(stmt).first() is not None:
            return True

        from app.models.washer_daily_group import WasherDailyGroup

        group_stmt = (
            select(TicketBranchOfficeService.id)
            .join(
                WasherDailyGroup,
                TicketBranchOfficeService.washer_daily_group_id == WasherDailyGroup.id,
            )
            .where(
                TicketBranchOfficeService.ticket_id == ticket_id,
                TicketBranchOfficeService.deleted_date.is_(None),
                WasherDailyGroup.branch_office_id == branch_office_id,
                WasherDailyGroup.deleted_date.is_(None),
            )
            .limit(1)
        )
        return self.db.scalars(group_stmt).first() is not None

    def _get_visible_ticket(self, ticket_id: int, user: UserPublic) -> Ticket:
        row = self.db.get(Ticket, ticket_id)
        if row is None or not row.is_active:
            raise TicketNotFoundError()
        branch_scope = self._branch_scope_for_user(user)
        if branch_scope is None:
            return row
        if branch_scope == 0 or not self._ticket_matches_branch(ticket_id, branch_scope):
            raise TicketNotFoundError()
        return row

    def _branch_id_for_ticket(self, ticket_id: int) -> str:
        branch_id = self._resolve_branch_office_id_for_ticket(ticket_id)
        return str(branch_id) if branch_id is not None else ""

    def _resolve_branch_office_id_for_ticket(self, ticket_id: int) -> int | None:
        from app.models.branch_office_washer import BranchOfficeWasher
        from app.models.ticket_branch_office_service import TicketBranchOfficeService

        washer_branch = self.db.scalars(
            select(BranchOfficeWasher.branch_office_id)
            .join(
                TicketBranchOfficeService,
                TicketBranchOfficeService.washer_id == BranchOfficeWasher.washer_id,
            )
            .where(
                TicketBranchOfficeService.ticket_id == ticket_id,
                TicketBranchOfficeService.deleted_date.is_(None),
                TicketBranchOfficeService.washer_id.isnot(None),
                BranchOfficeWasher.deleted_date.is_(None),
                BranchOfficeWasher.branch_office_id.isnot(None),
            )
            .limit(1),
        ).first()
        if washer_branch is not None:
            return int(washer_branch)

        from app.models.washer_daily_group import WasherDailyGroup

        group_branch = self.db.scalars(
            select(WasherDailyGroup.branch_office_id)
            .join(
                TicketBranchOfficeService,
                TicketBranchOfficeService.washer_daily_group_id == WasherDailyGroup.id,
            )
            .where(
                TicketBranchOfficeService.ticket_id == ticket_id,
                TicketBranchOfficeService.deleted_date.is_(None),
                WasherDailyGroup.deleted_date.is_(None),
            )
            .limit(1),
        ).first()
        if group_branch is not None:
            return int(group_branch)
        return None

    def _branch_name(self, ticket_id: int) -> str:
        branch_id = self._branch_id_for_ticket(ticket_id)
        if not branch_id:
            return "—"
        branch = self.db.get(BranchOffice, int(branch_id))
        return branch.branch_office if branch else "—"

    @staticmethod
    def _stored_pricing(row: Ticket) -> dict[str, int] | None:
        subtotal = parse_ticket_total(row.subtotal)
        total = parse_ticket_total(row.total)
        if subtotal is None or total is None:
            return None
        tax = parse_ticket_total(row.tax) or 0
        return {"subtotal": subtotal, "iva": tax, "tax": tax, "total": total}

    @staticmethod
    def _payment_split_amounts(row: Ticket) -> tuple[int, int]:
        total = parse_ticket_total(row.total) or 0
        efectivo = int(row.payment_efectivo_amount or 0)
        transbank = int(row.payment_transbank_amount or 0)
        if efectivo > 0 or transbank > 0:
            return efectivo, transbank
        if row.payment_type_id == PAYMENT_TYPE_EFECTIVO:
            return total, 0
        if row.payment_type_id == PAYMENT_TYPE_TRANSBANK:
            return 0, total
        if row.payment_type_id == PAYMENT_TYPE_MIXED and total > 0:
            return efectivo, transbank
        return 0, 0

    @staticmethod
    def _ticket_has_payment(row: Ticket) -> bool:
        return row.payment_type_id in PAID_PAYMENT_TYPE_IDS

    @staticmethod
    def _infer_apply_iva_from_row(row: Ticket) -> bool:
        if row.payment_type_id in (PAYMENT_TYPE_TRANSBANK, PAYMENT_TYPE_MIXED):
            return True
        _, transbank = TicketService._payment_split_amounts(row)
        if transbank > 0:
            return True
        tax = parse_ticket_total(row.tax)
        if tax is not None:
            return tax > 0
        return False

    def _ticket_pricing(self, ticket_id: int, row: Ticket | None = None) -> dict[str, int]:
        if row is not None:
            stored = self._stored_pricing(row)
            if stored is not None:
                return stored
        ticket_row = row if row is not None else self.db.get(Ticket, ticket_id)
        lines = self._lines.list_lines_for_ticket(ticket_id)
        gross = sum(line.price for line in lines)
        if ticket_row is not None and ticket_row.payment_type_id == PAYMENT_TYPE_MIXED:
            efectivo, transbank = self._payment_split_amounts(ticket_row)
            if efectivo > 0 and transbank > 0:
                return split_mixed_payment_totals(efectivo, transbank)
        apply_iva = (
            self._infer_apply_iva_from_row(ticket_row)
            if ticket_row is not None
            else False
        )
        return ticket_totals_from_subtotal(gross, apply_iva=apply_iva)

    @staticmethod
    def _resolve_apply_iva(data: TicketCreate) -> bool:
        if data.payment_type_id == PAYMENT_TYPE_TRANSBANK:
            return True
        if data.needs_tax_receipt is not None:
            return data.needs_tax_receipt
        return False

    def _to_list_item(
        self,
        row: Ticket,
        *,
        assignee: tuple[str, str, int | None, int | None] | None = None,
    ) -> TicketListItem:
        pricing = self._ticket_pricing(row.id, row)
        created = datetime_to_iso(row.added_date) or ""
        assignee_kind: str | None = None
        assignee_label: str | None = None
        assignee_washer_id: str | None = None
        assignee_group_id: str | None = None
        if assignee is not None:
            assignee_kind, assignee_label, washer_id, group_id = assignee
            if washer_id is not None:
                assignee_washer_id = str(washer_id)
            if group_id is not None:
                assignee_group_id = str(group_id)
        revenue_day = self.ticket_revenue_day(row)
        efectivo_amount, transbank_amount = self._payment_split_amounts(row)
        return TicketListItem(
            id=str(row.id),
            folio=f"T-{row.id}",
            branchId=self._branch_id_for_ticket(row.id),
            vehicleTypeId=str(row.car_type_id or ""),
            licensePlate=row.license_plate_id or "",
            total=pricing["total"],
            status=self._list_status_for_ticket(row),
            createdAt=created,
            customer_name=self._customer_name(row),
            paymentTypeId=(
                str(row.payment_type_id) if row.payment_type_id else None
            ),
            statusId=str(row.status_id) if row.status_id is not None else None,
            assigneeKind=assignee_kind,
            assigneeLabel=assignee_label,
            assigneeWasherId=assignee_washer_id,
            assigneeGroupId=assignee_group_id,
            revenueDay=revenue_day.isoformat() if revenue_day is not None else None,
            paymentEfectivoAmount=efectivo_amount if efectivo_amount > 0 else None,
            paymentTransbankAmount=transbank_amount if transbank_amount > 0 else None,
        )

    @staticmethod
    def _list_item_matches_revenue_day(item: TicketListItem, day: date) -> bool:
        rd = item.revenueDay
        if not rd:
            return False
        return rd.strip()[:10] == day.isoformat()

    def list_for_user(
        self,
        user: UserPublic,
        *,
        revenue_day: date | None = None,
    ) -> list[TicketListItem]:
        stmt = self._list_stmt_for_user(user)
        rows = self.db.scalars(stmt).all()
        ticket_ids = [int(row.id) for row in rows if row.id is not None]
        assignees = self._lines.assignee_labels_for_ticket_ids(ticket_ids)
        items = [
            self._to_list_item(row, assignee=assignees.get(int(row.id)) if row.id else None)
            for row in rows
        ]

        scope = self._branch_scope_for_user(user)
        if scope is not None:
            effective = business_today()
            return [i for i in items if self._list_item_matches_revenue_day(i, effective)]

        if revenue_day is not None:
            return [i for i in items if self._list_item_matches_revenue_day(i, revenue_day)]

        return items

    def summary_for_user(self, user: UserPublic) -> TicketSummaryResponse:
        stmt = self._list_stmt_for_user(user)
        rows = self.db.scalars(stmt).all()
        total_earnings = 0
        ticket_count = 0
        in_process_count = 0
        paid_count = 0
        for row in rows:
            ticket_count += 1
            if self.ticket_is_collected(row):
                paid_count += 1
                if row.id is not None:
                    pricing = self._ticket_pricing(row.id, row)
                    total_earnings += pricing["total"]
            elif self.ticket_is_in_process(row):
                in_process_count += 1
        return TicketSummaryResponse(
            totalEarnings=total_earnings,
            ticketCount=ticket_count,
            inProcessCount=in_process_count,
            paidCount=paid_count,
        )

    def ticket_earnings_date_buckets(
        self,
        user: UserPublic,
        branch_office_id: int,
    ) -> dict[str, dict[str, int]]:
        scope = self._branch_scope_for_user(user)
        if scope == 0:
            raise TicketValidationError("You have no branch assigned")

        if scope is not None and scope != branch_office_id:
            raise TicketValidationError("You cannot view another branch")

        if branch_office_id != 0:
            branch = self.db.get(BranchOffice, branch_office_id)
            if branch is None or not branch.is_active:
                raise TicketValidationError("Branch not found")

        buckets: dict[str, dict[str, int]] = defaultdict(empty_earnings_bucket)

        stmt = self._list_stmt_for_user(user)
        for row in self.db.scalars(stmt).all():
            if row.id is None:
                continue
            resolved_branch = self._resolve_branch_office_id_for_ticket(row.id)
            bucket_key = resolved_branch if resolved_branch is not None else 0
            if bucket_key != branch_office_id:
                continue
            if not self.ticket_is_collected(row):
                continue

            revenue_day = self.ticket_revenue_day(row)
            day_key = revenue_day.isoformat() if revenue_day is not None else "sin-fecha"

            pricing = self._ticket_pricing(row.id, row)
            bucket = buckets[day_key]
            bucket["ticket_count"] += 1
            bucket["subtotal"] += pricing["subtotal"]
            bucket["iva"] += pricing["iva"]
            bucket["total"] += pricing["total"]

        return dict(buckets)

    def earnings_by_branch(
        self,
        user: UserPublic,
        *,
        branch_office_id: int | None = None,
    ) -> TicketEarningsByBranchResponse:
        scope = self._branch_scope_for_user(user)
        if scope == 0:
            return TicketEarningsByBranchResponse(
                items=[],
                subtotal=0,
                iva=0,
                total=0,
                ticket_count=0,
            )

        filter_branch_id: int | None
        if scope is not None:
            filter_branch_id = scope
        else:
            filter_branch_id = branch_office_id

        if filter_branch_id is not None:
            branch = self.db.get(BranchOffice, filter_branch_id)
            if branch is None or not branch.is_active:
                raise TicketValidationError("Branch not found")

        buckets: dict[int, dict[str, int]] = defaultdict(
            lambda: {"ticket_count": 0, "subtotal": 0, "iva": 0, "total": 0},
        )

        stmt = self._list_stmt_for_user(user)
        for row in self.db.scalars(stmt).all():
            if row.id is None:
                continue
            resolved_branch = self._resolve_branch_office_id_for_ticket(row.id)
            bucket_key = resolved_branch if resolved_branch is not None else 0
            if filter_branch_id is not None and bucket_key != filter_branch_id:
                continue
            if not self.ticket_is_collected(row):
                continue

            pricing = self._ticket_pricing(row.id, row)
            bucket = buckets[bucket_key]
            bucket["ticket_count"] += 1
            bucket["subtotal"] += pricing["subtotal"]
            bucket["iva"] += pricing["iva"]
            bucket["total"] += pricing["total"]

        CollectionService(self.db).merge_into_branch_buckets(
            buckets,
            branch_office_id=filter_branch_id,
        )

        items: list[BranchEarningsItem] = []
        for branch_key, totals in buckets.items():
            if branch_key == 0:
                branch_name = "Sin sucursal"
                branch_id_str = "0"
            else:
                branch_row = self.db.get(BranchOffice, branch_key)
                branch_name = branch_row.branch_office if branch_row else f"Sucursal #{branch_key}"
                branch_id_str = str(branch_key)
            items.append(
                BranchEarningsItem(
                    branch_office_id=branch_id_str,
                    branch_name=branch_name,
                    ticket_count=totals["ticket_count"],
                    subtotal=totals["subtotal"],
                    iva=totals["iva"],
                    total=totals["total"],
                ),
            )

        items.sort(key=lambda row: row.branch_name.lower())

        return TicketEarningsByBranchResponse(
            items=items,
            subtotal=sum(row.subtotal for row in items),
            iva=sum(row.iva for row in items),
            total=sum(row.total for row in items),
            ticket_count=sum(row.ticket_count for row in items),
        )

    def earnings_by_branch_by_date(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
    ) -> TicketEarningsByBranchDateResponse:
        scope = self._branch_scope_for_user(user)
        if scope == 0:
            raise TicketValidationError("You have no branch assigned")

        if scope is not None and scope != branch_office_id:
            raise TicketValidationError("You cannot view another branch")

        if branch_office_id == 0:
            branch_name = "Sin sucursal"
        else:
            branch = self.db.get(BranchOffice, branch_office_id)
            if branch is None or not branch.is_active:
                raise TicketValidationError("Branch not found")
            branch_name = branch.branch_office

        buckets = self.ticket_earnings_date_buckets(user, branch_office_id)
        CollectionService(self.db).merge_into_date_buckets(buckets, branch_office_id)

        date_items: list[BranchEarningsByDateItem] = []
        for day_key, totals in buckets.items():
            date_items.append(
                BranchEarningsByDateItem(
                    date=day_key,
                    ticket_count=totals["ticket_count"],
                    subtotal=totals["subtotal"],
                    iva=totals["iva"],
                    total=totals["total"],
                ),
            )

        date_items.sort(key=lambda row: row.date, reverse=True)

        return TicketEarningsByBranchDateResponse(
            branch_office_id=str(branch_office_id),
            branch_name=branch_name,
            items=date_items,
            subtotal=sum(row.subtotal for row in date_items),
            iva=sum(row.iva for row in date_items),
            total=sum(row.total for row in date_items),
            ticket_count=sum(row.ticket_count for row in date_items),
        )

    def get_detail(self, ticket_id: int, user: UserPublic) -> TicketDetailResponse:
        row = self._get_visible_ticket(ticket_id, user)
        item = self._to_list_item(row)
        lines = self._lines.list_lines_for_ticket(ticket_id)
        pricing = self._ticket_pricing(ticket_id, row)
        return TicketDetailResponse(
            ticket=item,
            customer_name=self._customer_name(row),
            branch_name=self._branch_name(ticket_id),
            services=lines,
            subtotal=pricing["subtotal"],
            iva=pricing["iva"],
            total=pricing["total"],
        )

    def get_by_id(self, ticket_id: int, user: UserPublic) -> TicketPublic:
        row = self._get_visible_ticket(ticket_id, user)
        return self.to_public(row)

    def create(self, data: TicketCreate) -> TicketCreateResponse:
        """Crear ticket sin cobro: el pago se confirma después (checkout / PayTicket)."""
        if data.washer_id is not None and data.washer_daily_group_id is not None:
            raise TicketValidationError("Seleccione un lavador o un grupo, no ambos")
        if data.washer_daily_group_id is not None:
            self._validate_ticket_group(data.washer_daily_group_id)

        active_raffle = self._raffles.get_current_active_raffle()
        if active_raffle is not None and not data.customer_id:
            raise TicketValidationError(
                "Hay una rifa activa: registre o seleccione un cliente para participar",
            )

        now = self._now()
        row = Ticket(
            customer_id=data.customer_id,
            car_type_id=data.car_type_id,
            license_plate_id=(data.license_plate_id or "").strip() or None,
            photo_url=(data.photo_url or "").strip() or None,
            payment_type_id=None,
            status_id=data.status_id,
            tip=(data.tip or "").strip() or None,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )

        service_lines = [
            (
                line.service_id,
                line.total,
                (line.additional_service or "").strip() or None,
            )
            for line in data.service_lines
        ]

        try:
            self.db.add(row)
            self.db.flush()

            if not row.id:
                raise TicketValidationError("No se pudo crear el ticket en la tabla tickets")

            if service_lines:
                self._lines.create_lines_for_ticket(
                    ticket_id=row.id,
                    lines=service_lines,
                    washer_id=data.washer_id,
                    washer_daily_group_id=data.washer_daily_group_id,
                )
            elif data.washer_id is not None:
                self._lines.assign_washer_to_ticket(
                    row.id,
                    data.washer_id,
                    commit=False,
                )
            elif data.washer_daily_group_id is not None:
                self._validate_ticket_group(data.washer_daily_group_id)
                self._lines.assign_washer_to_ticket(
                    row.id,
                    None,
                    washer_daily_group_id=data.washer_daily_group_id,
                    commit=False,
                )

            self.db.flush()
            apply_iva = self._resolve_apply_iva(data)
            sync_ticket_total(self.db, row.id, apply_iva=apply_iva)

            if (
                parse_ticket_total(row.total) in (None, 0)
                and data.total is not None
                and round_money(data.total) > 0
            ):
                row.subtotal = str(round_money(data.subtotal or 0))
                row.tax = str(round_money(data.tax or 0))
                row.total = str(round_money(data.total))

            self.db.commit()
            self.db.refresh(row)
            return TicketCreateResponse(
                item=self.to_public(row),
                raffle=None,
            )
        except TicketLineValidationError as exc:
            self.db.rollback()
            raise TicketValidationError(str(exc)) from exc
        except TicketValidationError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def checkout(
        self,
        ticket_id: int,
        data: TicketCheckout,
        user: UserPublic,
    ) -> TicketCreateResponse:
        row = self._get_visible_ticket(ticket_id, user)
        if row.payment_type_id in PAID_PAYMENT_TYPE_IDS:
            raise TicketValidationError("Este ticket ya fue cobrado")

        active_raffle = self._raffles.get_current_active_raffle()
        if active_raffle is not None and not row.customer_id:
            raise TicketValidationError(
                "Hay una rifa activa: el ticket debe tener un cliente registrado",
            )

        total = round_money(data.total)
        split_efectivo = data.payment_efectivo_amount
        split_transbank = data.payment_transbank_amount
        has_split = split_efectivo is not None or split_transbank is not None

        if has_split:
            efectivo = round_money(split_efectivo or 0)
            transbank = round_money(split_transbank or 0)
            if efectivo <= 0 or transbank <= 0:
                raise TicketValidationError(
                    "Indique un monto mayor a 0 en efectivo y en Transbank",
                )
            mixed_pricing = split_mixed_payment_totals(efectivo, transbank)
            if mixed_pricing["total"] != total:
                raise TicketValidationError(
                    "Efectivo + Transbank debe sumar el total del ticket",
                )
            row.payment_type_id = PAYMENT_TYPE_MIXED
            row.payment_efectivo_amount = efectivo
            row.payment_transbank_amount = transbank
            row.subtotal = str(mixed_pricing["subtotal"])
            row.tax = str(mixed_pricing["tax"])
            row.total = str(mixed_pricing["total"])
        else:
            if data.payment_type_id not in (PAYMENT_TYPE_EFECTIVO, PAYMENT_TYPE_TRANSBANK):
                raise TicketValidationError("Seleccione el método de pago")
            row.payment_type_id = data.payment_type_id
            if data.payment_type_id == PAYMENT_TYPE_EFECTIVO:
                row.payment_efectivo_amount = total
                row.payment_transbank_amount = 0
            else:
                row.payment_efectivo_amount = 0
                row.payment_transbank_amount = total

        if not has_split:
            row.subtotal = str(round_money(data.subtotal))
            row.tax = str(round_money(data.tax))
            row.total = str(total)
        closed_status_id = self._resolve_closed_status_id()
        if closed_status_id is not None:
            row.status_id = closed_status_id
        row.updated_date = self._now()

        raffle_assignment = None
        if active_raffle is not None and row.customer_id:
            try:
                raffle_assignment = self._raffles.assign_number_for_customer(
                    active_raffle.id,
                    row.customer_id,
                    ticket_id=row.id,
                    commit=False,
                )
            except RaffleValidationError as exc:
                self.db.rollback()
                raise TicketValidationError(str(exc)) from exc

        try:
            self.db.commit()
            self.db.refresh(row)
            return TicketCreateResponse(
                item=self.to_public(row),
                raffle=raffle_assignment,
            )
        except Exception:
            self.db.rollback()
            raise

    def _apply_ticket_gross_amount(self, row: Ticket, gross_amount: int) -> None:
        if row.payment_type_id in PAID_PAYMENT_TYPE_IDS:
            raise TicketValidationError("No se puede cambiar el monto de un ticket ya cobrado")
        gross = round_money(gross_amount)
        if gross <= 0:
            raise TicketValidationError("El monto debe ser un entero mayor a 0")
        apply_iva = self._infer_apply_iva_from_row(row)
        pricing = ticket_totals_from_subtotal(gross, apply_iva=apply_iva)
        row.subtotal = str(pricing["subtotal"])
        row.tax = str(pricing["tax"])
        row.total = str(pricing["total"])

    def update(self, ticket_id: int, data: TicketUpdate, user: UserPublic) -> TicketPublic:
        row = self._get_visible_ticket(ticket_id, user)

        patch = data.model_dump(exclude_unset=True)
        if not patch:
            return self.to_public(row)

        if user.role == "admin":
            allowed = {"gross_amount", "status_id", "washer_id", "washer_daily_group_id"}
            disallowed = set(patch.keys()) - allowed
            if disallowed:
                raise TicketValidationError(
                    "Solo puede modificar el monto, el lavador o el estatus del ticket",
                )
            if row.payment_type_id in PAID_PAYMENT_TYPE_IDS:
                if "gross_amount" in patch:
                    raise TicketValidationError("No se puede cambiar el monto de un ticket ya cobrado")
                if "washer_id" in patch or "washer_daily_group_id" in patch:
                    raise TicketValidationError(
                        "No se puede cambiar el lavador de un ticket ya cobrado",
                    )
            if "gross_amount" in patch:
                self._apply_ticket_gross_amount(row, patch["gross_amount"])
            if "washer_id" in patch or "washer_daily_group_id" in patch:
                washer_id = patch.get("washer_id")
                group_id = patch.get("washer_daily_group_id")
                if washer_id is not None and group_id is not None:
                    raise TicketValidationError("Seleccione un lavador o un grupo, no ambos")
                if washer_id is None and group_id is None:
                    raise TicketValidationError("Seleccione un lavador o un grupo")
                if group_id is not None:
                    self._validate_ticket_group(group_id)
                try:
                    self._lines.reassign_ticket_assignee(
                        ticket_id,
                        washer_id=washer_id,
                        washer_daily_group_id=group_id,
                    )
                except TicketLineValidationError as exc:
                    raise TicketValidationError(str(exc)) from exc
            if "status_id" in patch:
                row.status_id = patch["status_id"]
        elif user.role == "manager":
            disallowed = set(patch.keys()) - {"status_id"}
            if disallowed:
                raise TicketValidationError("No tiene permiso para modificar este ticket")
            if "status_id" in patch:
                row.status_id = patch["status_id"]
        else:
            raise TicketValidationError("No tiene permiso para modificar tickets")

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, ticket_id: int, user: UserPublic) -> None:
        """Elimina el ticket y todas sus líneas en tickets_branch_offices_services (soft delete)."""
        row = self._get_visible_ticket(ticket_id, user)
        now = self._now()
        try:
            self._lines.soft_delete_for_ticket(ticket_id, deleted_at=now)
            row.deleted_date = now
            row.updated_date = now
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
