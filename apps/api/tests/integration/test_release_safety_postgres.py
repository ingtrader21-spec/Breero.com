import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, select

from app.api.internal_odoo import failures
from app.db.session import SessionLocal
from app.domains.booking.models import (
    Address,
    Booking,
    BookingStatus,
    Customer,
    LegalEntity,
    ServiceArea,
)
from app.domains.booking.repository import BookingRepository
from app.domains.catalog.models import Service
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.common.outbox_service import OutboxService
from app.domains.compliance.models import ConsentEvent, Suppression
from app.domains.compliance.schemas import CommunicationPreferenceCreate
from app.domains.compliance.service import ComplianceService, digest
from app.domains.public_submissions.models import (
    DownstreamStatus,
    PublicSubmission,
    SubmissionType,
)
from app.domains.workforce.models import Vendor, VendorStatus, Worker, WorkerStatus


def booking(
    *,
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    legal_entity_id: uuid.UUID,
    service_id: uuid.UUID,
    worker_id: uuid.UUID,
    start: datetime,
    status: BookingStatus,
    expires_at: datetime,
    marker: str,
) -> Booking:
    return Booking(
        reference=f"RS-{marker[-8:]}-{status.value[:3]}",
        idempotency_key=f"release-safety-{marker}-{status.value}",
        idempotency_request_hash=marker.ljust(64, "0")[:64],
        customer_id=customer_id,
        address_id=address_id,
        legal_entity_id=legal_entity_id,
        service_id=service_id,
        provider_worker_id=worker_id,
        window_start=start,
        window_end=start + timedelta(hours=1),
        status=status,
        pricing_snapshot={"release_safety_test": True},
        total_amount=Decimal("0.00"),
        currency="USD",
        expires_at=expires_at,
        guest_confirmation_token_hash=marker.ljust(64, "1")[:64],
        guest_confirmation_expires_at=start + timedelta(days=1),
    )


@pytest.mark.asyncio
async def test_expired_holds_do_not_consume_service_or_provider_capacity() -> None:
    marker = uuid.uuid4().hex
    now = datetime.now(UTC)
    start = now + timedelta(days=3)
    async with SessionLocal() as session:
        entity = LegalEntity(code=f"RS-{marker[:8]}", name="Release Safety", currency="USD")
        service = Service(
            slug=f"release-safety-{marker}",
            name="Release safety",
            category="home-services",
            pricing_model="quote_required",
            is_active=True,
            is_bookable=True,
        )
        customer = Customer(
            first_name="Release",
            last_name="Safety",
            email=f"release-safety-{marker}@example.com",
            phone="+12815550100",
        )
        vendor = Vendor(
            legal_name=f"Release Safety {marker}",
            display_name="Release Safety",
            email=f"provider-{marker}@example.com",
            phone="+12815550101",
            status=VendorStatus.ACTIVE,
            capabilities=["release-safety"],
        )
        session.add_all([entity, service, customer, vendor])
        await session.flush()
        area = ServiceArea(
            legal_entity_id=entity.id,
            name="Release safety area",
            country_code="US",
            state_code="TX",
            city="Cypress",
            postal_codes=["77433"],
            boundary=WKTElement(
                "MULTIPOLYGON(((-95.8 29.8,-95.5 29.8,-95.5 30.1,-95.8 30.1,-95.8 29.8)))",
                srid=4326,
            ),
            active=True,
        )
        worker = Worker(
            vendor_id=vendor.id,
            first_name="Release",
            last_name="Worker",
            email=f"worker-{marker}@example.com",
            phone="+12815550102",
            status=WorkerStatus.ACTIVE,
            skills=["release-safety"],
            available=True,
        )
        session.add_all([area, worker])
        await session.flush()
        address = Address(
            formatted_address="20633 Longenbaugh Rd, Cypress, TX 77433",
            line1="20633 Longenbaugh Rd",
            city="Cypress",
            state_code="TX",
            postal_code="77433",
            country_code="US",
            location=WKTElement("POINT(-95.7 29.9)", srid=4326),
            service_area_id=area.id,
            geocoding_provider="release-safety-test",
            timezone_name="America/Chicago",
            customer_id=customer.id,
        )
        session.add(address)
        await session.flush()

        rows = [
            booking(
                customer_id=customer.id,
                address_id=address.id,
                legal_entity_id=entity.id,
                service_id=service.id,
                worker_id=worker.id,
                start=start,
                status=status,
                expires_at=expiry,
                marker=f"{marker}{index}",
            )
            for index, (status, expiry) in enumerate(
                [
                    (BookingStatus.TENTATIVE_HOLD, now - timedelta(minutes=1)),
                    (BookingStatus.PENDING_PROVIDER_CONFIRMATION, now - timedelta(minutes=1)),
                    (BookingStatus.TENTATIVE_HOLD, now + timedelta(minutes=30)),
                    (BookingStatus.PENDING_PROVIDER_CONFIRMATION, now + timedelta(minutes=30)),
                    (BookingStatus.CONFIRMED, now - timedelta(minutes=1)),
                ]
            )
        ]
        session.add_all(rows)
        await session.commit()

        repository = BookingRepository(session)
        assert await repository.booking_count(service.id, start, start + timedelta(hours=1)) == 3
        assert await repository.provider_booking_count(
            worker.id, start, start + timedelta(hours=1)
        ) == 3


