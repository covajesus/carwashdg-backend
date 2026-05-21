from datetime import datetime

from pydantic import BaseModel


class BranchOfficeServiceCreate(BaseModel):
    branch_office_id: int
    service_id: int
    car_type_id: int


class BranchOfficeServiceUpdate(BaseModel):
    branch_office_id: int | None = None
    service_id: int | None = None
    car_type_id: int | None = None


class BranchOfficeServicePublic(BaseModel):
    id: str
    branch_office_id: str
    service_id: str
    car_type_id: str
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
