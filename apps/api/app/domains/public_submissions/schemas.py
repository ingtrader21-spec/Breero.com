import re
import uuid
from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import AnyHttpUrl, BaseModel, EmailStr, Field, field_validator, model_validator

from app.domains.common.us import US_STATES_AND_DC

from .consent import CONSENT_DISCLOSURES_BY_POLICY, CONSENT_FLAGS

SERVICE_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LEGACY_CONSENT_FLAGS = ("marketing_consent", "sms_consent", "email_consent")


class TrackingFields(BaseModel):
    source_url: AnyHttpUrl
    utm_source: str | None = Field(default=None, max_length=120)
    utm_medium: str | None = Field(default=None, max_length=120)
    utm_campaign: str | None = Field(default=None, max_length=120)
    utm_content: str | None = Field(default=None, max_length=120)
    utm_term: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=16)
    customer_timezone: str | None = Field(default=None, max_length=64)
    transactional_contact_allowed: bool = False
    transactional_email_consent: bool = False
    transactional_sms_consent: bool = False
    marketing_email_consent: bool = False
    marketing_sms_consent: bool = False
    consent_disclosures: dict[str, str] = Field(default_factory=dict)
    marketing_consent: bool = False
    sms_consent: bool = False
    email_consent: bool = False
    consent_timestamp: str | None = Field(default=None, max_length=40)
    consent_source: str | None = Field(default=None, max_length=120)
    policy_version: str | None = Field(default=None, max_length=40)
    company: str = Field(default="", max_length=0, exclude=True)

    @field_validator("consent_disclosures")
    @classmethod
    def bounded_consent_disclosures(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 10:
            raise ValueError("At most 10 consent disclosures may be supplied")
        for key, disclosure in value.items():
            if not key or len(key) > 80:
                raise ValueError("Consent disclosure keys must contain 1 to 80 characters")
            if not disclosure.strip() or len(disclosure) > 2000:
                raise ValueError("Consent disclosure text must contain 1 to 2000 characters")
        return value

    @model_validator(mode="after")
    def require_versioned_consent_evidence(self) -> Self:
        enabled_legacy = [flag for flag in LEGACY_CONSENT_FLAGS if getattr(self, flag)]
        if enabled_legacy:
            raise ValueError(
                "Legacy aggregate consent flags are not accepted; use the channel-specific flags"
            )

        if any(getattr(self, flag) for flag in CONSENT_FLAGS):
            policy_version = self.policy_version or ""
            if not policy_version:
                raise ValueError("A policy version is required for consent")
            if policy_version not in CONSENT_DISCLOSURES_BY_POLICY:
                raise ValueError("The supplied consent policy version is not supported")
        return self


class ServiceRequestCreate(TrackingFields):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    service_id: uuid.UUID | None = None
    service_slug: str | None = Field(default=None, pattern=SERVICE_SLUG_PATTERN.pattern)
    service_description: str = Field(min_length=5, max_length=4000)
    address_line1: str = Field(min_length=3, max_length=240)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    postal_code: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")
    requested_date: date | None = None
    requested_timing: str | None = Field(default=None, max_length=200)
    contact_preference: Literal["email", "phone", "text"]

    @field_validator("state")
    @classmethod
    def supported_us_state(cls, value: str) -> str:
        if value not in US_STATES_AND_DC:
            raise ValueError("Service requests require a U.S. state or Washington, D.C.")
        return value


class ContactCreate(TrackingFields):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, min_length=7, max_length=40)
    category: Literal[
        "booking_help",
        "service_issue",
        "billing",
        "general",
        "business",
        "privacy_request",
        "provider_question",
    ]
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=10, max_length=5000)


class ProviderInterestCreate(TrackingFields):
    business_name: str = Field(min_length=2, max_length=200)
    contact_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    business_website: AnyHttpUrl | None = None
    service_categories: list[str] = Field(min_length=1, max_length=20)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    postal_code: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")
    license_details: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=3000)

    @field_validator("state")
    @classmethod
    def supported_us_state(cls, value: str) -> str:
        if value not in US_STATES_AND_DC:
            raise ValueError("Provider interest requires a U.S. state or Washington, D.C.")
        return value

    @field_validator("service_categories")
    @classmethod
    def valid_unique_service_categories(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value]
        if any(not SERVICE_SLUG_PATTERN.fullmatch(item) for item in normalized):
            raise ValueError("Service categories must use lowercase service slugs")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Service categories must be unique")
        return normalized


class SubmissionAccepted(BaseModel):
    request_id: uuid.UUID
    status: Literal["REQUEST_ACCEPTED"] = "REQUEST_ACCEPTED"
    downstream_status: str


class DispatcherAuditEntry(BaseModel):
    action: str
    actor_id: uuid.UUID | None
    metadata: dict[str, Any]
    created_at: datetime


class DispatcherQueueItem(BaseModel):
    request_id: uuid.UUID
    submission_type: str
    created_at: datetime
    request_age_seconds: int
    required_follow_up: bool
    customer_timezone: str | None
    address_verification_state: str | None
    manual_dispatch_state: str | None
    provider_assigned: bool
    contact_attempts: list[dict[str, Any]]
    downstream_status: str
    payload: dict[str, Any]
    audit_history: list[DispatcherAuditEntry]


class DispatcherQueueUpdate(BaseModel):
    manual_dispatch_state: Literal[
        "PENDING_MANUAL_DISPATCH",
        "CUSTOMER_CONTACT_PENDING",
        "CUSTOMER_CONTACTED",
        "ADDRESS_VALIDATION_PENDING",
        "PROVIDER_MATCH_PENDING",
        "QUOTE_COORDINATION_PENDING",
        "CANCELLED",
        "CLOSED",
    ] | None = None
    address_verification_state: Literal[
        "PENDING_MANUAL_VALIDATION", "MANUALLY_VERIFIED", "REJECTED"
    ] | None = None
    address_timezone: str | None = Field(default=None, max_length=64)
    contact_outcome: Literal[
        "NO_ANSWER", "VOICEMAIL", "CUSTOMER_REACHED", "FOLLOW_UP_REQUESTED", "CANCELLED"
    ] | None = None
    required_follow_up: bool | None = None
    note: str | None = Field(default=None, max_length=1000)
