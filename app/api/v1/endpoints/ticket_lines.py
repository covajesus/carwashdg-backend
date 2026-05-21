from fastapi import APIRouter, HTTPException, status

from app.api.deps import TicketLineServiceDep
from app.schemas.ticket_branch_office_service import (
    ErrorResponse,
    TicketBranchOfficeServiceCreate,
    TicketBranchOfficeServiceDeleteResponse,
    TicketBranchOfficeServiceItemResponse,
    TicketBranchOfficeServiceListResponse,
    TicketBranchOfficeServiceUpdate,
)
from app.services.ticket_line_service import TicketLineNotFoundError, TicketLineValidationError

router = APIRouter(prefix="/ticket-services", tags=["ticket_services"])


@router.get("", response_model=TicketBranchOfficeServiceListResponse)
def list_ticket_services(
    service: TicketLineServiceDep,
) -> TicketBranchOfficeServiceListResponse:
    return TicketBranchOfficeServiceListResponse(items=service.list_all())


@router.get(
    "/ticket/{ticket_id}",
    response_model=TicketBranchOfficeServiceListResponse,
)
def list_ticket_services_by_ticket(
    ticket_id: int,
    service: TicketLineServiceDep,
) -> TicketBranchOfficeServiceListResponse:
    if ticket_id < 1:
        raise HTTPException(status_code=400, detail="Ticket no válido")
    return TicketBranchOfficeServiceListResponse(
        items=service.list_all(ticket_id=ticket_id),
    )


@router.post("", response_model=TicketBranchOfficeServiceItemResponse, status_code=status.HTTP_201_CREATED)
def create_ticket_service(
    body: TicketBranchOfficeServiceCreate,
    service: TicketLineServiceDep,
) -> TicketBranchOfficeServiceItemResponse:
    try:
        return TicketBranchOfficeServiceItemResponse(item=service.create(body))
    except TicketLineValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{line_id}", response_model=TicketBranchOfficeServiceItemResponse, responses={404: {"model": ErrorResponse}})
def get_ticket_service(line_id: int, service: TicketLineServiceDep) -> TicketBranchOfficeServiceItemResponse:
    try:
        return TicketBranchOfficeServiceItemResponse(item=service.get_by_id(line_id))
    except TicketLineNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc


@router.patch("/{line_id}", response_model=TicketBranchOfficeServiceItemResponse, responses={404: {"model": ErrorResponse}})
def update_ticket_service(
    line_id: int,
    body: TicketBranchOfficeServiceUpdate,
    service: TicketLineServiceDep,
) -> TicketBranchOfficeServiceItemResponse:
    try:
        return TicketBranchOfficeServiceItemResponse(item=service.update(line_id, body))
    except TicketLineNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except TicketLineValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{line_id}", response_model=TicketBranchOfficeServiceDeleteResponse, responses={404: {"model": ErrorResponse}})
def delete_ticket_service(line_id: int, service: TicketLineServiceDep) -> TicketBranchOfficeServiceDeleteResponse:
    try:
        service.delete(line_id)
    except TicketLineNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    return TicketBranchOfficeServiceDeleteResponse()
