from pydantic import BaseModel, Field


class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    # 0 = use washer day/Sunday %; >0 overrides for this service only
    washerPercentage: str | None = Field(default="0", max_length=255)
    # Compatibilidad con el panel (no persistidos en BD)
    category: str | None = None
    image: str | None = None


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    washerPercentage: str | None = Field(default=None, max_length=255)
    category: str | None = None
    image: str | None = None


class ServicePublic(BaseModel):
    id: str
    name: str
    description: str = ""
    washerPercentage: str = "0"
    category: str = ""
    image: str = ""
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class ServiceListResponse(BaseModel):
    items: list[ServicePublic]


class ServiceItemResponse(BaseModel):
    item: ServicePublic


class ServiceDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
