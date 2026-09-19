import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, update

from app.config import settings
from app.db.session import SessionLocal
from app.domains.auth.access_service import AccessService
from app.domains.auth.models import AccessAssignment, User, UserRole
from app.domains.auth.schemas import LoginRequest
from app.domains.auth.security import hash_password
from app.domains.auth.service import AuthService
from app.domains.common.outbox import EventStatus, IntegrationEvent
from app.domains.common.outbox_service import OutboxService
from app.domains.tenant_email.delivery import FakeTenantEmailGateway, TenantEmailDeliveryService
from app.domains.tenant_email.models import EmailMessage
from app.domains.tenant_email.schemas import (
    EmailComposeRequest,
    EmailCredentialCreate,
    EmailDomainCreate,
    EmailSenderCreate,
)
from app.domains.tenant_email.service import TenantEmailService
from app.domains.workforce.models import Vendor, VendorStatus


class FakeSecretResolver:
    def resolve(self, reference: str) -> str:
        assert reference.startswith("breero-email/")
        return "test-only-secret-never-persisted"


@pytest.mark.asyncio
async def test_login_dashboard_domain_sender_compose_outbox_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = uuid.uuid4().hex
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "transactional_email_mode", "controlled_canary")

    async with SessionLocal() as session:
        await session.execute(delete(IntegrationEvent))
        await session.commit()

        account = User(
            email=f"email-admin-{marker}@example.com",
            full_name="Tenant Email Admin",
            password_hash=await hash_password("Tenant-email-test-123!"),
            role=UserRole.admin,
            is_active=True,
            email_verified=True,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)

        login = await AuthService(session).login(
            LoginRequest(email=account.email, password="Tenant-email-test-123!")
        )
        assert login.access_token
        assert login.user.id == account.id

        context = await AccessService(session).context(account)
        assert context.dashboard_path == "/admin"
        assert "email.domain.manage" in context.permissions
        assert "email.credential.manage" in context.permissions
        assert "email.message.compose" in context.permissions

        email_service = TenantEmailService(session)
        domain = await email_service.create_domain(
            EmailDomainCreate(domain=f"mail-{marker}.example.test"), account
        )
        domain = await email_service.set_domain_verification(domain.id, True, account)
        assert domain.verification_status == "VERIFIED"

        sender = await email_service.create_sender(
            EmailSenderCreate(
                domain_id=domain.id,
                local_part="operations",
                display_name="BREERO Operations",
            ),
            account,
        )
        credential = await email_service.create_credential(
            EmailCredentialCreate(
                provider="smtp",
                label="Tenant SMTP",
                username=f"smtp-{marker}",
                secret_ref=f"breero-email/brand/breero/test/{marker}",
                smtp_host="smtp.example.test",
                smtp_port=587,
                use_tls=True,
            ),
            account,
        )
        credential_payload = credential.model_dump()
        assert "secret_ref" not in credential_payload
        assert "password" not in credential_payload
        assert credential.secret_configured is True

        message = await email_service.compose(
            EmailComposeRequest(
                sender_id=sender.id,
                credential_id=credential.id,
                to_email=f"recipient-{marker}@example.com",
                subject="Service request update",
                text_body="Your BREERO service request has been updated.",
                idempotency_key=f"tenant-email-e2e-{marker}",
            ),
            account,
        )
        assert message.status == "QUEUED"

        event = await session.scalar(
            select(IntegrationEvent).where(
                IntegrationEvent.aggregate_type == "email_message",
                IntegrationEvent.aggregate_id == message.id,
                IntegrationEvent.event_type == "email.message.queued",
            )
        )
        assert event is not None
        assert event.status == EventStatus.PENDING
        assert "secret" not in str(event.payload).lower()
        assert "smtp" not in str(event.payload).lower()

        gateway = FakeTenantEmailGateway(sent=[])
        delivery = TenantEmailDeliveryService(
            session,
            gateway=gateway,
            secret_resolver=FakeSecretResolver(),
        )
        outbox = OutboxService(session)
        processed = await outbox.process(delivery.deliver)
        assert processed == 1

        await session.refresh(event)
        stored_message = await session.get(EmailMessage, message.id)
        assert stored_message is not None
        assert event.status == EventStatus.DELIVERED
        assert stored_message.status == "DELIVERED"
        assert stored_message.provider_message_id == "fake-tenant-email-1"
        assert gateway.sent == [
            {
                "provider": "smtp",
                "from": f"operations@{domain.domain}",
                "to": f"recipient-{marker}@example.com",
                "subject": "Service request update",
                "text": "Your BREERO service request has been updated.",
                "secret": "[REDACTED]",
            }
        ]