@pytest.mark.asyncio
async def test_activation_and_manual_retry_deliver_once_and_are_audited() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(AuditLog))
        await session.execute(delete(IntegrationEvent))
        await session.commit()
        now = datetime.now(UTC)
        activated = IntegrationEvent(
            aggregate_type="public_submission",
            aggregate_id=uuid.uuid4(),
            event_type="breero.service_request.created",
            idempotency_key=f"activate:{uuid.uuid4()}",
            payload={},
            status=EventStatus.PENDING_CONFIGURATION,
            next_attempt_at=now,
        )
        unrelated = IntegrationEvent(
            aggregate_type="professional_lead",
            aggregate_id=uuid.uuid4(),
            event_type="breero.professional_lead.created",
            idempotency_key=f"unrelated:{uuid.uuid4()}",
            payload={},
            status=EventStatus.PENDING_CONFIGURATION,
            next_attempt_at=now,
        )
        terminal = IntegrationEvent(
            aggregate_type="public_submission",
            aggregate_id=uuid.uuid4(),
            event_type="breero.contact_request.created",
            idempotency_key=f"retry:{uuid.uuid4()}",
            payload={},
            status=EventStatus.FAILED_TERMINAL,
            next_attempt_at=now,
            attempt_count=5,
            last_error_code="TEST_TERMINAL",
            last_error="Safe terminal failure",
        )
        session.add_all([activated, unrelated, terminal])
        await session.commit()

        listed = await failures(session=session, _=None)
        assert [row["event_id"] for row in listed] == [terminal.id]

        outbox = OutboxService(session)
        assert await outbox.activate_pending_configuration() == 1
        assert await outbox.activate_pending_configuration() == 0
        actor_id = uuid.uuid4()
        await outbox.retry(terminal.id, actor_id)
        with pytest.raises(ValueError, match="Only failed or configuration-pending integration events"):
            await outbox.retry(terminal.id, actor_id)

        deliveries: list[uuid.UUID] = []

        async def deliver(event: IntegrationEvent) -> None:
            deliveries.append(event.id)

        assert await outbox.process(deliver) == 2
        assert await outbox.process(deliver) == 0
        assert sorted(deliveries) == sorted([activated.id, terminal.id])
        assert len(deliveries) == len(set(deliveries))
        await session.refresh(unrelated)
        assert unrelated.status == EventStatus.PENDING_CONFIGURATION
        assert await session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "integration.retry",
                AuditLog.resource_id == terminal.id,
                AuditLog.actor_id == actor_id,
            )
        ) == 1


