from pydantic import BaseModel, Field


class RaffleCreate(BaseModel):
    status_id: int | None = None
    raffle: str = Field(..., min_length=1, max_length=255)


class RaffleUpdate(BaseModel):
    status_id: int | None = None
    raffle: str | None = Field(default=None, min_length=1, max_length=255)


class RafflePublic(BaseModel):
    id: str
    status_id: str | None = None
    raffle: str
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class RaffleListResponse(BaseModel):
    items: list[RafflePublic]


class RaffleItemResponse(BaseModel):
    item: RafflePublic


class RaffleDeleteResponse(BaseModel):
    ok: bool = True


class RaffleNumberPublic(BaseModel):
    id: str
    raffle_id: str
    number: int
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class RaffleNumberListResponse(BaseModel):
    items: list[RaffleNumberPublic]


class RaffleDrawResponse(BaseModel):
    item: RaffleNumberPublic


class ErrorResponse(BaseModel):
    error: str
