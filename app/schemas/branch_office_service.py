from datetime import datetime

from pydantic import BaseModel, Field


class BranchOfficeServiceCreate(BaseModel):
    branch_office_id: int
    service_id: int
    price: int = Field(..., ge=0)


class BranchOfficeServiceUpdate(BaseModel):
    branch_office_id: int | None = None
    service_id: int | None = None
    price: int | None = Field(default=None, ge=0)


class BranchOfficeServicePublic(BaseModel):
    id: str
    branch_office_id: str
    service_id: str
    price: int
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None


class BranchOfficeServiceListResponse(BaseModel):
    items: list[BranchOfficeServicePublic]


class BranchOfficeServiceItemResponse(BaseModel):
    item: BranchOfficeServicePublic


class BranchOfficeServiceDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
