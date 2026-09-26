import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import QualificationReviewStatus, QualificationStatus, QualificationType

# Opaque evidence references only: no scheme separators or path characters, so a
# provider cannot plant a clickable URL or storage path for reviewers.
EVIDENCE_REFERENCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
JURISDICTION_PATTERN = r"^[A-Z]{2,3}$"
REFERENCE_LAST4_PATTERN = r"^[A-Za-z0-9]{4}$"
EXPIRY_REQUIRED_TYPES = frozenset({QualificationType.LICENSE, QualificationType.INSURANCE})


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class QualificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_id: uuid.UUID | None = None
    qualification_type: QualificationType
    title: str = Field(min_length=1, max_length=160)
    issuer: str | None = Field(default=None, max_length=160)
    jurisdiction: str | None = Field(default=None, pattern=JURISDICTION_PATTERN)
    reference_last4: str | None = Field(default=None, pattern=REFERENCE_LAST4_PATTERN)
    issued_on: date | None = None
    expires_on: date | None = None
    evidence_reference: str | None = Field(default=None, pattern=EVIDENCE_REFERENCE_PATTERN)

    @model_validator(mode="after")
    def validate_record(self) -> "QualificationCreate":
        title = _normalize_text(self.title)
        if not title:
            raise ValueError("title is required")
        self.title = title
        self.issuer = _normalize_text(self.issuer)
        if self.issued_on and self.expires_on and self.issued_on > self.expires_on:
            raise ValueError("issued_on must not be after expires_on")
        return self


class QualificationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    issuer: str | None = Field(default=None, max_length=160)
    jurisdiction: str | None = Field(default=None, pattern=JURISDICTION_PATTERN)
    reference_last4: str | None = Field(default=None, pattern=REFERENCE_LAST4_PATTERN)
    issued_on: date | None = None
    expires_on: date | None = None
    evidence_reference: str | None = Field(default=None, pattern=EVIDENCE_REFERENCE_PATTERN)

    @model_validator(mode="after")
    def validate_patch(self) -> "QualificationUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one qualification field is required")
        if "title" in self.model_fields_set:
            title = _normalize_text(self.title)
            if not title:
                raise ValueError("title cannot be cleared")
            self.title = title
        if "issuer" in self.model_fields_set:
            self.issuer = _normalize_text(self.issuer)
        return self


class QualificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: uuid.UUID
    worker_id: uuid.UUID | None
    qualification_type: QualificationType
    title: str
    issuer: str | None
    jurisdiction: str | None
    reference_last4: str | None
    issued_on: date | None
    expires_on: date | None
    evidence_reference: str | None
    status: QualificationStatus
    review_status: QualificationReviewStatus
    review_reason: str | None
    reviewed_at: datetime | None
    submitted_at: datetime | None
    is_expired: bool = False
    version: int
    created_at: datetime
    updated_at: datetime


class EvidenceStorageRead(BaseModel):
    upload_enabled: bool
    reason: str


class QualificationList(BaseModel):
    items: list[QualificationRead]
    total: int
    evidence_storage: EvidenceStorageRead


class QualificationReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROVED", "REJECTED", "INFORMATION_REQUESTED"]
    reason: str = Field(min_length=3, max_length=1000)
