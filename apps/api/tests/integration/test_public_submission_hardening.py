import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.core.errors import DomainError
from app.db.session import SessionLocal
from app.domains.catalog.models import Service
from app.domains.common.outbox import IntegrationEvent
from app.domains.public_submissions.models import PublicSubmission, SubmissionType
from app.domains.public_submissions.schemas import ServiceRequestCreate
from app.domains.public_submissions.service import PublicSubmissionService


def service_request(marker: str, service_slug: str, description: str) -> ServiceRequestCreate:
    return ServiceRequestCreate(
        name="Concurrent Customer",
        email=f"concurrent-{marker}@example.com",
        phone="+1 281 555 0199",
        service_slug=service_slug,
        service_description=description,
        address_line1="1 Main Street",
        city="Houston",
        state="TX",
        postal_code="77002",
        contact_preference="email",
        source_url="https://staging.breero.com/request-service",
        transactional_contact_allowed=True,
        consent_source="integration_test",
        policy_version="2026-08-13-request-only",
    )


@pytest.mark.asyncio
async def test_concurrent_same_payload_has_one_submission_and_event(monkeypatch) -> None:
    monkeypatch.setattr(settings, "middleware_enabled", False)
    marker = uuid.uuid4().hex
    service_slug = f"concurrent-service-{marker}"
    idempotency_key = f"concurrent-key-{marker}"

    async with SessionLocal() as session:
        session.add(
            Service(
                slug=service_slug,
                name="Concurrent test service",
                description="Test-only service",
                category="home-services",
                pricing_model="quote_required",
                is_active=True,
                is_bookable=False,
                sort_order=999,
            )
        )
        await session.commit()

    payload = service_request(marker, service_slug, "The same concurrent request body")

    async def submit():
        async with SessionLocal() as session:
            return await PublicSubmissionService(session).accept(
                SubmissionType.SERVICE_REQUEST,
                payload,
                idempotency_key,
                "192.0.2.30",
            )

    first, second = await asyncio.gather(submit(), submit())
    assert first.request_id == second.request_id

    async with SessionLocal() as session:
        submission_count = await session.scalar(
            select(func.count())
            .select_from(PublicSubmission)
            .where(
                PublicSubmission.submission_type == SubmissionType.SERVICE_REQUEST,
                PublicSubmission.idempotency_key == idempotency_key,
            )
        )
        event_count = await session.scalar(
            select(func.count())
            .select_from(IntegrationEvent)
            .where(IntegrationEvent.aggregate_id == first.request_id)
        )
    assert submission_count == 1
    assert event_count == 1


@pytest.mark.asyncio
async def test_concurrent_different_payloads_conflict(monkeypatch) -> None:
    monkeypatch.setattr(settings, "middleware_enabled", False)
    marker = uuid.uuid4().hex
    service_slug = f"conflict-service-{marker}"
    idempotency_key = f"conflict-key-{marker}"

    async with SessionLocal() as session:
        session.add(
            Service(
                slug=service_slug,
                name="Conflict test service",
                description="Test-only service",
                category="home-services",
                pricing_model="quote_required",
                is_active=True,
                is_bookable=False,
                sort_order=999,
            )
        )
        await session.commit()

    payloads = (
        service_request(marker, service_slug, "First concurrent request body"),
        service_request(marker, service_slug, "Second concurrent request body"),
    )

    async def submit(payload: ServiceRequestCreate):
        async with SessionLocal() as session:
            return await PublicSubmissionService(session).accept(
                SubmissionType.SERVICE_REQUEST,
                payload,
                idempotency_key,
                "192.0.2.31",
            )

    results = await asyncio.gather(*(submit(payload) for payload in payloads), return_exceptions=True)
    accepted = [result for result in results if not isinstance(result, Exception)]
    rejected = [result for result in results if isinstance(result, DomainError)]

    assert len(accepted) == 1
    assert len(rejected) == 1
    assert rejected[0].code == "IDEMPOTENCY_CONFLICT"

    async with SessionLocal() as session:
        submission_count = await session.scalar(
            select(func.count())
            .select_from(PublicSubmission)
            .where(
                PublicSubmission.submission_type == SubmissionType.SERVICE_REQUEST,
                PublicSubmission.idempotency_key == idempotency_key,
            )
        )
    assert submission_count == 1
