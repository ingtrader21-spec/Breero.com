import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ApprovalStatus


class CatalogSkillRead(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    category: str
    description: str | None
    provider_approval_required: bool


class CatalogSkillList(BaseModel):
    items: list[CatalogSkillRead]
    total: int


class RequiredSkillRead(CatalogSkillRead):
    required: bool


class ProviderServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: uuid.UUID
    display_order: int = Field(default=0, ge=0, le=10000)


class ProviderServiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=10000)

    @model_validator(mode="after")
    def validate_patch(self) -> "ProviderServiceUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one provider-service field is required")
        return self


class ProviderServiceRead(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    service_id: uuid.UUID
    service_slug: str
    service_name: str
    service_category: str
    status: ApprovalStatus
    active: bool
    display_order: int
    provider_approval_required: bool
    required_skills: list[RequiredSkillRead]
    version: int
    created_at: datetime
    updated_at: datetime


class ProviderServiceList(BaseModel):
    items: list[ProviderServiceRead]
    total: int


class ProviderSkillCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: uuid.UUID
    worker_id: uuid.UUID | None = None


class ProviderSkillRead(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    worker_id: uuid.UUID
    skill: CatalogSkillRead
    status: ApprovalStatus
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ProviderSkillList(BaseModel):
    items: list[ProviderSkillRead]
    total: int
