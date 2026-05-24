from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

UserRole = Literal["admin", "manager", "washer"]


class UserCreate(BaseModel):
    fullName: str = Field(default="", max_length=255)
    email: str | None = None
    password: str | None = Field(default=None, min_length=6, max_length=255)
    role: UserRole = "washer"
    branchOfficeId: int | None = Field(default=None, ge=1)
    weekPercentage: str | None = Field(default=None, max_length=255)
    sundayPercentage: str | None = Field(default=None, max_length=255)
    dailyGoal: str | None = Field(default=None, max_length=255)
    dailyGoalPercentage: str | None = Field(default=None, max_length=255)
    active: bool = True
    statusId: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def validate_profile(self) -> "UserCreate":
        if not self.fullName.strip():
            raise ValueError("El nombre completo es obligatorio")
        if self.role != "washer":
            pwd = (self.password or "").strip()
            if len(pwd) < 6:
                raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return self


class UserUpdate(BaseModel):
    fullName: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = None
    password: str | None = Field(default=None, min_length=6, max_length=255)
    role: UserRole | None = None
    branchOfficeId: int | None = Field(default=None, ge=1)
    weekPercentage: str | None = Field(default=None, max_length=255)
    sundayPercentage: str | None = Field(default=None, max_length=255)
    dailyGoal: str | None = Field(default=None, max_length=255)
    dailyGoalPercentage: str | None = Field(default=None, max_length=255)
    active: bool | None = None
    statusId: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        text = str(value).strip()
        return text or None


class UserPublic(BaseModel):
    id: str
    fullName: str
    email: str
    role: UserRole
    roleLabel: str
    branchOfficeId: int | None = Field(default=None, ge=1)
    weekPercentage: str | None = None
    sundayPercentage: str | None = None
    dailyGoal: str | None = None
    dailyGoalPercentage: str | None = None
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