@pytest.mark.asyncio
async def test_vendor_scope_cannot_cross_tenant_email_resources_or_secret_namespace() -> None:
    marker = uuid.uuid4().hex
    async with SessionLocal() as session:
        vendor_one = Vendor(
            legal_name=f"Tenant One {marker}", display_name="Tenant One",
            email=f"tenant-one-{marker}@example.com", phone="+12815550110",
            status=VendorStatus.ACTIVE, capabilities=["email"],
        )
        vendor_two = Vendor(
            legal_name=f"Tenant Two {marker}", display_name="Tenant Two",
            email=f"tenant-two-{marker}@example.com", phone="+12815550111",
            status=VendorStatus.ACTIVE, capabilities=["email"],
        )
        session.add_all([vendor_one, vendor_two])
        await session.flush()

        provider = User(
            email=f"provider-{marker}@example.com",
            full_name="Scoped Provider",
            password_hash=await hash_password("Tenant-email-test-123!"),
            role=UserRole.vendor_admin,
            is_active=True,
            email_verified=True,
        )
        session.add(provider)
        await session.flush()
        session.add(
            AccessAssignment(
                user_id=provider.id, brand_key="breero", role_key="vendor_admin",
                department="provider", tenant_scope="vendor", vendor_id=vendor_one.id,
                active=True, is_primary=True,
            )
        )
        await session.commit()

        service = TenantEmailService(session)
        allowed = await service.create_domain(
            EmailDomainCreate(domain=f"allowed-{marker}.example.test", vendor_id=vendor_one.id),
            provider,
        )
        assert allowed.vendor_id == vendor_one.id

        with pytest.raises(HTTPException) as exc_info:
            await service.create_domain(
                EmailDomainCreate(domain=f"blocked-{marker}.example.test", vendor_id=vendor_two.id),
                provider,
            )
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as secret_error:
            await service.create_credential(
                EmailCredentialCreate(
                    vendor_id=vendor_one.id,
                    provider="smtp",
                    label="Wrong tenant secret",
                    secret_ref=f"breero-email/vendor/{vendor_two.id}/smtp/main",
                    smtp_host="smtp.example.test",
                    smtp_port=587,
                ),
                provider,
            )
        assert secret_error.value.status_code == 400


