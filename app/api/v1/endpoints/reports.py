from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUserDep, EerrServiceDep
from app.schemas.eerr import EerrMonthResponse
from app.schemas.ticket import ErrorResponse
from app.services.eerr_service import EerrForbiddenError, EerrValidationError

router = APIRouter(prefix="/reports", tags=["reports"])


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
) -> EerrMonthResponse:
    try:
        return service.build_month(
            current_user,
            year=year,
            month=month,
        )
    except EerrForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc
    except EerrValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
