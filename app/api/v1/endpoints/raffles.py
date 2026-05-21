from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import RaffleServiceDep
from app.schemas.raffle import (
    ErrorResponse,
    RaffleCreate,
    RaffleCurrentResponse,
    RaffleDeleteResponse,
    RaffleDrawResponse,
    RaffleItemResponse,
    RaffleListResponse,
    RaffleNumberListResponse,
    RaffleUpdate,
)
from app.services.raffle_service import RaffleNotFoundError, RaffleValidationError

router = APIRouter(prefix="/raffles", tags=["raffles"])


@router.get(
    "",
    response_model=RaffleListResponse,
    responses={401: {"model": ErrorResponse}},
)
def list_raffles(service: RaffleServiceDep) -> RaffleListResponse:
    return RaffleListResponse(items=service.list_all())


@router.get(
    "/current",
    response_model=RaffleCurrentResponse,
    responses={401: {"model": ErrorResponse}},
)
def get_current_raffle(service: RaffleServiceDep) -> RaffleCurrentResponse:
    return RaffleCurrentResponse(item=service.get_current_active_public())


@router.post(
    "",
    response_model=RaffleItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def create_raffle(
    body: RaffleCreate,
    service: RaffleServiceDep,
) -> RaffleItemResponse:
    try:
        item = service.create(body)
    except RaffleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RaffleItemResponse(item=item)


@router.get(
    "/{raffle_id}",
    response_model=RaffleItemResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def get_raffle(
    raffle_id: int,
    service: RaffleServiceDep,
) -> RaffleItemResponse:
    try:
        item = service.get_by_id(raffle_id)
    except RaffleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return RaffleItemResponse(item=item)


@router.patch(
    "/{raffle_id}",
    response_model=RaffleItemResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def update_raffle(
    raffle_id: int,
    body: RaffleUpdate,
    service: RaffleServiceDep,
) -> RaffleItemResponse:
    try:
        item = service.update(raffle_id, body)
    except RaffleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    except RaffleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RaffleItemResponse(item=item)


@router.delete(
    "/{raffle_id}",
    response_model=RaffleDeleteResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def delete_raffle(
    raffle_id: int,
    service: RaffleServiceDep,
) -> RaffleDeleteResponse:
    try:
        service.delete(raffle_id)
    except RaffleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return RaffleDeleteResponse()


@router.get(
    "/{raffle_id}/numbers",
    response_model=RaffleNumberListResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def list_raffle_numbers(
    raffle_id: int,
    service: RaffleServiceDep,
) -> RaffleNumberListResponse:
    try:
        items = service.list_numbers(raffle_id)
    except RaffleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return RaffleNumberListResponse(items=items)


@router.get(
    "/{raffle_id}/draw",
    response_model=RaffleDrawResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def draw_raffle_number(
    raffle_id: int,
    service: RaffleServiceDep,
    min_number: int = Query(default=1, ge=0, alias="min"),
    max_number: int = Query(default=9999, ge=1, alias="max"),
) -> RaffleDrawResponse:
    try:
        return service.draw_number(
            raffle_id,
            min_number=min_number,
            max_number=max_number,
        )
    except RaffleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    except RaffleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
