from datetime import datetime

from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    customer_id: int | None = None
    car_type_id: int | None = None
    license_plate_id: str | None = Field(default=None, max_length=255)
    photo_url: str | None = Field(default=None, max_length=500)
    payment_type_id: int | None = None
    status_id: int | None = None
    washer_id: int | None = None
    branch_office_service_ids: list[int] = Field(default_factory=list)
    total: int | None = Field(default=None, ge=0)
    tip: str | None = Field(default=None, max_length=255)


class TicketUpdate(BaseModel):
    customer_id: int | None = None
    car_type_id: int | None = None
    license_plate_id: str | None = Field(default=None, max_length=255)
    photo_url: str | None = Field(default=None, max_length=500)
    payment_type_id: int | None = None
    status_id: int | None = None
    tip: str | None = Field(default=None, max_length=255)


class TicketPublic(BaseModel):
    id: str
    customer_id: str | None = None
    car_type_id: str | None = None
    license_plate_id: str | None = None
    photo_url: str | None = None
    payment_type_id: str | None = None
    status_id: str | None = None
    tip: str | None = None
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None


class TicketListItem(BaseModel):
    id: str
    folio: str
    branchId: str
    vehicleTypeId: str
    licensePlate: str
    total: int
    status: str
    createdAt: str
    customer_name: str


class TicketServiceLine(BaseModel):
    id: str
    ticket_id: str
    branch_office_service_id: str
    service_id: str
    service_name: str
    price: int
    washer_id: str | None = None
    added_date: str | None = None


class TicketListResponse(BaseModel):
    items: list[TicketListItem]


class TicketDetailResponse(BaseModel):
    ticket: TicketListItem
    customer_name: str
    branch_name: str
    services: list[TicketServiceLine]
    subtotal: int
    iva: int
    total: int


class TicketItemResponse(BaseModel):
    item: TicketPublic


class TicketDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
