from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, TicketServiceDep
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
def list_tickets(
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketListResponse:
    return TicketListResponse(items=service.list_for_user(current_user))


@router.get("/summary", response_model=TicketSummaryResponse)
def tickets_summary(
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketSummaryResponse:
    return service.summary_for_user(current_user)


@router.post("", response_model=TicketCreateResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: TicketCreate,
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketCreateResponse:
    try:
        return service.create(body)
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{ticket_id}", response_model=TicketDetailResponse, responses={404: {"model": ErrorResponse}})
def get_ticket(
    ticket_id: int,
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketDetailResponse:
    try:
        return service.get_detail(ticket_id, current_user)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc


@router.patch("/{ticket_id}", response_model=TicketItemResponse, responses={404: {"model": ErrorResponse}})
def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketItemResponse:
    try:
        return TicketItemResponse(item=service.update(ticket_id, body, current_user))
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{ticket_id}", response_model=TicketDeleteResponse, responses={404: {"model": ErrorResponse}})
def delete_ticket(
    ticket_id: int,
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketDeleteResponse:
    try:
        service.delete(ticket_id, current_user)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    return TicketDeleteResponse()
