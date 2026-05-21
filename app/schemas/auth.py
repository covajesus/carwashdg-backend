from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserPublic


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    ok: bool = True
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class LoginErrorResponse(BaseModel):
    ok: bool = False
    error: str


class MeResponse(BaseModel):
    user: UserPublic
