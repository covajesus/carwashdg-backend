from pydantic import BaseModel, Field


class RaffleCreate(BaseModel):
    raffle: str = Field(..., min_length=1, max_length=255)
    start_date: str = Field(..., min_length=1)
    end_date: str = Field(..., min_length=1)


class RaffleUpdate(BaseModel):
    raffle: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: str | None = None
    end_date: str | None = None


class RafflePublic(BaseModel):
    id: str
    raffle: str
    start_date: str | None = None
    end_date: str | None = None
    added_date: str | None = None
    updated_date: str | None = None
    deleted_date: str | None = None


class RaffleListResponse(BaseModel):
    items: list[RafflePublic]


class RaffleItemResponse(BaseModel):
    item: RafflePublic


class RaffleCurrentResponse(BaseModel):
    item: RafflePublic | None = None


class RaffleDeleteResponse(BaseModel):
    ok: bool = True


class RaffleAssignmentPublic(BaseModel):
    raffle_id: str
    raffle_name: str
    number: int


class RaffleNumberPublic(BaseModel):
    id: str
    raffle_id: str
    customer_id: str | None = None
    ticket_id: str | None = None
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
