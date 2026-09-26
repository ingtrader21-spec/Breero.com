import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.jobs.models import JobStatus

from .models import AssignmentStatus, OfferStatus


class OfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    vendor_id: uuid.UUID
    worker_id: uuid.UUID | None
    status: OfferStatus
    score: int
    expires_at: datetime


class OfferDecision(BaseModel):
    accept: bool
    worker_id: uuid.UUID | None = None


class ManualAssignment(BaseModel):
    vendor_id: uuid.UUID
    worker_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=1000)


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    vendor_id: uuid.UUID
    worker_id: uuid.UUID
    status: AssignmentStatus
    assigned_at: datetime


class Reassignment(BaseModel):
    vendor_id: uuid.UUID
    worker_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=1000)
    expected_version: int | None = Field(
        default=None,
        ge=1,
        description="Job version the operator reviewed; a mismatch is rejected with 409.",
    )


class ReassignmentRead(BaseModel):
    assignment: AssignmentRead
    released_assignment_id: uuid.UUID
    job_id: uuid.UUID
    job_status: JobStatus
    job_version: int
