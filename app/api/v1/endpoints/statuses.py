from fastapi import APIRouter, HTTPException, status

from app.api.deps import StatusServiceDep
from app.schemas.status import (
    ErrorResponse,
    StatusCreate,
    StatusDeleteResponse,
    StatusItemResponse,
    StatusListResponse,
    StatusUpdate,
)
from app.services.status_service import StatusNotFoundError, StatusValidationError

router = APIRouter(prefix="/statuses", tags=["statuses"])


@router.get(
    "",
    response_model=StatusListResponse,
    responses={401: {"model": ErrorResponse}},
)
def list_statuses(service: StatusServiceDep) -> StatusListResponse:
    return StatusListResponse(items=service.list_all())


@router.post(
    "",
    response_model=StatusItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def create_status(
    body: StatusCreate,
    service: StatusServiceDep,
) -> StatusItemResponse:
    try:
        item = service.create(body)
    except StatusValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return StatusItemResponse(item=item)


@router.get(
    "/{status_id}",
    response_model=StatusItemResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def get_status(
    status_id: int,
    service: StatusServiceDep,
) -> StatusItemResponse:
    try:
        item = service.get_by_id(status_id)
    except StatusNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return StatusItemResponse(item=item)


@router.patch(
    "/{status_id}",
    response_model=StatusItemResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def update_status(
    status_id: int,
    body: StatusUpdate,
    service: StatusServiceDep,
) -> StatusItemResponse:
    try:
        item = service.update(status_id, body)
    except StatusNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    except StatusValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return StatusItemResponse(item=item)


@router.delete(
    "/{status_id}",
    response_model=StatusDeleteResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def delete_status(
    status_id: int,
    service: StatusServiceDep,
) -> StatusDeleteResponse:
    try:
        service.delete(status_id)
    except StatusNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return StatusDeleteResponse()
