import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .catalog import AuditCategory, AuditResult

MetadataScalar = str | int | float | bool | None
MetadataValue = MetadataScalar | list[str | int | float | bool]


class AuditActor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID | None
    type: str


class AuditResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    id: uuid.UUID


class AuditEventSummary(BaseModel):
    """Admin-safe projection of one audit row. Never includes raw metadata."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    occurred_at: datetime
    category: AuditCategory
    action: str
    result: AuditResult
    actor: AuditActor
    resource: AuditResource
    vendor_id: uuid.UUID | None
    request_id: str | None
    correlation_id: str | None
    security_relevant: bool


class AuditEventDetail(AuditEventSummary):
    metadata: dict[str, MetadataValue] = Field(
        description="Allowlisted, length-bounded metadata. Unlisted keys are withheld."
    )
    metadata_withheld_keys: int = Field(
        ge=0, description="Number of stored metadata keys not exposed by the allowlist."
    )
    source_fingerprint: str | None = Field(
        description="Truncated keyed hash of the request source; never a raw address."
    )


class AuditEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEventSummary]
    next_cursor: str | None
    limit: int
    occurred_from: datetime
    occurred_to: datetime


class AuditCorrelationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    items: list[AuditEventDetail]
    truncated: bool


class AuditFilterLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_window_days: int
    max_window_days: int
    default_page_size: int
    max_page_size: int
    max_trace_events: int


class AuditCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[AuditCategory]
    security_categories: list[AuditCategory]
    security_actions: list[str]
    results: list[AuditResult]
    limits: AuditFilterLimits
    retention: dict[str, Any]
