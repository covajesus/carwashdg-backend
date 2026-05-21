from fastapi import APIRouter, HTTPException, status

from app.api.deps import TicketServiceDep
from app.schemas.ticket import (
    ErrorResponse,
    TicketCreate,
    TicketCreateResponse,
    TicketDeleteResponse,
    TicketDetailResponse,
    TicketItemResponse,
    TicketListResponse,
    TicketSummaryResponse,
    TicketUpdate,
)
from app.services.ticket_service import TicketNotFoundError, TicketValidationError

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=TicketListResponse)
def list_tickets(service: TicketServiceDep) -> TicketListResponse:
    return TicketListResponse(items=service.list_for_admin())


@router.get("/summary", response_model=TicketSummaryResponse)
def tickets_summary(service: TicketServiceDep) -> TicketSummaryResponse:
    return service.summary_for_admin()


@router.post("", response_model=TicketCreateResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(body: TicketCreate, service: TicketServiceDep) -> TicketCreateResponse:
    try:
        return service.create(body)
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{ticket_id}", response_model=TicketDetailResponse, responses={404: {"model": ErrorResponse}})
def get_ticket(ticket_id: int, service: TicketServiceDep) -> TicketDetailResponse:
    try:
        return service.get_detail(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc


@router.patch("/{ticket_id}", response_model=TicketItemResponse, responses={404: {"model": ErrorResponse}})
def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    service: TicketServiceDep,
) -> TicketItemResponse:
    try:
        return TicketItemResponse(item=service.update(ticket_id, body))
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{ticket_id}", response_model=TicketDeleteResponse, responses={404: {"model": ErrorResponse}})
def delete_ticket(ticket_id: int, service: TicketServiceDep) -> TicketDeleteResponse:
    try:
        service.delete(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    return TicketDeleteResponse()
