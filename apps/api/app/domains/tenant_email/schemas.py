import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class TenantScopedInput(BaseModel):
    brand_key: str = Field(default="breero", min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    vendor_id: uuid.UUID | None = None


class EmailDomainCreate(TenantScopedInput):
    domain: str = Field(min_length=3, max_length=253)
    dkim_selector: str | None = Field(default=None, max_length=63)
    return_path_domain: str | None = Field(default=None, max_length=253)

    @field_validator("domain", "return_path_domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().rstrip(".")
        if "@" in normalized or " " in normalized or "." not in normalized:
            raise ValueError("invalid email domain")
        return normalized


class EmailDomainRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    brand_key: str
    vendor_id: uuid.UUID | None
    domain: str
    verification_status: str
    dkim_selector: str | None
    return_path_domain: str | None
    active: bool
    created_at: datetime


class EmailSenderCreate(TenantScopedInput):
    domain_id: uuid.UUID
    local_part: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$")
    display_name: str = Field(min_length=1, max_length=160)
    reply_to: EmailStr | None = None


class EmailSenderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    brand_key: str
    vendor_id: uuid.UUID | None
    domain_id: uuid.UUID
    local_part: str
    display_name: str
    reply_to: EmailStr | None
    active: bool
    created_at: datetime


class EmailCredentialCreate(TenantScopedInput):
    provider: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=120)
    username: str | None = Field(default=None, max_length=320)
    secret_ref: str = Field(min_length=8, max_length=255, pattern=r"^breero-email/[A-Za-z0-9._/-]+$")
    smtp_host: str | None = Field(default=None, max_length=253)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    use_tls: bool = True

    @model_validator(mode="after")
    def validate_transport(self) -> "EmailCredentialCreate":
        if self.provider == "smtp" and (not self.smtp_host or not self.smtp_port):
            raise ValueError("smtp credentials require smtp_host and smtp_port")
        return self


class EmailCredentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    brand_key: str
    vendor_id: uuid.UUID | None
    provider: str
    label: str
    username: str | None
    smtp_host: str | None
    smtp_port: int | None
    use_tls: bool
    active: bool
    secret_configured: bool = True
    created_at: datetime


class EmailComposeRequest(TenantScopedInput):
    sender_id: uuid.UUID
    credential_id: uuid.UUID
    to_email: EmailStr
    subject: str = Field(min_length=1, max_length=255)
    text_body: str = Field(min_length=1, max_length=100_000)
    idempotency_key: str = Field(min_length=8, max_length=255)


class EmailMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    brand_key: str
    vendor_id: uuid.UUID | None
    sender_id: uuid.UUID
    credential_id: uuid.UUID
    to_email: EmailStr
    subject: str
    status: str
    idempotency_key: str
    queued_at: datetime | None
    delivered_at: datetime | None
    provider_message_id: str | None
    created_at: datetime


class EmailOutboxRead(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    status: str
    attempts: int
    next_attempt_at: datetime
    last_error_code: str | None = None
