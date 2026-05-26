from datetime import date

from fastapi import APIRouter, HTTPException

from app.api.deps import CollectionServiceDep, CurrentUserDep, TicketServiceDep
from app.schemas.collection import (
    CollectionCalendarResponse,
    CollectionDayResponse,
    CollectionUpsert,
)
from app.schemas.ticket import ErrorResponse
from app.services.collection_service import CollectionForbiddenError, CollectionValidationError
from app.services.ticket_service import TicketValidationError

router = APIRouter(prefix="/collections", tags=["collections"])


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc


@router.get(
    "/branch/{branch_office_id}/calendar",
    response_model=CollectionCalendarResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_collection_calendar(
    branch_office_id: int,
    year: int,
    month: int,
    current_user: CurrentUserDep,
    ticket_service: TicketServiceDep,
    collection_service: CollectionServiceDep,
) -> CollectionCalendarResponse:
    try:
        buckets = ticket_service.ticket_earnings_date_buckets(current_user, branch_office_id)
        return collection_service.build_calendar_month(
            current_user,
            branch_office_id,
            year=year,
            month=month,
            tickets_date_buckets=buckets,
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc


@router.get(
    "/branch/{branch_office_id}/date/{collection_date}",
    response_model=CollectionDayResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_collection_day(
    branch_office_id: int,
    collection_date: str,
    current_user: CurrentUserDep,
    ticket_service: TicketServiceDep,
    collection_service: CollectionServiceDep,
) -> CollectionDayResponse:
    day = _parse_date(collection_date)
    try:
        buckets = ticket_service.ticket_earnings_date_buckets(current_user, branch_office_id)
        tickets_bucket = collection_service.tickets_bucket_for_date(buckets, day)
        return collection_service.build_day_response(
            current_user,
            branch_office_id,
            day,
            tickets_bucket=tickets_bucket,
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc


@router.put(
    "/branch/{branch_office_id}/date/{collection_date}",
    response_model=CollectionDayResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def upsert_collection_day(
    branch_office_id: int,
    collection_date: str,
    body: CollectionUpsert,
    current_user: CurrentUserDep,
    ticket_service: TicketServiceDep,
    collection_service: CollectionServiceDep,
) -> CollectionDayResponse:
    day = _parse_date(collection_date)
    try:
        collection_service.upsert(current_user, branch_office_id, day, body)
        buckets = ticket_service.ticket_earnings_date_buckets(current_user, branch_office_id)
        tickets_bucket = collection_service.tickets_bucket_for_date(buckets, day)
        return collection_service.build_day_response(
            current_user,
            branch_office_id,
            day,
            tickets_bucket=tickets_bucket,
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionForbiddenError as exc:
        raise HTTPException(status_code=403, detail="Not authorized") from exc
