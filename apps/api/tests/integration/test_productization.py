import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.config import settings
from app.core.errors import DomainError
from app.db.session import SessionLocal
from app.domains.catalog.models import Service
from app.domains.common.outbox import EventStatus, IntegrationEvent
from app.domains.payments.models import Payment, PaymentPurpose, PaymentStatus
from app.domains.payments.schemas import ProviderIntent, ProviderRefund
from app.domains.payments.service import PaymentService
from app.domains.professional_leads.models import (
    DisputeStatus,
    LeadPurchase,
    LeadPurchaseStatus,
    LeadStatus,
    ProfessionalLead,
)
from app.domains.professional_leads.service import ProfessionalLeadService
from app.domains.public_submissions.consent import DEFAULT_CONSENT_POLICY_VERSION
from app.domains.public_submissions.models import DownstreamStatus, PublicSubmission, SubmissionType
from app.domains.public_submissions.schemas import (
    ContactCreate,
    ProviderInterestCreate,
    ServiceRequestCreate,
)
from app.domains.public_submissions.service import PublicSubmissionService
from app.domains.workforce.models import Vendor, VendorStatus


class FakeLeadStripeProvider:
    async def create_intent(self, **_: Any) -> ProviderIntent:
        return ProviderIntent(
            id=f"pi_lead_{uuid.uuid4().hex}",
            status="requires_action",
            client_secret="pi_lead_secret_test",
        )

    async def capture_intent(self, provider_payment_id: str, **_: Any) -> ProviderIntent:
        return ProviderIntent(id=provider_payment_id, status="succeeded")

    def verify_webhook(self, body: bytes, signature: str) -> dict[str, Any]:
        assert signature == "fake-lead-signature"
        return json.loads(body)

    async def create_refund(self, provider_payment_id: str, **_: Any) -> ProviderRefund:
        return ProviderRefund(id=f"re_{provider_payment_id}", status="succeeded")


@pytest.mark.asyncio
async def test_public_forms_are_atomic_idempotent_and_pending_configuration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "middleware_enabled", False)
    marker = uuid.uuid4().hex
    async with SessionLocal() as session:
        service = Service(
            slug=f"test-form-{marker}",
            name="Test service",
            description="Test-only service",
            category="home-services",
            pricing_model="quote_required",
            is_active=True,
            is_bookable=False,
            sort_order=999,
        )
        session.add(service)
        await session.commit()

        submissions = PublicSubmissionService(session)
        service_data = ServiceRequestCreate(
            name="Test Customer",
            email=f"customer-{marker}@example.com",
            phone="+1 281 555 0100",
            service_slug=service.slug,
            service_description="A test-only repair request",
            address_line1="20633 Longenbaugh Rd",
            city="Cypress",
            state="TX",
            postal_code="77433",
            contact_preference="email",
            source_url="https://staging.breero.com/book",
            transactional_contact_allowed=True,
            policy_version=DEFAULT_CONSENT_POLICY_VERSION,
        )
        accepted = await submissions.accept(
            SubmissionType.SERVICE_REQUEST, service_data, f"service-{marker}", "192.0.2.10"
        )
        replay = await submissions.accept(
            SubmissionType.SERVICE_REQUEST, service_data, f"service-{marker}", "192.0.2.10"
        )
        assert replay.request_id == accepted.request_id
        assert accepted.downstream_status == DownstreamStatus.PENDING_CONFIGURATION.value

        row = await session.get(PublicSubmission, accepted.request_id)
        event = await session.scalar(
            select(IntegrationEvent).where(IntegrationEvent.aggregate_id == accepted.request_id)
        )
        assert row and event
        assert event.status == EventStatus.PENDING_CONFIGURATION
        assert event.processed_at is None
        assert row.payload["transactional_contact_allowed"] is True
        assert row.payload["consent_recorded_by"] == "breero_api"
        assert row.payload["consent_timestamp"]
        assert row.payload["consent_source"] == "breero_public_api"
        assert row.payload["policy_version"] == DEFAULT_CONSENT_POLICY_VERSION
        assert row.payload["consent_disclosures"]["transactional_contact"].startswith(
            "I agree that BREERO may contact me"
        )
        assert row.payload["provider_assigned"] is False
        assert row.payload["appointment_confirmed"] is False
        assert row.payload["payment_required"] is False

        changed = service_data.model_copy(update={"service_description": "A changed request body"})
        with pytest.raises(DomainError, match="Key already used"):
            await submissions.accept(
                SubmissionType.SERVICE_REQUEST, changed, f"service-{marker}", "192.0.2.10"
            )

        without_contact_permission = service_data.model_copy(
            update={"transactional_contact_allowed": False}
        )
        with pytest.raises(DomainError, match="Permission to contact"):
            await submissions.accept(
                SubmissionType.SERVICE_REQUEST,
                without_contact_permission,
                f"service-no-consent-{marker}",
                "192.0.2.10",
            )

        contact = ContactCreate(
            name="Test Customer",
            email=f"contact-{marker}@example.com",
            category="booking_help",
            subject="Test booking question",
            message="This is a test-only contact request.",
            source_url="https://staging.breero.com/contact",
            transactional_contact_allowed=True,
            policy_version=DEFAULT_CONSENT_POLICY_VERSION,
        )
        provider = ProviderInterestCreate(
            business_name="Test Provider LLC",
            contact_name="Test Provider",
            email=f"provider-{marker}@example.com",
            phone="+1 281 555 0101",
            service_categories=[service.slug],
            city="Cypress",
            state="TX",
            postal_code="77433",
            source_url="https://staging.breero.com/partners",
            transactional_contact_allowed=True,
            policy_version=DEFAULT_CONSENT_POLICY_VERSION,
        )
        await submissions.accept(SubmissionType.CONTACT, contact, f"contact-{marker}", "192.0.2.11")
        await submissions.accept(
            SubmissionType.PROVIDER_INTEREST,
            provider,
            f"provider-{marker}",
            "192.0.2.12",
        )
        assert (
            await session.scalar(
                select(PublicSubmission).where(
                    PublicSubmission.submission_type == SubmissionType.PROVIDER_INTEREST,
                    PublicSubmission.idempotency_key == f"provider-{marker}",
                )
            )
            is not None
        )


