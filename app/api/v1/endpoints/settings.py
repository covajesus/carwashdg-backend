from fastapi import APIRouter, HTTPException, status

from app.api.deps import ConfigurationServiceDep
from app.schemas.configuration import (
    ConfigurationItemResponse,
    ConfigurationUpdate,
    ErrorResponse,
)
from app.services.configuration_service import ConfigurationValidationError

router = APIRouter(prefix="/settings", tags=["configurations"])


@router.get(
    "",
    response_model=ConfigurationItemResponse,
    responses={401: {"model": ErrorResponse}},
)
def get_settings(service: ConfigurationServiceDep) -> ConfigurationItemResponse:
    return ConfigurationItemResponse(item=service.get_settings())


@router.patch(
    "",
    response_model=ConfigurationItemResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def update_settings(
    body: ConfigurationUpdate,
    service: ConfigurationServiceDep,
) -> ConfigurationItemResponse:
    try:
        item = service.update_settings(body)
    except ConfigurationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConfigurationItemResponse(item=item)
