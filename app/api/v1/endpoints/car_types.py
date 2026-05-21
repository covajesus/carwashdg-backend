from fastapi import APIRouter, HTTPException, status

from app.api.deps import CarTypeServiceDep
from app.schemas.car_type import (
    CarTypeCreate,
    CarTypeDeleteResponse,
    CarTypeItemResponse,
    CarTypeListResponse,
    CarTypeUpdate,
    ErrorResponse,
)
from app.services.car_type_service import CarTypeNotFoundError, CarTypeValidationError

router = APIRouter(prefix="/car-types", tags=["car_types"])


@router.get(
    "",
    response_model=CarTypeListResponse,
    responses={401: {"model": ErrorResponse}},
)
def list_car_types(service: CarTypeServiceDep) -> CarTypeListResponse:
    return CarTypeListResponse(items=service.list_all())


@router.post(
    "",
    response_model=CarTypeItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def create_car_type(
    body: CarTypeCreate,
    service: CarTypeServiceDep,
) -> CarTypeItemResponse:
    try:
        item = service.create(body)
    except CarTypeValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CarTypeItemResponse(item=item)


@router.get(
    "/{car_type_id}",
    response_model=CarTypeItemResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def get_car_type(
    car_type_id: int,
    service: CarTypeServiceDep,
) -> CarTypeItemResponse:
    try:
        item = service.get_by_id(car_type_id)
    except CarTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return CarTypeItemResponse(item=item)


@router.patch(
    "/{car_type_id}",
    response_model=CarTypeItemResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def update_car_type(
    car_type_id: int,
    body: CarTypeUpdate,
    service: CarTypeServiceDep,
) -> CarTypeItemResponse:
    try:
        item = service.update(car_type_id, body)
    except CarTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    except CarTypeValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CarTypeItemResponse(item=item)


@router.delete(
    "/{car_type_id}",
    response_model=CarTypeDeleteResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def delete_car_type(
    car_type_id: int,
    service: CarTypeServiceDep,
) -> CarTypeDeleteResponse:
    try:
        service.delete(car_type_id)
    except CarTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return CarTypeDeleteResponse()