@pytest.mark.asyncio
async def test_reopt_in_is_limited_to_matching_channel_and_purpose() -> None:
    async with SessionLocal() as session:
        email = f"release-safety-{uuid.uuid4().hex}@example.com"
        email_hash = digest(email)
        email_marketing = Suppression(
            destination_hash=email_hash,
            channel="EMAIL",
            purpose="MARKETING_EMAIL",
            reason="PREFERENCE_WITHDRAWN",
            source="PREFERENCE_CENTER",
            active=True,
        )
        email_transactional = Suppression(
            destination_hash=email_hash,
            channel="EMAIL",
            purpose="TRANSACTIONAL_EMAIL",
            reason="PREFERENCE_WITHDRAWN",
            source="PREFERENCE_CENTER",
            active=True,
        )
        unrelated_sms = Suppression(
            destination_hash=email_hash,
            channel="SMS",
            purpose="MARKETING_SMS",
            reason="RECIPIENT_REVOCATION",
            source="SMS_INBOUND",
            active=True,
        )
        session.add_all([email_marketing, email_transactional, unrelated_sms])
        await session.commit()

        await ComplianceService(session).preferences(
            CommunicationPreferenceCreate(
                destination=email,
                transactionalEmail=True,
                marketingEmail=True,
                source_url="https://breero.com/communications-preferences",
                disclosure_text="I explicitly opt in to these email purposes.",
                policy_versions={"privacy": "2026.08.23"},
            ),
            "192.0.2.5",
            "release-safety-test",
        )
        await session.refresh(email_marketing)
        await session.refresh(email_transactional)
        await session.refresh(unrelated_sms)
        assert email_marketing.active is False
        assert email_transactional.active is False
        assert unrelated_sms.active is True
        assert await session.scalar(
            select(func.count(ConsentEvent.id)).where(
                ConsentEvent.destination_hash == email_hash,
                ConsentEvent.granted.is_(True),
            )
        ) == 2

        phone = f"+1281{uuid.uuid4().int % 10_000_000:07d}"
        phone_hash = digest(phone)
        sms_marketing = Suppression(
            destination_hash=phone_hash,
            channel="SMS",
            purpose="MARKETING_SMS",
            reason="PREFERENCE_WITHDRAWN",
            source="PREFERENCE_CENTER",
            active=True,
        )
        unrelated_email = Suppression(
            destination_hash=phone_hash,
            channel="EMAIL",
            purpose="MARKETING_EMAIL",
            reason="PREFERENCE_WITHDRAWN",
            source="PREFERENCE_CENTER",
            active=True,
        )
        session.add_all([sms_marketing, unrelated_email])
        await session.commit()
        await ComplianceService(session).preferences(
            CommunicationPreferenceCreate(
                destination=phone,
                marketingSms=True,
                source_url="https://breero.com/communications-preferences",
                disclosure_text="I explicitly opt in to this SMS purpose.",
                policy_versions={"privacy": "2026.08.23"},
            ),
            "192.0.2.6",
            "release-safety-test",
        )
        await session.refresh(sms_marketing)
        await session.refresh(unrelated_email)
        assert sms_marketing.active is False
        assert unrelated_email.active is True


@pytest.mark.asyncio
async def test_parking_and_activation_synchronize_public_submission_status() -> None:
    marker = uuid.uuid4().hex
    event_type = f"breero.release_safety_status.{marker}"

    async with SessionLocal() as session:
        submission = PublicSubmission(
            submission_type=SubmissionType.SERVICE_REQUEST,
            idempotency_key=f"release-safety-status-{marker}",
            request_hash=marker.ljust(64, "0"),
            normalized_email=f"release-safety-status-{marker}@example.com",
            normalized_phone=None,
            payload={"release_safety_test": True},
            downstream_status=DownstreamStatus.PENDING,
            source_ip_hash=marker.ljust(64, "1"),
        )
        session.add(submission)
        await session.flush()

        event = IntegrationEvent(
            aggregate_type="public_submission",
            aggregate_id=submission.id,
            event_type=event_type,
            idempotency_key=f"release-safety-status-event-{marker}",
            payload={"submission_id": str(submission.id)},
            status=EventStatus.PENDING,
            next_attempt_at=datetime.now(UTC),
        )
        session.add(event)
        await session.commit()

        outbox = OutboxService(session)
        assert await outbox.park_unconfigured(event_prefix=event_type) == 1
        await session.refresh(submission)
        await session.refresh(event)
        assert event.status == EventStatus.PENDING_CONFIGURATION
        assert submission.downstream_status == DownstreamStatus.PENDING_CONFIGURATION

        assert await outbox.activate_pending_configuration(event_prefix=event_type) == 1
        await session.refresh(submission)
        await session.refresh(event)
        assert event.status == EventStatus.PENDING
        assert submission.downstream_status == DownstreamStatus.PENDING
