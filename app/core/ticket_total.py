from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pricing import round_amount, ticket_totals_from_subtotal
from app.models.branch_office_service import BranchOfficeService
from app.models.ticket import Ticket
from app.models.ticket_branch_office_service import TicketBranchOfficeService


def parse_ticket_total(value: str | None) -> int | None:
    if not value or not str(value).strip():
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _subtotal_for_ticket(db: Session, ticket_id: int) -> int:
    stmt = select(TicketBranchOfficeService).where(
        TicketBranchOfficeService.ticket_id == ticket_id,
        TicketBranchOfficeService.deleted_date.is_(None),
    )
    subtotal = 0
    for line in db.scalars(stmt).all():
        if line.branch_office_service_id is None:
            continue
        bos = db.get(BranchOfficeService, line.branch_office_service_id)
        if bos is None or not bos.is_active:
            continue
        subtotal += round_amount(bos.price or 0)
    return subtotal


def sync_ticket_total(db: Session, ticket_id: int) -> int:
    total = ticket_totals_from_subtotal(_subtotal_for_ticket(db, ticket_id))["total"]
    row = db.get(Ticket, ticket_id)
    if row is not None:
        row.total = str(total)
    return total
