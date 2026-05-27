from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, TicketServiceDep
from app.schemas.ticket import (
    ErrorResponse,
    TicketCheckout,
    TicketCreate,
    TicketCreateResponse,
    TicketDeleteResponse,
    TicketDetailResponse,
    TicketEarningsByBranchDateResponse,
    TicketEarningsByBranchResponse,
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
    revenue_day: date | None = Query(default=None, alias="date"),
) -> TicketListResponse:
    return TicketListResponse(
        items=service.list_for_user(current_user, revenue_day=revenue_day),
    )


@router.get("/summary", response_model=TicketSummaryResponse)
def tickets_summary(
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketSummaryResponse:
    return service.summary_for_user(current_user)


@router.get(
    "/earnings-by-branch",
    response_model=TicketEarningsByBranchResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def earnings_by_branch(
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketEarningsByBranchResponse:
    try:
        return service.earnings_by_branch(current_user, branch_office_id=None)
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/earnings-by-branch/branch/{branch_office_id}",
    response_model=TicketEarningsByBranchResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def earnings_by_branch_for_office(
    branch_office_id: int,
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketEarningsByBranchResponse:
    try:
        return service.earnings_by_branch(
            current_user,
            branch_office_id=branch_office_id,
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/earnings-by-branch/branch/{branch_office_id}/by-date",
    response_model=TicketEarningsByBranchDateResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def earnings_by_branch_by_date(
    branch_office_id: int,
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketEarningsByBranchDateResponse:
    try:
        return service.earnings_by_branch_by_date(
            current_user,
            branch_office_id=branch_office_id,
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.post(
    "/{ticket_id}/checkout",
    response_model=TicketCreateResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def checkout_ticket(
    ticket_id: int,
    body: TicketCheckout,
    service: TicketServiceDep,
    current_user: CurrentUserDep,
) -> TicketCreateResponse:
    try:
        return service.checkout(ticket_id, body, current_user)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
