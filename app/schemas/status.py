from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StatusCreate(BaseModel):
    status: str = Field(..., min_length=1, max_length=255)


class StatusUpdate(BaseModel):
    status: str | None = Field(default=None, min_length=1, max_length=255)


class StatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None


class StatusPublic(BaseModel):
    id: str
    status: str
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class StatusListResponse(BaseModel):
    items: list[StatusPublic]


class StatusItemResponse(BaseModel):
    item: StatusPublic


class StatusDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
