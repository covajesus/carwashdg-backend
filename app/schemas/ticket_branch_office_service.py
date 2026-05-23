from pydantic import BaseModel, Field


class TicketBranchOfficeServiceCreate(BaseModel):
    ticket_id: int
    service_id: int | None = None
    additional_service: str | None = Field(default=None, max_length=255)
    washer_id: int | None = None
    total: int | None = Field(default=None, ge=0)


class TicketBranchOfficeServiceUpdate(BaseModel):
    ticket_id: int | None = None
    service_id: int | None = None
    additional_service: str | None = Field(default=None, max_length=255)
    washer_id: int | None = None
    total: int | None = Field(default=None, ge=0)


class TicketBranchOfficeServicePublic(BaseModel):
    id: str
    ticket_id: str
    service_id: str | None = None
    additional_service: str | None = None
    washer_id: str | None = None
    total: int = 0
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class TicketBranchOfficeServiceListResponse(BaseModel):
    items: list[TicketBranchOfficeServicePublic]


class TicketBranchOfficeServiceItemResponse(BaseModel):
    item: TicketBranchOfficeServicePublic


class TicketBranchOfficeServiceDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
