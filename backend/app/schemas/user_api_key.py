from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserApiKeyCreate(BaseModel):
    api_key: str = Field(min_length=20, max_length=512)


class UserApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    key_last_four: str
    is_valid: bool
    last_validated_at: datetime | None


class UserApiKeyTestResponse(BaseModel):
    valid: bool
    error: str | None = None
