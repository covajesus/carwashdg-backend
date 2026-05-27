from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ManagementTypeId = Literal[1, 2]


class BranchOfficeBase(BaseModel):
    branch_office: str = Field(..., min_length=1, max_length=255)


class BranchOfficeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    active: bool = True
    managementTypeId: ManagementTypeId = Field(..., description="1=Administrada, 2=Subarriendo")


class BranchOfficeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None
    managementTypeId: ManagementTypeId | None = None


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
    managementTypeId: int = 1


class BranchOfficeListResponse(BaseModel):
    items: list[BranchOfficePublic]


class BranchOfficeItemResponse(BaseModel):
    item: BranchOfficePublic


class BranchOfficeDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
