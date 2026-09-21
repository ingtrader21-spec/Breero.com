import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.finance.schemas import EarningRead, PayoutBatchRead
from app.domains.jobs.schemas import JobRead
from app.domains.workforce.schemas import (
    ProviderApplicationRead,
    ProviderCredentialRead,
    VendorRead,
    WorkerRead,
)


class EffectiveCapabilities(BaseModel):
    request_intake: bool
    scheduling: bool
    instant_booking: bool
    online_payments: bool
    payouts: bool
    automatic_assignment: bool
    provider_self_service: bool
    marketplace_matching: bool
    messaging: bool
    reviews: bool
    middleware_delivery: bool
    transactional_email_mode: str
    transactional_sms_mode: str


class StatusCount(BaseModel):
    status: str
    count: int


class MoneyStatus(BaseModel):
    status: str
    currency: str
    count: int
    amount_minor: int


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


class ProviderOverview(BaseModel):
    vendor: VendorRead
    application: ProviderApplicationRead | None
    capabilities: EffectiveCapabilities
    workers_total: int
    workers_available: int
    services_active: int
    skills_active: int
    credentials_total: int
    credentials_verified: int
    credentials_expiring_soon: int
    jobs: list[StatusCount]
    earnings: list[MoneyStatus]
    recent_jobs: list[JobRead]
    recent_earnings: list[EarningRead]
    recent_payout_batches: list[PayoutBatchRead]


class OperationsOverview(BaseModel):
    capabilities: EffectiveCapabilities
    intake_items_total: int
    bookings: list[StatusCount]
    jobs: list[StatusCount]
    vendors: list[StatusCount]
    provider_applications: list[StatusCount]
    outbox: list[StatusCount]
    recent_jobs: list[JobRead]


class AdminOverview(BaseModel):
    capabilities: EffectiveCapabilities
    users_total: int
    users_active: int
    customers_total: int
    service_zones_total: int
    service_zones_active: int
    postal_codes_total: int
    postal_codes_active: int
    bookings: list[StatusCount]
    jobs: list[StatusCount]
    vendors: list[StatusCount]
    provider_applications: list[StatusCount]
    earnings: list[MoneyStatus]
    payout_batches: list[StatusCount]
    outbox: list[StatusCount]
    recent_audit: list[AuditEventRead]


class ProviderJobList(BaseModel):
    items: list[JobRead]
    total: int


class ProviderWorkerList(BaseModel):
    items: list[WorkerRead]
    total: int


class ProviderCredentialList(BaseModel):
    items: list[ProviderCredentialRead]
    total: int


class ProviderEarningList(BaseModel):
    items: list[EarningRead]
    total: int


class ProviderPayoutBatchList(BaseModel):
    items: list[PayoutBatchRead]
    total: int


class AuditEventList(BaseModel):
    items: list[AuditEventRead]
    total: int
