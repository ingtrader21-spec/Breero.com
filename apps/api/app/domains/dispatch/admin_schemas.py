import uuid

from pydantic import BaseModel, Field


class AdminAssignmentRequest(BaseModel):
    professional_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500)


class AdminUnassignmentRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class CandidateRead(BaseModel):
    provider_id: uuid.UUID
    professional_id: uuid.UUID
    eligibility: bool = True
    score: int
    distance_meters: int | None
    available_capacity_minutes: int
    schedule_match: bool
    service_area_match: bool
    warnings: tuple[str, ...]