@pytest.mark.asyncio
async def test_outbox_listing_filters_tenant_scope_before_the_page_limit() -> None:
    # Regression test: /email/outbox used to select the newest 200 events globally
    # and only remove other tenants' rows afterward. A vendor-scoped caller whose own
    # events were older than 200 more-recent events from other tenants would see an
    # incomplete or empty outbox even though their own events still exist. The scope
    # must be applied in the SQL query, before LIMIT.
    from app.api.v1 import email as email_router

    marker = uuid.uuid4().hex
    async with SessionLocal() as session:
        quiet_vendor = Vendor(
            legal_name=f"Quiet Tenant {marker}", display_name="Quiet Tenant",
            email=f"quiet-{marker}@example.com", phone="+12815550120",
            status=VendorStatus.ACTIVE, capabilities=["email"],
        )
        noisy_vendor = Vendor(
            legal_name=f"Noisy Tenant {marker}", display_name="Noisy Tenant",
            email=f"noisy-{marker}@example.com", phone="+12815550121",
            status=VendorStatus.ACTIVE, capabilities=["email"],
        )
        session.add_all([quiet_vendor, noisy_vendor])
        await session.flush()

        owner = User(
            email=f"quiet-owner-{marker}@example.com",
            full_name="Quiet Tenant Owner",
            password_hash=await hash_password("Tenant-email-test-123!"),
            role=UserRole.vendor_admin,
            is_active=True,
            email_verified=True,
        )
        noisy_owner = User(
            email=f"noisy-owner-{marker}@example.com",
            full_name="Noisy Tenant Owner",
            password_hash=await hash_password("Tenant-email-test-123!"),
            role=UserRole.vendor_admin,
            is_active=True,
            email_verified=True,
        )
        session.add_all([owner, noisy_owner])
        await session.flush()
        session.add_all(
            [
                AccessAssignment(
                    user_id=owner.id, brand_key="breero", role_key="vendor_admin",
                    department="provider", tenant_scope="vendor", vendor_id=quiet_vendor.id,
                    active=True, is_primary=True,
                ),
                AccessAssignment(
                    user_id=noisy_owner.id, brand_key="breero", role_key="vendor_admin",
                    department="provider", tenant_scope="vendor", vendor_id=noisy_vendor.id,
                    active=True, is_primary=True,
                ),
            ]
        )
        await session.commit()

        service = TenantEmailService(session)

        async def provision(vendor: Vendor, actor: User) -> tuple:
            domain = await service.create_domain(
                EmailDomainCreate(domain=f"outbox-{vendor.id}.example.test", vendor_id=vendor.id), actor
            )
            domain = await service.set_domain_verification(domain.id, True, actor)
            sender = await service.create_sender(
                EmailSenderCreate(
                    vendor_id=vendor.id, domain_id=domain.id, local_part="notify", display_name="Notify"
                ),
                actor,
            )
            credential = await service.create_credential(
                EmailCredentialCreate(
                    vendor_id=vendor.id,
                    provider="smtp",
                    label="Outbox test",
                    secret_ref=f"breero-email/vendor/{vendor.id}/smtp/main",
                    smtp_host="smtp.example.test",
                    smtp_port=587,
                ),
                actor,
            )
            return sender, credential

        quiet_sender, quiet_credential = await provision(quiet_vendor, owner)
        noisy_sender, noisy_credential = await provision(noisy_vendor, noisy_owner)

        base_time = datetime.now(UTC)
        quiet_message = await service.compose(
            EmailComposeRequest(
                vendor_id=quiet_vendor.id,
                sender_id=quiet_sender.id,
                credential_id=quiet_credential.id,
                to_email=f"recipient-{marker}@example.com",
                subject="Quiet tenant's only message",
                text_body="This is the only message the quiet tenant ever sends.",
                idempotency_key=f"outbox-quiet-{marker}",
            ),
            owner,
        )
        # Backdate it well before the flood of noisy-tenant events below.
        await session.execute(
            update(IntegrationEvent)
            .where(IntegrationEvent.aggregate_id == quiet_message.id)
            .values(created_at=base_time - timedelta(days=1))
        )
        await session.commit()

        # Flood in more than the page size (200) of newer events belonging to a
        # different tenant, all referencing a single real sender/credential to
        # satisfy the foreign keys cheaply.
        noisy_messages = [
            EmailMessage(
                brand_key="breero",
                vendor_id=noisy_vendor.id,
                sender_id=noisy_sender.id,
                credential_id=noisy_credential.id,
                to_email=f"flood-{marker}-{i}@example.com",
                subject="Noise",
                text_body="Noise",
                status="QUEUED",
                idempotency_key=f"outbox-noisy-{marker}-{i}",
                created_by=noisy_owner.id,
            )
            for i in range(210)
        ]
        session.add_all(noisy_messages)
        await session.flush()
        session.add_all(
            [
                IntegrationEvent(
                    aggregate_type="email_message",
                    aggregate_id=message.id,
                    event_type="email.message.queued",
                    idempotency_key=f"outbox-noisy-event-{marker}-{i}",
                    payload={},
                    status=EventStatus.PENDING,
                    next_attempt_at=base_time,
                    created_at=base_time + timedelta(seconds=i),
                )
                for i, message in enumerate(noisy_messages)
            ]
        )
        await session.commit()

        result = await email_router.list_outbox(session=session, user=owner)
        assert quiet_message.id in {row.message_id for row in result}
