from datetime import datetime

from pydantic import BaseModel


class RolPublic(BaseModel):
    id: str
    rol: str
    added_date: datetime | None = None
    updated_date: datetime | None = None


class RolListResponse(BaseModel):
    items: list[RolPublic]


class RolItemResponse(BaseModel):
    item: RolPublic


class ErrorResponse(BaseModel):
    error: str
