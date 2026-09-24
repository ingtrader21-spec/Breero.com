import enum
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsScopeKind(enum.StrEnum):
    marketplace = "marketplace"
    provider = "provider"


class MetricGroupKey(enum.StrEnum):
    request = "request"
    qualification = "qualification"
    matching = "matching"
    opportunity = "opportunity"
    quote = "quote"
    booking = "booking"
    utilization = "utilization"
    completion = "completion"
    cancellation = "cancellation"
    review = "review"
    response_time = "response_time"
    finance = "finance"


class MetricGroupStatus(enum.StrEnum):
    available = "available"
    """Computed from the source of record for the requested scope and window."""
    unavailable = "unavailable"
    """No certified source of record exists yet; no value is fabricated."""
    restricted = "restricted"
    """The source exists but cannot be attributed to the caller's tenant scope."""


MetricUnit = Literal["count", "ratio", "seconds"]


class AnalyticsScopeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AnalyticsScopeKind
    vendor_id: uuid.UUID | None = None


class AnalyticsWindowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime


class AnalyticsProjectionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field(
        default="live_read_model",
        description="Figures are computed at read time from source-of-record tables.",
    )
    source_of_record: str = "postgresql"
    consistency: str = Field(
        default="repeatable_read_snapshot",
        description="All groups in one response are read from one database snapshot.",
    )
    max_age_seconds: int = Field(
        description="Clients must treat the response as stale after this many seconds.",
    )


class MetricValueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    unit: MetricUnit
    value: float | int | None = Field(
        description="Null when the value is undefined, e.g. a rate with a zero denominator.",
    )
    numerator: int | None = None
    denominator: int | None = None


class MetricGroupRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: MetricGroupKey
    label: str
    status: MetricGroupStatus
    reason: str | None = None
    note: str | None = Field(
        default=None,
        description="Interpretation caveat for available groups.",
    )
    blocked_by: str | None = Field(
        default=None,
        description="Delivery dependency that must land before this group can be projected.",
    )
    sources: list[str] = Field(default_factory=list)
    source_watermark: datetime | None = Field(
        default=None,
        description="Latest source-row change inside the scope and window.",
    )
    values: list[MetricValueRead] = Field(default_factory=list)


class MarketplaceMetricsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: AnalyticsScopeRead
    window: AnalyticsWindowRead
    generated_at: datetime
    projection: AnalyticsProjectionRead
    groups: list[MetricGroupRead]
