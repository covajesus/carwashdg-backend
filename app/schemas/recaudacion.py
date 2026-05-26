from datetime import date

from pydantic import BaseModel, Field


class RecaudacionUpsert(BaseModel):
    gross_amount: int = Field(ge=0)


class RecaudacionDayResponse(BaseModel):
    branch_office_id: str
    branch_name: str
    collection_date: date
    manual_gross_amount: int = Field(ge=0)
    tickets_ticket_count: int = Field(ge=0)
    tickets_subtotal: int = Field(ge=0)
    tickets_iva: int = Field(ge=0)
    tickets_total: int = Field(ge=0)
    ticket_count: int = Field(ge=0)
    subtotal: int = Field(ge=0)
    iva: int = Field(ge=0)
    total: int = Field(ge=0)
