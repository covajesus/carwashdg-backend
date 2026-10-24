from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.api.deps import ConfigurationServiceDep
from app.schemas.configuration import ConfigurationItemResponse, ErrorResponse
from app.services.configuration_service import ConfigurationValidationError

router = APIRouter(prefix="/configurations", tags=["configurations"])


@router.get(
    "",
    response_model=ConfigurationItemResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_configurations(service: ConfigurationServiceDep) -> ConfigurationItemResponse:
    """Configuración pública del sitio web (contacto y redes)."""
    return ConfigurationItemResponse(item=service.get_settings())


@router.get(
    "/benefit-images/{slot}",
    responses={404: {"model": ErrorResponse}},
)
def get_benefit_image(slot: str, service: ConfigurationServiceDep) -> Response:
    try:
        content, media_type = service.read_benefit_image(slot)
    except ConfigurationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado") from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
