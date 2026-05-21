from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BranchOfficeBase(BaseModel):
    branch_office: str = Field(..., min_length=1, max_length=255)


class BranchOfficeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    active: bool = True


class BranchOfficeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None


class BranchOfficeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_office: str
    added_date: datetime | None = None
    updated_date: datetime | None = None
    deleted_date: datetime | None = None

    @property
    def active(self) -> bool:
        return self.deleted_date is None


class BranchOfficePublic(BaseModel):
    id: str
    name: str
    active: bool


class BranchOfficeListResponse(BaseModel):
    items: list[BranchOfficePublic]


class BranchOfficeItemResponse(BaseModel):
    item: BranchOfficePublic


class BranchOfficeDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
