from fastapi import APIRouter

from app.api.deps import ConfigurationServiceDep
from app.schemas.configuration import ConfigurationItemResponse, ErrorResponse

router = APIRouter(prefix="/configurations", tags=["configurations"])


@router.get(
    "",
    response_model=ConfigurationItemResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_configurations(service: ConfigurationServiceDep) -> ConfigurationItemResponse:
    """Configuración pública del sitio web (contacto y redes)."""
    return ConfigurationItemResponse(item=service.get_settings())
