from pydantic import BaseModel, Field


class DashboardHomeSummaryResponse(BaseModel):
    year: int
    month: int
    revenue_subtotal: int = Field(ge=0)
    expenses_total: int = Field(ge=0)
