from pydantic import BaseModel, ConfigDict


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    github_login: str
    email: str | None = None
    avatar_url: str | None = None


class LoginUrlResponse(BaseModel):
    url: str
