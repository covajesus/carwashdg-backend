from datetime import date, datetime

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    expense_type: str = Field(..., min_length=1, max_length=64)
    amount: int = Field(..., ge=1)
    expense_date: date
    photo_url: str | None = None
    branchOfficeId: int | None = Field(default=None, ge=1)


class ExpenseUpdate(BaseModel):
    expense_type: str | None = Field(default=None, min_length=1, max_length=64)
    amount: int | None = Field(default=None, ge=1)
    expense_date: date | None = None
    photo_url: str | None = None
    branchOfficeId: int | None = Field(default=None, ge=1)


class ExpensePublic(BaseModel):
    id: str
    expense_type: str
    expense_type_label: str
    amount: int = Field(ge=0)
    expense_date: date | None = None
    branchOfficeId: int | None = Field(default=None, ge=1)
    branchOfficeName: str | None = None
    photo_url: str | None = None
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None


class ExpenseListResponse(BaseModel):
    items: list[ExpensePublic]


class ExpenseItemResponse(BaseModel):
    item: ExpensePublic


class ExpenseDeleteResponse(BaseModel):
    ok: bool = True


class ExpenseTypeOption(BaseModel):
    id: str
    label: str


class ExpenseTypesResponse(BaseModel):
    items: list[ExpenseTypeOption]
