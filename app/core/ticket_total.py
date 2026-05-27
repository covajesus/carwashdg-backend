from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pricing import round_money, ticket_totals_from_subtotal
from app.models.ticket import Ticket
from app.models.ticket_branch_office_service import TicketBranchOfficeService


def parse_ticket_total(value: str | None) -> int | None:
    if not value or not str(value).strip():
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _line_amount(line: TicketBranchOfficeService) -> int:
    additional = (line.additional_service or "").strip()
    svc_id = line.service_id
    # Línea solo lavador (placeholder), sin servicio ni monto.
    if svc_id is None and not additional:
        return 0
    if line.total is not None:
        return round_money(line.total)
    return 0


def _gross_lines_total_for_ticket(db: Session, ticket_id: int) -> int:
    """Suma de montos brutos de líneas activas."""
    stmt = select(TicketBranchOfficeService).where(
        TicketBranchOfficeService.ticket_id == ticket_id,
        TicketBranchOfficeService.deleted_date.is_(None),
    )
    return sum(_line_amount(line) for line in db.scalars(stmt).all())


def sync_ticket_total(db: Session, ticket_id: int, *, apply_iva: bool = True) -> int:
    pricing = ticket_totals_from_subtotal(
        _gross_lines_total_for_ticket(db, ticket_id),
        apply_iva=apply_iva,
    )
    row = db.get(Ticket, ticket_id)
    if row is not None:
        row.subtotal = str(pricing["subtotal"])
        row.tax = str(pricing["tax"])
        row.total = str(pricing["total"])
    return pricing["total"]
