from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConfigurationUpdate(BaseModel):
    phone: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=255)
    facebook_url: str | None = Field(default=None, max_length=255)
    twitter_url: str | None = Field(default=None, max_length=255)
    tiktok_url: str | None = Field(default=None, max_length=255)
    instagram_url: str | None = Field(default=None, max_length=255)


class ConfigurationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    email: str
    address: str
    facebook_url: str
    twitter_url: str
    tiktok_url: str
    instagram_url: str


class ConfigurationPublic(BaseModel):
    phone: str
    email: str
    address: str
    facebook_url: str
    twitter_url: str
    tiktok_url: str
    instagram_url: str
    updated_date: datetime | None = None


class ConfigurationItemResponse(BaseModel):
    item: ConfigurationPublic


class ErrorResponse(BaseModel):
    error: str
