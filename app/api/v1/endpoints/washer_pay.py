from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, WasherPayServiceDep
from app.schemas.ticket import ErrorResponse
from app.schemas.washer_pay import (
    WasherPayDetailResponse,
    WasherPayStatusResponse,
    WasherPayStatusUpdate,
    WasherPaySummaryResponse,
)
from app.services.washer_pay_service import WasherPayValidationError

router = APIRouter(prefix="/washer-pay", tags=["washer-pay"])


@router.get(
    "/branch/{branch_office_id}/date/{date_value}",
    response_model=WasherPaySummaryResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def washer_pay_summary(
    branch_office_id: int,
    date_value: str,
    current_user: CurrentUserDep,
    service: WasherPayServiceDep,
) -> WasherPaySummaryResponse:
    if branch_office_id < 1:
        raise HTTPException(status_code=400, detail="Sucursal no válida")
    try:
        return service.summary_by_branch_and_date(
            current_user,
            branch_office_id=branch_office_id,
            date_value=date_value,
        )
    except WasherPayValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/branch/{branch_office_id}/date/{date_value}/washer/{washer_id}",
    response_model=WasherPayDetailResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def washer_pay_detail(
    branch_office_id: int,
    date_value: str,
    washer_id: int,
    current_user: CurrentUserDep,
    service: WasherPayServiceDep,
) -> WasherPayDetailResponse:
    if branch_office_id < 1:
        raise HTTPException(status_code=400, detail="Sucursal no válida")
    if washer_id < 1:
        raise HTTPException(status_code=400, detail="Lavador no válido")
    try:
        return service.detail_for_washer(
            current_user,
            branch_office_id=branch_office_id,
            date_value=date_value,
            washer_id=washer_id,
        )
    except WasherPayValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/branch/{branch_office_id}/date/{date_value}/washer/{washer_id}/payment-status",
    response_model=WasherPayStatusResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def washer_pay_set_status(
    branch_office_id: int,
    date_value: str,
    washer_id: int,
    body: WasherPayStatusUpdate,
    current_user: CurrentUserDep,
    service: WasherPayServiceDep,
) -> WasherPayStatusResponse:
    if branch_office_id < 1:
        raise HTTPException(status_code=400, detail="Sucursal no válida")
    if washer_id < 1:
        raise HTTPException(status_code=400, detail="Lavador no válido")
    try:
        return service.set_payment_status(
            current_user,
            branch_office_id=branch_office_id,
            date_value=date_value,
            washer_id=washer_id,
            payment_status=body.payment_status,
        )
    except WasherPayValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
