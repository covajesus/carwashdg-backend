from typing import Literal

from pydantic import BaseModel, Field

WasherPayPaymentStatus = Literal["paid", "unpaid"]


class WasherPaySummaryItem(BaseModel):
    washer_id: str
    full_name: str
    amount: int = Field(ge=0)
    ticket_count: int = Field(ge=0)
    applied_percentage: str | None = None
    payment_status: WasherPayPaymentStatus = "unpaid"


class WasherPaySummaryResponse(BaseModel):
    branch_office_id: str
    branch_name: str
    date: str
    items: list[WasherPaySummaryItem]
    amount: int = Field(ge=0)


WasherPayPercentageScope = Literal["day", "group_average"]


class WasherPayDetailLine(BaseModel):
    kind: str
    ticket_id: str | None = None
    label: str
    description: str
    base_amount: int = Field(ge=0)
    line_gross_net: int | None = Field(
        default=None,
        ge=0,
        description="Monto neto total de la línea antes de repartir en grupo",
    )
    group_member_count: int | None = Field(default=None, ge=1)
    percentage: str | None = None
    percentage_scope: WasherPayPercentageScope = "day"
    percentage_label: str | None = None
    day_percentage: str | None = None
    amount: int = Field(ge=0)


class WasherPayDetailResponse(BaseModel):
    washer_id: str
    full_name: str
    branch_office_id: str
    branch_name: str
    date: str
    daily_sales: int = Field(ge=0)
    daily_goal: str | None = None
    daily_goal_percentage: str | None = None
    week_percentage: str | None = None
    sunday_percentage: str | None = None
    applied_percentage: str | None = None
    applied_percentage_label: str | None = None
    goal_met: bool = False
    commission_total: int = Field(ge=0)
    goal_bonus: int = Field(ge=0)
    items: list[WasherPayDetailLine]
    amount: int = Field(ge=0)
    payment_status: WasherPayPaymentStatus = "unpaid"


class WasherPayStatusUpdate(BaseModel):
    payment_status: WasherPayPaymentStatus


class WasherPayStatusResponse(BaseModel):
    washer_id: str
    branch_office_id: str
    date: str
    payment_status: WasherPayPaymentStatus
