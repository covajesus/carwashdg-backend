from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CarTypeCreate(BaseModel):
    car_type: str = Field(..., min_length=1, max_length=255)
    icon: str = Field(default="", max_length=255)


class CarTypeUpdate(BaseModel):
    car_type: str | None = Field(default=None, min_length=1, max_length=255)
    icon: str | None = Field(default=None, max_length=255)


class CarTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    car_type: str
    icon: str
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None


class CarTypePublic(BaseModel):
    id: str
    car_type: str
    icon: str
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class CarTypeListResponse(BaseModel):
    items: list[CarTypePublic]


class CarTypeItemResponse(BaseModel):
    item: CarTypePublic


class CarTypeDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
