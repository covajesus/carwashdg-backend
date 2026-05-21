from fastapi import APIRouter, HTTPException, status

from app.api.deps import SliderServiceDep
from app.schemas.slider import (
    ErrorResponse,
    SliderCreate,
    SliderDeleteResponse,
    SliderItemResponse,
    SliderListResponse,
    SliderUpdate,
)
from app.services.slider_service import SliderNotFoundError, SliderValidationError

router = APIRouter(prefix="/sliders", tags=["sliders"])


@router.get(
    "",
    response_model=SliderListResponse,
    responses={401: {"model": ErrorResponse}},
)
def list_sliders(service: SliderServiceDep) -> SliderListResponse:
    return SliderListResponse(items=service.list_all())


@router.post(
    "",
    response_model=SliderItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def create_slider(
    body: SliderCreate,
    service: SliderServiceDep,
) -> SliderItemResponse:
    try:
        item = service.create(body)
    except SliderValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SliderItemResponse(item=item)


@router.get(
    "/{slider_id}",
    response_model=SliderItemResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def get_slider(
    slider_id: int,
    service: SliderServiceDep,
) -> SliderItemResponse:
    try:
        item = service.get_by_id(slider_id)
    except SliderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return SliderItemResponse(item=item)


@router.patch(
    "/{slider_id}",
    response_model=SliderItemResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def update_slider(
    slider_id: int,
    body: SliderUpdate,
    service: SliderServiceDep,
) -> SliderItemResponse:
    try:
        item = service.update(slider_id, body)
    except SliderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    except SliderValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SliderItemResponse(item=item)


@router.delete(
    "/{slider_id}",
    response_model=SliderDeleteResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def delete_slider(
    slider_id: int,
    service: SliderServiceDep,
) -> SliderDeleteResponse:
    try:
        service.delete(slider_id)
    except SliderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return SliderDeleteResponse()
