from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

CollectionCalendarStatus = Literal["ok", "missing", "future"]


class CollectionUpsert(BaseModel):
    gross_amount: int = Field(ge=0)


class CollectionDayResponse(BaseModel):
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


class CollectionCalendarDay(BaseModel):
    date: date
    status: CollectionCalendarStatus
    has_tickets: bool
    has_manual: bool
    tickets_total: int = Field(ge=0)
    manual_gross_amount: int = Field(ge=0)
    total: int = Field(ge=0)


class CollectionCalendarResponse(BaseModel):
    branch_office_id: str
    branch_name: str
    year: int
    month: int
    days: list[CollectionCalendarDay]
