import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.domains.auth.models import UserRole


class AdminUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    role: UserRole

    @model_validator(mode="after")
    def internal_role_only(self) -> "AdminUserCreate":
        if self.role not in {
            UserRole.BREERO_ADMIN,
            UserRole.BREERO_DISPATCH,
            UserRole.BREERO_SUPPORT,
        }:
            raise ValueError("only internal BREERO roles may be provisioned")
        return self


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    password_set_required: bool
    created_at: datetime


class FeatureFlagPatch(BaseModel):
    enabled: bool
    reason: str = Field(min_length=3, max_length=500)


class ProviderApplicationDecision(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class FeatureFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    enabled: bool
    description: str
    updated_at: datetime


class OperatingHourWrite(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_local_time: time
    end_local_time: time
    emergency_only: bool = False
    active: bool = True

    @model_validator(mode="after")
    def ordered(self) -> "OperatingHourWrite":
        if self.end_local_time <= self.start_local_time:
            raise ValueError("end_local_time must be after start_local_time")
        if self.day_of_week != 6 and self.emergency_only:
            raise ValueError("emergency-only operating hours are restricted to Sunday")
        return self


class OperatingHourRead(OperatingHourWrite):
    model_config = ConfigDict(from_attributes=True)
    updated_at: datetime


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_type: str
    action: str
    resource_type: str
    resource_id: uuid.UUID
    metadata_json: dict
    created_at: datetime
