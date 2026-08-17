from fastapi import APIRouter, HTTPException

from app.api.deps import (
    ComparisonServiceDep,
    CurrentUserDep,
    DashboardServiceDep,
    EerrServiceDep,
    WasherPayServiceDep,
)
from app.schemas.comparison import ComparisonResponse
from app.schemas.dashboard import DashboardHomeSummaryResponse
from app.schemas.eerr import EerrMonthResponse
from app.schemas.ticket import ErrorResponse
from app.schemas.washer_pay import WasherPayMonthResponse
from app.services.comparison_service import ComparisonForbiddenError, ComparisonValidationError
from app.services.dashboard_service import DashboardForbiddenError, DashboardValidationError
from app.services.eerr_service import EerrForbiddenError, EerrValidationError
from app.services.washer_pay_service import WasherPayValidationError

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/dashboard-home",
    response_model=DashboardHomeSummaryResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_dashboard_home_summary(
    year: int,
    month: int,
    current_user: CurrentUserDep,
    service: DashboardServiceDep,
) -> DashboardHomeSummaryResponse:
    try:
        return service.build_home_summary(
            current_user,
            year=year,
            month=month,
        )
    except DashboardForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc
    except DashboardValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/eerr",
    response_model=EerrMonthResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_eerr_month(
    year: int,
    month: int,
    current_user: CurrentUserDep,
    service: EerrServiceDep,
    branch_office_id: int | None = None,
) -> EerrMonthResponse:
    try:
        return service.build_month(
            current_user,
            year=year,
            month=month,
            branch_office_id=branch_office_id,
        )
    except EerrForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc
    except EerrValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/comparison",
    response_model=ComparisonResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_comparison_report(
    year: int,
    month: int,
    current_user: CurrentUserDep,
    service: ComparisonServiceDep,
    branch_office_id: int | None = None,
) -> ComparisonResponse:
    try:
        return service.build(
            current_user,
            year=year,
            month=month,
            branch_office_id=branch_office_id,
        )
    except ComparisonForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc
    except ComparisonValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/washer-pay",
    response_model=WasherPayMonthResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_washer_pay_month(
    year: int,
    month: int,
    current_user: CurrentUserDep,
    service: WasherPayServiceDep,
    branch_office_id: int | None = None,
    washer_id: int | None = None,
) -> WasherPayMonthResponse:
    try:
        return service.month_report(
            current_user,
            year=year,
            month=month,
            branch_office_id=branch_office_id,
            washer_id=washer_id,
        )
    except WasherPayValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
