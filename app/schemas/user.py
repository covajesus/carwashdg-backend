from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

UserRole = Literal["admin", "manager", "washer"]


class UserCreate(BaseModel):
    fullName: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=255)
    role: UserRole = "washer"
    branchId: str | None = None
    active: bool = True
    statusId: str | None = None


class UserUpdate(BaseModel):
    fullName: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=255)
    role: UserRole | None = None
    branchId: str | None = None
    active: bool | None = None
    statusId: str | None = None


class UserPublic(BaseModel):
    id: str
    fullName: str
    email: str
    role: UserRole
    branchId: str | None = None
    statusId: str | None = None
    active: bool


class UserListResponse(BaseModel):
    items: list[UserPublic]


class UserItemResponse(BaseModel):
    item: UserPublic


class UserDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
