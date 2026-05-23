from fastapi import APIRouter, HTTPException, status

from app.api.deps import CashClosureServiceDep, CurrentUserDep
from app.schemas.cash_closure import CashClosureConfirmResponse, CashClosureTodayResponse
from app.schemas.ticket import ErrorResponse
from app.services.cash_closure_service import CashClosureValidationError

router = APIRouter(prefix="/cash-closure", tags=["cash-closure"])


@router.get(
    "/today",
    response_model=CashClosureTodayResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def cash_closure_today(
    current_user: CurrentUserDep,
    service: CashClosureServiceDep,
) -> CashClosureTodayResponse:
    try:
        return service.today_status(current_user)
    except CashClosureValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/confirm",
    response_model=CashClosureConfirmResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def cash_closure_confirm(
    current_user: CurrentUserDep,
    service: CashClosureServiceDep,
) -> CashClosureConfirmResponse:
    try:
        return service.confirm_close(current_user)
    except CashClosureValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
