from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, WasherDailyGroupServiceDep
from app.schemas.washer_daily_group import (
    ErrorResponse,
    TicketWasherOptionsResponse,
    WasherDailyGroupCreate,
    WasherDailyGroupDeleteResponse,
    WasherDailyGroupItemResponse,
    WasherDailyGroupListResponse,
    WasherDailyGroupUpdate,
)
from app.services.washer_daily_group_service import (
    WasherDailyGroupNotFoundError,
    WasherDailyGroupValidationError,
)

router = APIRouter(prefix="/washer-daily-groups", tags=["washer-daily-groups"])


@router.get(
    "/branch/{branch_office_id}",
    response_model=WasherDailyGroupListResponse,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
def list_groups(
    branch_office_id: int,
    user: CurrentUserDep,
    service: WasherDailyGroupServiceDep,
) -> WasherDailyGroupListResponse:
    try:
        return service.list_for_branch_and_date(user, branch_office_id=branch_office_id)
    except WasherDailyGroupValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/branch/{branch_office_id}/ticket-options",
    response_model=TicketWasherOptionsResponse,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
def ticket_washer_options(
    branch_office_id: int,
    user: CurrentUserDep,
    service: WasherDailyGroupServiceDep,
) -> TicketWasherOptionsResponse:
    try:
        return service.ticket_washer_options(user, branch_office_id=branch_office_id)
    except WasherDailyGroupValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{group_id}",
    response_model=WasherDailyGroupItemResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
def get_group(
    group_id: int,
    user: CurrentUserDep,
    service: WasherDailyGroupServiceDep,
) -> WasherDailyGroupItemResponse:
    try:
        item = service.get_by_id(user, group_id)
    except WasherDailyGroupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WasherDailyGroupValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WasherDailyGroupItemResponse(item=item)


@router.post(
    "",
    response_model=WasherDailyGroupItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
def create_group(
    body: WasherDailyGroupCreate,
    user: CurrentUserDep,
    service: WasherDailyGroupServiceDep,
) -> WasherDailyGroupItemResponse:
    try:
        item = service.create_for_manager(user, data=body)
    except WasherDailyGroupValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WasherDailyGroupItemResponse(item=item)


@router.patch(
    "/{group_id}",
    response_model=WasherDailyGroupItemResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
def update_group(
    group_id: int,
    body: WasherDailyGroupUpdate,
    user: CurrentUserDep,
    service: WasherDailyGroupServiceDep,
) -> WasherDailyGroupItemResponse:
    try:
        item = service.update(user, group_id, body)
    except WasherDailyGroupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WasherDailyGroupValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WasherDailyGroupItemResponse(item=item)


@router.delete(
    "/{group_id}",
    response_model=WasherDailyGroupDeleteResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
def delete_group(
    group_id: int,
    user: CurrentUserDep,
    service: WasherDailyGroupServiceDep,
) -> WasherDailyGroupDeleteResponse:
    try:
        service.delete(user, group_id)
    except WasherDailyGroupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WasherDailyGroupValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WasherDailyGroupDeleteResponse()
