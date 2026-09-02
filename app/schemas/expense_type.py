from typing import Literal

from pydantic import BaseModel, Field

ExpenseClassification = Literal["cash", "bank"]


class ExpenseTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    classification: ExpenseClassification = "bank"
    adminOnly: bool = False
    requiresPhoto: bool = True


class ExpenseTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    classification: ExpenseClassification | None = None
    adminOnly: bool | None = None
    requiresPhoto: bool | None = None


class ExpenseTypePublic(BaseModel):
    id: str
    code: str
    name: str
    classification: ExpenseClassification
    classificationLabel: str
    adminOnly: bool = False
    requiresPhoto: bool = True
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class ExpenseTypeListResponse(BaseModel):
    items: list[ExpenseTypePublic]


class ExpenseTypeItemResponse(BaseModel):
    item: ExpenseTypePublic


class ExpenseTypeDeleteResponse(BaseModel):
    ok: bool = True
