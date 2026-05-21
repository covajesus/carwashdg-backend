from pydantic import BaseModel, Field


class TicketBranchOfficeServiceCreate(BaseModel):
    ticket_id: int
    branch_office_service_id: int | None = None
    washer_id: int | None = None


class TicketBranchOfficeServiceUpdate(BaseModel):
    ticket_id: int | None = None
    branch_office_service_id: int | None = None
    washer_id: int | None = None


class TicketBranchOfficeServicePublic(BaseModel):
    id: str
    ticket_id: str
    branch_office_service_id: str | None = None
    washer_id: str | None = None
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
