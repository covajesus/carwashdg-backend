from pydantic import BaseModel, Field, model_validator


class WasherDailyGroupMemberPublic(BaseModel):
    washer_id: str
    full_name: str


class WasherDailyGroupPublic(BaseModel):
    id: str
    branch_office_id: str
    group_date: str
    name: str
    members: list[WasherDailyGroupMemberPublic] = Field(default_factory=list)


class WasherDailyGroupListResponse(BaseModel):
    branch_office_id: str
    group_date: str
    items: list[WasherDailyGroupPublic]


class WasherDailyGroupItemResponse(BaseModel):
    item: WasherDailyGroupPublic


class WasherDailyGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    washer_ids: list[int] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_members(self) -> "WasherDailyGroupCreate":
        unique = list(dict.fromkeys(self.washer_ids))
        if len(unique) != len(self.washer_ids):
            raise ValueError("No repita lavadores en el grupo")
        if any(w < 1 for w in unique):
            raise ValueError("Lavador no válido")
        self.washer_ids = unique
        return self


class WasherDailyGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    washer_ids: list[int] | None = None

    @model_validator(mode="after")
    def validate_members(self) -> "WasherDailyGroupUpdate":
        if self.washer_ids is None:
            return self
        unique = list(dict.fromkeys(self.washer_ids))
        if len(unique) != len(self.washer_ids):
            raise ValueError("No repita lavadores en el grupo")
        if len(unique) < 1:
            raise ValueError("Seleccione al menos un lavador")
        if any(w < 1 for w in unique):
            raise ValueError("Lavador no válido")
        self.washer_ids = unique
        return self


class WasherDailyGroupDeleteResponse(BaseModel):
    ok: bool = True


class TicketWasherOptionWasher(BaseModel):
    kind: str = "washer"
    id: str
    full_name: str


class TicketWasherOptionGroup(BaseModel):
    kind: str = "group"
    id: str
    name: str
    member_names: list[str] = Field(default_factory=list)


class TicketWasherOptionsResponse(BaseModel):
    branch_office_id: str
    group_date: str
    washers: list[TicketWasherOptionWasher]
    groups: list[TicketWasherOptionGroup]


class ErrorResponse(BaseModel):
    error: str
