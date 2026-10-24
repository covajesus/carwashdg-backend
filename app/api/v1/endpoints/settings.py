from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import ConfigurationServiceDep, CurrentUserDep
from app.schemas.configuration import (
    ConfigurationSettingsItemResponse,
    ConfigurationUpdate,
    ErrorResponse,
)
from app.services.configuration_service import ConfigurationValidationError

router = APIRouter(prefix="/settings", tags=["configurations"])


@router.get(
    "",
    response_model=ConfigurationSettingsItemResponse,
    responses={401: {"model": ErrorResponse}},
)
def get_settings(service: ConfigurationServiceDep) -> ConfigurationSettingsItemResponse:
    return ConfigurationSettingsItemResponse(item=service.get_admin_settings())


@router.patch(
    "",
    response_model=ConfigurationSettingsItemResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def update_settings(
    body: ConfigurationUpdate,
    service: ConfigurationServiceDep,
) -> ConfigurationSettingsItemResponse:
    try:
        item = service.update_settings(body)
    except ConfigurationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConfigurationSettingsItemResponse(item=item)


@router.put(
    "/benefit-images/{slot}",
    response_model=ConfigurationSettingsItemResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def upload_benefit_image(
    slot: str,
    current_user: CurrentUserDep,
    service: ConfigurationServiceDep,
    file: UploadFile = File(...),
) -> ConfigurationSettingsItemResponse:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
    content = await file.read()
    try:
        item = service.save_benefit_image(slot, file.content_type or "", content)
    except ConfigurationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConfigurationSettingsItemResponse(item=item)
