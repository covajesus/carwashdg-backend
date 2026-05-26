from datetime import date

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, RecaudacionServiceDep, TicketServiceDep
from app.schemas.recaudacion import RecaudacionDayResponse, RecaudacionUpsert
from app.schemas.ticket import ErrorResponse
from app.services.recaudacion_service import (
    RecaudacionForbiddenError,
    RecaudacionValidationError,
)
from app.services.ticket_service import TicketValidationError

router = APIRouter(prefix="/recaudacion", tags=["recaudacion"])


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc


@router.get(
    "/branch/{branch_office_id}/date/{collection_date}",
    response_model=RecaudacionDayResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_recaudacion_day(
    branch_office_id: int,
    collection_date: str,
    current_user: CurrentUserDep,
    ticket_service: TicketServiceDep,
    recaudacion_service: RecaudacionServiceDep,
) -> RecaudacionDayResponse:
    day = _parse_date(collection_date)
    try:
        buckets = ticket_service.ticket_earnings_date_buckets(current_user, branch_office_id)
        tickets_bucket = recaudacion_service.tickets_bucket_for_date(buckets, day)
        return recaudacion_service.build_day_response(
            current_user,
            branch_office_id,
            day,
            tickets_bucket=tickets_bucket,
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RecaudacionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RecaudacionForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc


@router.put(
    "/branch/{branch_office_id}/date/{collection_date}",
    response_model=RecaudacionDayResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def upsert_recaudacion_day(
    branch_office_id: int,
    collection_date: str,
    body: RecaudacionUpsert,
    current_user: CurrentUserDep,
    ticket_service: TicketServiceDep,
    recaudacion_service: RecaudacionServiceDep,
) -> RecaudacionDayResponse:
    day = _parse_date(collection_date)
    try:
        recaudacion_service.upsert(current_user, branch_office_id, day, body)
        buckets = ticket_service.ticket_earnings_date_buckets(current_user, branch_office_id)
        tickets_bucket = recaudacion_service.tickets_bucket_for_date(buckets, day)
        return recaudacion_service.build_day_response(
            current_user,
            branch_office_id,
            day,
            tickets_bucket=tickets_bucket,
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RecaudacionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RecaudacionForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc
