from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    clients: str = Field(..., min_length=1, max_length=255)


class ClientUpdate(BaseModel):
    clients: str | None = Field(default=None, min_length=1, max_length=255)


class ClientPublic(BaseModel):
    id: str
    clients: str
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class ClientListResponse(BaseModel):
    items: list[ClientPublic]


class ClientItemResponse(BaseModel):
    item: ClientPublic


class ClientDeleteResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    error: str
