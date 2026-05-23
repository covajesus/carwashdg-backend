from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

UserRole = Literal["admin", "manager", "washer"]


class UserCreate(BaseModel):
    fullName: str = Field(default="", max_length=255)
    email: EmailStr | None = None
    password: str = Field(..., min_length=6, max_length=255)
    role: UserRole = "washer"
    branchOfficeId: int | None = Field(default=None, ge=1)
    weekPercentage: str | None = Field(default=None, max_length=255)
    sundayPercentage: str | None = Field(default=None, max_length=255)
    dailyGoal: str | None = Field(default=None, max_length=255)
    dailyGoalPercentage: str | None = Field(default=None, max_length=255)
    active: bool = True
    statusId: str | None = None
    isGroupWasher: bool = False
    groupMemberNames: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_profile(self) -> "UserCreate":
        if self.role != "washer":
            if self.isGroupWasher or self.groupMemberNames:
                raise ValueError("Solo los lavadores pueden ser grupales")
            if not self.fullName.strip():
                raise ValueError("El nombre completo es obligatorio")
            if self.email is None or not str(self.email).strip():
                raise ValueError("El correo es obligatorio")
            return self

        if self.isGroupWasher:
            names = [n.strip() for n in self.groupMemberNames if n.strip()]
            if len(names) < 2:
                raise ValueError("Indique al menos 2 nombres para el lavador grupal")
            self.groupMemberNames = names
            return self

        if not self.fullName.strip():
            raise ValueError("El nombre completo es obligatorio")
        return self


class UserUpdate(BaseModel):
    fullName: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=255)
    role: UserRole | None = None
    branchOfficeId: int | None = Field(default=None, ge=1)
    weekPercentage: str | None = Field(default=None, max_length=255)
    sundayPercentage: str | None = Field(default=None, max_length=255)
    dailyGoal: str | None = Field(default=None, max_length=255)
    dailyGoalPercentage: str | None = Field(default=None, max_length=255)
    active: bool | None = None
    statusId: str | None = None
    isGroupWasher: bool | None = None
    groupMemberNames: list[str] | None = None


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
    isGroupWasher: bool = False
    groupMemberNames: list[str] = Field(default_factory=list)


class UserListResponse(BaseModel):
    items: list[UserPublic]


class UserItemResponse(BaseModel):
    item: UserPublic


class UserDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
