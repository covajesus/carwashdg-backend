from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SliderCreate(BaseModel):
    slider: str = Field(..., min_length=1, max_length=255)
    position: str = Field(..., min_length=1, max_length=255)


class SliderUpdate(BaseModel):
    slider: str | None = Field(default=None, min_length=1, max_length=255)
    position: str | None = Field(default=None, min_length=1, max_length=255)


class SliderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slider: str
    position: str
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None


class SliderPublic(BaseModel):
    id: str
    slider: str
    position: str
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None


class SliderListResponse(BaseModel):
    items: list[SliderPublic]


class SliderItemResponse(BaseModel):
    item: SliderPublic


class SliderDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
