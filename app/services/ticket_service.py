from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pricing import ticket_totals_from_subtotal
from app.core.ticket_total import parse_ticket_total
from app.models.branch_office import BranchOffice
from app.models.branch_office_service import BranchOfficeService
from app.models.customer import Customer
from app.models.status import Status
from app.models.ticket import Ticket
from app.schemas.ticket import (
    TicketCreate,
    TicketDetailResponse,
    TicketListItem,
    TicketPublic,
    TicketSummaryResponse,
    TicketUpdate,
)
from app.services.ticket_line_service import TicketLineService, TicketLineValidationError


class TicketNotFoundError(Exception):
    pass


class TicketValidationError(Exception):
    pass


PAYMENT_TYPE_EFECTIVO = 1
PAYMENT_TYPE_TRANSBANK = 2


class TicketService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._lines = TicketLineService(db)

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

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

    def _branch_id_for_ticket(self, ticket_id: int) -> str:
        from app.models.ticket_branch_office_service import TicketBranchOfficeService

        line = self.db.scalars(
            select(TicketBranchOfficeService)
            .where(
                TicketBranchOfficeService.ticket_id == ticket_id,
                TicketBranchOfficeService.deleted_date.is_(None),
            )
            .limit(1),
        ).first()
        if line is None or line.branch_office_service_id is None:
            return ""
        bos = self.db.get(BranchOfficeService, line.branch_office_service_id)
        return str(bos.branch_office_id) if bos and bos.branch_office_id else ""

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

    def _ticket_pricing(self, ticket_id: int, row: Ticket | None = None) -> dict[str, int]:
        if row is not None:
            stored = self._stored_pricing(row)
            if stored is not None:
                return stored
        lines = self._lines.list_lines_for_ticket(ticket_id)
        subtotal = sum(line.price for line in lines)
        return ticket_totals_from_subtotal(subtotal, apply_iva=True)

    @staticmethod
    def _resolve_apply_iva(data: TicketCreate) -> bool:
        if data.payment_type_id == PAYMENT_TYPE_TRANSBANK:
            return True
        if data.needs_tax_receipt is not None:
            return data.needs_tax_receipt
        return False

    def _to_list_item(self, row: Ticket) -> TicketListItem:
        pricing = self._ticket_pricing(row.id, row)
        created = row.added_date.isoformat() if row.added_date else ""
        return TicketListItem(
            id=str(row.id),
            folio=f"T-{row.id}",
            branchId=self._branch_id_for_ticket(row.id),
            vehicleTypeId=str(row.car_type_id or ""),
            licensePlate=row.license_plate_id or "",
            total=pricing["total"],
            status=self._status_text(row.status_id),
            createdAt=created,
            customer_name=self._customer_name(row),
        )

    def list_for_admin(self) -> list[TicketListItem]:
        stmt = self._active_filter(select(Ticket)).order_by(Ticket.added_date.desc())
        return [self._to_list_item(row) for row in self.db.scalars(stmt).all()]

    def summary_for_admin(self) -> TicketSummaryResponse:
        items = self.list_for_admin()
        return TicketSummaryResponse(
            totalEarnings=sum(item.total for item in items),
            ticketCount=len(items),
        )

    def get_detail(self, ticket_id: int) -> TicketDetailResponse:
        row = self.db.get(Ticket, ticket_id)
        if row is None or not row.is_active:
            raise TicketNotFoundError()

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

    def get_by_id(self, ticket_id: int) -> TicketPublic:
        stmt = self._active_filter(select(Ticket)).where(Ticket.id == ticket_id)
        row = self.db.scalars(stmt).first()
        if row is None:
            raise TicketNotFoundError()
        return self.to_public(row)

    def create(self, data: TicketCreate) -> TicketPublic:
        if data.payment_type_id not in (PAYMENT_TYPE_EFECTIVO, PAYMENT_TYPE_TRANSBANK):
            raise TicketValidationError("Seleccione el método de pago")

        now = self._now()
        row = Ticket(
            customer_id=data.customer_id,
            car_type_id=data.car_type_id,
            license_plate_id=(data.license_plate_id or "").strip() or None,
            photo_url=(data.photo_url or "").strip() or None,
            payment_type_id=data.payment_type_id,
            status_id=data.status_id,
            tip=(data.tip or "").strip() or None,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )

        service_lines = [
            (line.branch_office_service_id, line.total)
            for line in data.branch_office_service_lines
            if line.branch_office_service_id > 0
        ]
        service_ids = [sid for sid in data.branch_office_service_ids if sid > 0]

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
                )
            elif service_ids:
                raise TicketValidationError(
                    "Indique el monto de cada servicio (branch_office_service_lines)",
                )
            elif data.washer_id is not None:
                self._lines.assign_washer_to_ticket(
                    row.id,
                    data.washer_id,
                    commit=False,
                )

            lines = self._lines.list_lines_for_ticket(row.id)
            subtotal = sum(line.price for line in lines)
            apply_iva = self._resolve_apply_iva(data)
            pricing = ticket_totals_from_subtotal(subtotal, apply_iva=apply_iva)
            row.subtotal = str(pricing["subtotal"])
            row.tax = str(pricing["tax"])
            row.total = str(pricing["total"])

            self.db.commit()
            self.db.refresh(row)
            return self.to_public(row)
        except TicketLineValidationError as exc:
            self.db.rollback()
            raise TicketValidationError(str(exc)) from exc
        except Exception:
            self.db.rollback()
            raise

    def update(self, ticket_id: int, data: TicketUpdate) -> TicketPublic:
        row = self.db.get(Ticket, ticket_id)
        if row is None or not row.is_active:
            raise TicketNotFoundError()

        patch = data.model_dump(exclude_unset=True)
        for key, value in patch.items():
            if key == "license_plate_id" and value is not None:
                value = value.strip() or None
            if key == "photo_url" and value is not None:
                value = value.strip() or None
            if key == "tip" and value is not None:
                value = value.strip() or None
            setattr(row, key, value)

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, ticket_id: int) -> None:
        row = self.db.get(Ticket, ticket_id)
        if row is None or not row.is_active:
            raise TicketNotFoundError()
        now = self._now()
        try:
            self._lines.soft_delete_for_ticket(ticket_id, deleted_at=now)
            row.deleted_date = now
            row.updated_date = now
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
