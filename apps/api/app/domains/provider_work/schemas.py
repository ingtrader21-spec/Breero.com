import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.dispatch.models import OfferStatus
from app.domains.jobs.models import JobStatus


class ProviderJobRead(BaseModel):
    """Job fields a provider may see; customer identity and pricing are excluded."""

    id: uuid.UUID
    booking_id: uuid.UUID
    service_id: uuid.UUID
    service_name: str | None
    status: JobStatus
    scheduled_start: datetime
    scheduled_end: datetime
    worker_id: uuid.UUID | None
    completed_at: datetime | None
    updated_at: datetime | None


class ProviderJobList(BaseModel):
    items: list[ProviderJobRead]
    total: int


class ProviderOfferRead(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    worker_id: uuid.UUID | None
    status: OfferStatus
    round: int
    expires_at: datetime
    responded_at: datetime | None
    created_at: datetime | None
    job_status: JobStatus | None
    service_id: uuid.UUID | None
    service_name: str | None
    scheduled_start: datetime | None
    scheduled_end: datetime | None


class ProviderOfferList(BaseModel):
    items: list[ProviderOfferRead]
    total: int


class ProviderOfferDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept: bool
    worker_id: uuid.UUID | None = None
