from pydantic import BaseModel, ConfigDict, Field


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    github_login: str
    email: str | None = None
    avatar_url: str | None = None


class LoginUrlResponse(BaseModel):
    url: str


class SmtpSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    smtp_host: str | None
    smtp_port: int | None
    smtp_username: str | None
    smtp_from: str | None
    smtp_use_tls: bool
    notify_email_enabled: bool
    password_set: bool


class SmtpSettingsUpdate(BaseModel):
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=255)
    smtp_password: str | None = Field(default=None, max_length=255)
    smtp_from: str | None = Field(default=None, max_length=320)
    smtp_use_tls: bool | None = None
    notify_email_enabled: bool | None = None
    clear_password: bool = False


class ChatWebhookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url_set: bool
    enabled: bool


class ChatWebhookUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=2048)
    enabled: bool | None = None
    clear: bool = False
