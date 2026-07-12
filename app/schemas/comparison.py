from pydantic import BaseModel, Field


class ComparisonDailyPoint(BaseModel):
    day: int = Field(ge=1, le=31)
    current_net: int | None = None
    current_gross: int | None = None
    previous_net: int | None = None
    previous_gross: int | None = None


class ComparisonMonthlyPoint(BaseModel):
    month: int = Field(ge=1, le=12)
    current_net: int = Field(ge=0)
    current_gross: int = Field(ge=0)
    previous_net: int = Field(ge=0)
    previous_gross: int = Field(ge=0)


class ComparisonYearlyPoint(BaseModel):
    year: int
    net: int = Field(ge=0)
    gross: int = Field(ge=0)


class ComparisonResponse(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    branch_office_id: str
    branch_name: str
    previous_year: int
    previous_month: int = Field(ge=1, le=12)
    previous_month_year: int
    daily: list[ComparisonDailyPoint]
    monthly: list[ComparisonMonthlyPoint]
    yearly: list[ComparisonYearlyPoint]
