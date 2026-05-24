from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.raffle import RaffleAssignmentPublic


class TicketServiceLineInput(BaseModel):
    """service_id=0 + additional_service para servicios escritos a mano."""

    service_id: int = Field(default=0, ge=0)
    additional_service: str | None = Field(default=None, max_length=255)
    total: int = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_line(self) -> "TicketServiceLineInput":
        name = (self.additional_service or "").strip()
        if self.service_id == 0:
            if not name:
                raise ValueError("Indique el nombre del servicio adicional")
        elif name:
            raise ValueError("additional_service solo aplica cuando service_id es 0")
        return self


class TicketCreate(BaseModel):
    customer_id: int | None = None
    car_type_id: int | None = None
    license_plate_id: str | None = Field(default=None, max_length=255)
    photo_url: str | None = Field(default=None, max_length=500)
    payment_type_id: int | None = Field(default=None, ge=1, le=2)
    needs_tax_receipt: bool | None = None
    status_id: int | None = None
    washer_id: int | None = None
    service_lines: list[TicketServiceLineInput] = Field(default_factory=list)
    subtotal: int | None = Field(default=None, ge=0)
    tax: int | None = Field(default=None, ge=0)
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


class TicketCheckout(BaseModel):
    payment_type_id: int = Field(..., ge=1, le=2)
    needs_tax_receipt: bool | None = None
    subtotal: int = Field(..., ge=0)
    tax: int = Field(..., ge=0)
    total: int = Field(..., gt=0)


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
    paymentTypeId: str | None = None
    statusId: str | None = None


class TicketServiceLine(BaseModel):
    id: str
    ticket_id: str
    service_id: str
    service_name: str
    price: int
    additional_service: str | None = None
    washer_id: str | None = None
    added_date: str | None = None


class TicketListResponse(BaseModel):
    items: list[TicketListItem]


class TicketSummaryResponse(BaseModel):
    """Suma de `total` por ticket (misma lógica que el listado admin)."""

    totalEarnings: int = Field(ge=0)
    ticketCount: int = Field(ge=0)


class BranchEarningsItem(BaseModel):
    branch_office_id: str
    branch_name: str
    ticket_count: int = Field(ge=0)
    subtotal: int = Field(ge=0)
    iva: int = Field(ge=0)
    total: int = Field(ge=0)


class TicketEarningsByBranchResponse(BaseModel):
    items: list[BranchEarningsItem]
    subtotal: int = Field(ge=0)
    iva: int = Field(ge=0)
    total: int = Field(ge=0)
    ticket_count: int = Field(ge=0)


class BranchEarningsByDateItem(BaseModel):
    """Totales de tickets de una sucursal agrupados por día (fecha de alta)."""

    date: str
    ticket_count: int = Field(ge=0)
    subtotal: int = Field(ge=0)
    iva: int = Field(ge=0)
    total: int = Field(ge=0)


class TicketEarningsByBranchDateResponse(BaseModel):
    branch_office_id: str
    branch_name: str
    items: list[BranchEarningsByDateItem]
    subtotal: int = Field(ge=0)
    iva: int = Field(ge=0)
    total: int = Field(ge=0)
    ticket_count: int = Field(ge=0)


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


class TicketCreateResponse(BaseModel):
    item: TicketPublic
    raffle: RaffleAssignmentPublic | None = None


class TicketDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
