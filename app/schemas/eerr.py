from pydantic import BaseModel, Field


class EerrDetailItem(BaseModel):
    id: str
    date: str | None = None
    description: str
    amount: int = Field(ge=0)


class EerrAccountLine(BaseModel):
    id: str
    kind: str = Field(description="income | expense | cost")
    label: str
    amount: int
    items: list[EerrDetailItem] = Field(default_factory=list)


class EerrMonthResponse(BaseModel):
    branch_office_id: str
    branch_name: str
    year: int
    month: int
    revenue_subtotal: int = Field(ge=0)
    revenue_iva: int = Field(ge=0)
    revenue_total: int = Field(ge=0)
    washer_pay_total: int = Field(ge=0)
    expenses_operational_total: int = Field(ge=0)
    arriendo_total: int = Field(ge=0)
    expenses_total: int = Field(ge=0)
    net_profit: int
    accounts: list[EerrAccountLine]