@pytest.mark.asyncio
async def test_leads_enforce_eligibility_purchase_idempotency_and_dispute_window(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "stripe_enabled", True)
    marker = uuid.uuid4().hex
    async with SessionLocal() as session:
        plumbing_vendor = Vendor(
            legal_name="Test Plumbing LLC",
            display_name="Test Plumbing",
            email=f"plumbing-{marker}@example.test",
            phone="+12815550102",
            status=VendorStatus.ACTIVE,
            capabilities=["plumbing"],
        )
        electrical_vendor = Vendor(
            legal_name="Test Electrical LLC",
            display_name="Test Electrical",
            email=f"electrical-{marker}@example.test",
            phone="+12815550103",
            status=VendorStatus.ACTIVE,
            capabilities=["electrical"],
        )
        lead = ProfessionalLead(
            service_category="plumbing",
            location_summary="Cypress, TX 77433",
            qualification_criteria={"state": "TX"},
            price_minor=2500,
            currency="USD",
            policy_version="2026-08-12",
            status=LeadStatus.AVAILABLE,
            expires_at=datetime.now(UTC) + timedelta(days=2),
        )
        session.add_all([plumbing_vendor, electrical_vendor, lead])
        await session.commit()

        leads = ProfessionalLeadService(session, FakeLeadStripeProvider())
        assert lead.id in {item.id for item in await leads.available(plumbing_vendor)}
        assert await leads.available(electrical_vendor) == []
        with pytest.raises(DomainError, match="not found"):
            await leads.get(lead.id, electrical_vendor)

        purchase = await leads.purchase(lead.id, plumbing_vendor.id, f"purchase-{marker}")
        replay = await leads.purchase(lead.id, plumbing_vendor.id, f"purchase-{marker}")
        assert replay["id"] == purchase["id"]
        assert purchase["status"] == LeadPurchaseStatus.PENDING_PAYMENT
        payment = await session.get(Payment, purchase["payment_id"])
        assert payment and payment.payment_purpose == PaymentPurpose.PROFESSIONAL_LEAD
        assert payment.amount_minor == lead.price_minor
        assert payment.currency == lead.currency
        assert lead.status == LeadStatus.RESERVED
        payment_service = PaymentService(session, leads.payment_provider)
        event = json.dumps(
            {
                "id": f"evt_lead_{marker}",
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "object": "payment_intent",
                        "id": payment.provider_payment_id,
                        "status": "succeeded",
                        "amount_received": payment.amount_minor,
                    }
                },
            }
        ).encode()
        await payment_service.process_webhook(event, "fake-lead-signature")
        await session.refresh(purchase_row := await session.get(LeadPurchase, purchase["id"]))
        await session.refresh(lead)
        assert purchase_row.status == LeadPurchaseStatus.PAID
        assert lead.status == LeadStatus.PURCHASED
        await session.refresh(payment)
        assert payment.status == PaymentStatus.CAPTURED

        other_lead = ProfessionalLead(
            service_category="plumbing",
            location_summary="Cypress, TX 77433",
            qualification_criteria={},
            price_minor=2500,
            currency="USD",
            policy_version="2026-08-12",
            status=LeadStatus.AVAILABLE,
        )
        session.add(other_lead)
        await session.commit()
        with pytest.raises(DomainError, match="Key already used"):
            await leads.purchase(other_lead.id, plumbing_vendor.id, f"purchase-{marker}")

        dispute = await leads.dispute(
            lead.id, plumbing_vendor.id, "invalid_contact", "The supplied number is invalid."
        )
        duplicate = await leads.dispute(
            lead.id, plumbing_vendor.id, "invalid_contact", "The supplied number is invalid."
        )
        assert duplicate.id == dispute.id
        assert dispute.status == DisputeStatus.OPEN
        assert dispute.deadline_at == purchase_row.created_at + timedelta(hours=72)

        purchase_row.created_at = datetime.now(UTC) - timedelta(hours=73)
        await session.commit()
        with pytest.raises(DomainError, match="72-hour"):
            await leads.dispute(
                lead.id,
                plumbing_vendor.id,
                "wrong_service_category",
                "The opportunity category is incorrect.",
            )
