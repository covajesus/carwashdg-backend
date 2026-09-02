from datetime import date, datetime

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    expenseTypeId: int = Field(..., ge=1)
    amount: int = Field(..., ge=1)
    expense_date: date
    photo_url: str | None = None
    branchOfficeId: int | None = Field(default=None, ge=1)


class ExpenseUpdate(BaseModel):
    expenseTypeId: int | None = Field(default=None, ge=1)
    amount: int | None = Field(default=None, ge=1)
    expense_date: date | None = None
    photo_url: str | None = None
    branchOfficeId: int | None = Field(default=None, ge=1)


class ExpensePublic(BaseModel):
    id: str
    expenseTypeId: int | None = Field(default=None, ge=1)
    expense_type: str
    expense_type_label: str
    classification: str | None = None
    classificationLabel: str | None = None
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
    classification: str
    classificationLabel: str
    requiresPhoto: bool = True
    adminOnly: bool = False


class ExpenseTypesResponse(BaseModel):
    items: list[ExpenseTypeOption]
