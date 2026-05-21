from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    license_plate_id: str = Field(..., min_length=1, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(default="", max_length=255)
    email: str = Field(default="", max_length=255)


class CustomerUpdate(BaseModel):
    license_plate_id: str | None = Field(default=None, min_length=1, max_length=255)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class CustomerPublic(BaseModel):
    id: str
    license_plate_id: str
    full_name: str
    phone: str
    email: str
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None


class CustomerListResponse(BaseModel):
    items: list[CustomerPublic]


class CustomerItemResponse(BaseModel):
    item: CustomerPublic


class CustomerDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
