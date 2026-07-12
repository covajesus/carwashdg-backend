from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

CollectionCalendarStatus = Literal["ok", "missing", "future"]


class CollectionUpsert(BaseModel):
    """Manual day collection. Prefer cash/card breakdown; gross_amount kept for legacy clients."""

    cash_amount: int | None = Field(default=None, ge=0)
    card_gross: int | None = Field(default=None, ge=0)
    card_tax: int | None = Field(default=None, ge=0)
    gross_amount: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def resolve_amounts(self) -> "CollectionUpsert":
        cash = int(self.cash_amount or 0)
        card = int(self.card_gross or 0)
        tax = int(self.card_tax or 0)
        legacy_gross = self.gross_amount

        if self.cash_amount is None and self.card_gross is None and legacy_gross is not None:
            cash = int(legacy_gross)
            card = 0
            tax = 0

        if card <= 0:
            card = 0
            tax = 0
        elif tax > card:
            raise ValueError("Card tax cannot exceed card gross")

        object.__setattr__(self, "cash_amount", cash)
        object.__setattr__(self, "card_gross", card)
        object.__setattr__(self, "card_tax", tax)
        object.__setattr__(self, "gross_amount", cash + card)
        return self


class CollectionDayResponse(BaseModel):
    branch_office_id: str
    branch_name: str
    collection_date: date
    manual_gross_amount: int = Field(ge=0)
    manual_cash_amount: int = Field(ge=0, default=0)
    manual_card_gross: int = Field(ge=0, default=0)
    manual_card_tax: int = Field(ge=0, default=0)
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


class CollectionBranchSummaryItem(BaseModel):
    branch_office_id: str
    branch_name: str
    ticket_count: int = Field(ge=0)
    subtotal: int = Field(ge=0)
    iva: int = Field(ge=0)
    total: int = Field(ge=0)
    has_collection: bool = False
    missing_day_count: int = Field(ge=0, default=0)
    missing_dates: list[date] = Field(default_factory=list)


class CollectionBranchesSummaryResponse(BaseModel):
    date_from: date
    date_to: date
    items: list[CollectionBranchSummaryItem]
    subtotal: int = Field(ge=0)
    iva: int = Field(ge=0)
    total: int = Field(ge=0)
    ticket_count: int = Field(ge=0)
    missing_day_count: int = Field(ge=0, default=0)
