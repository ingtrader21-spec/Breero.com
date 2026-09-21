import posixpath
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.auth.access_service import AccessService
from app.domains.auth.models import AccessRole, TenantScope, User
from app.domains.common.outbox import EventStatus, IntegrationEvent
from app.domains.tenant_email.models import EmailCredential, EmailDomain, EmailMessage, EmailSender
from app.domains.tenant_email.schemas import (
    EmailComposeRequest,
    EmailCredentialCreate,
    EmailCredentialRead,
    EmailDomainCreate,
    EmailMessageRead,
    EmailSenderCreate,
)

INTERNAL_BROAD_ROLES = {
    AccessRole.operations,
    AccessRole.ops_manager,
    AccessRole.support,
    AccessRole.finance,
    AccessRole.quality,
    AccessRole.trust_safety,
    AccessRole.sales,
    AccessRole.marketing,
    AccessRole.admin,
    AccessRole.superadmin,
}


class TenantEmailService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def assert_scope(self, user: User, brand_key: str, vendor_id: uuid.UUID | None) -> None:
        context = await AccessService(self.session).context(user, brand_key)
        if "*" in context.permissions:
            return
        for assignment in context.assignments:
            if assignment.role in INTERNAL_BROAD_ROLES and assignment.tenant_scope in {
                TenantScope.global_,
                TenantScope.brand,
            }:
                return
            if (
                vendor_id is not None
                and assignment.tenant_scope == TenantScope.vendor
                and assignment.vendor_id == vendor_id
            ):
                return
        raise HTTPException(403, "Tenant scope is not authorized")

    async def scoped_vendor_ids(self, user: User, brand_key: str) -> set[uuid.UUID] | None:
        """The vendor scope a listing query should filter to.

        Returns None when the caller can see every tenant (wildcard permission, or a
        global/brand-scoped assignment in one of the internal broad roles); otherwise
        the set of vendor ids their assignments actually grant -- possibly empty.
        """
        context = await AccessService(self.session).context(user, brand_key)
        if "*" in context.permissions:
            return None
        vendor_ids: set[uuid.UUID] = set()
        for assignment in context.assignments:
            if assignment.role in INTERNAL_BROAD_ROLES and assignment.tenant_scope in {
                TenantScope.global_,
                TenantScope.brand,
            }:
                return None
            if assignment.tenant_scope == TenantScope.vendor and assignment.vendor_id is not None:
                vendor_ids.add(assignment.vendor_id)
        return vendor_ids

    @staticmethod
    def expected_secret_prefix(brand_key: str, vendor_id: uuid.UUID | None) -> str:
        if vendor_id is not None:
            return f"breero-email/vendor/{vendor_id}/"
        return f"breero-email/brand/{brand_key}/"

    @staticmethod
    def validate_secret_ref(secret_ref: str, expected_prefix: str) -> str:
        """Normalize and validate a credential secret reference against its tenant
        namespace, returning the value to persist.

        A plain ``str.startswith(expected_prefix)`` check accepts a reference like
        ``"<expected_prefix>../../../database-secret"``: it starts with the right
        namespace, and ``FileSecretResolver`` later accepts it because the resolved
        path still lands under the shared secret root -- just under someone else's
        file. Reject any ".." segment outright, then re-check the prefix against the
        normalized reference.
        """
        if any(segment == ".." for segment in secret_ref.split("/")):
            raise HTTPException(400, "Credential secret reference may not contain '..' segments")
        normalized = posixpath.normpath(secret_ref)
        if not normalized.startswith(expected_prefix):
            raise HTTPException(400, f"Credential secret reference must start with {expected_prefix}")
        return normalized

    @staticmethod
    def _credential_read(record: EmailCredential) -> EmailCredentialRead:
        return EmailCredentialRead(
            id=record.id,
            brand_key=record.brand_key,
            vendor_id=record.vendor_id,
            provider=record.provider,
            label=record.label,
            username=record.username,
            smtp_host=record.smtp_host,
            smtp_port=record.smtp_port,
            use_tls=record.use_tls,
            active=record.active,
            secret_configured=bool(record.secret_ref),
            created_at=record.created_at,
        )

    async def create_domain(self, data: EmailDomainCreate, user: User) -> EmailDomain:
        await self.assert_scope(user, data.brand_key, data.vendor_id)
        record = EmailDomain(
            brand_key=data.brand_key,
            vendor_id=data.vendor_id,
            domain=data.domain,
            dkim_selector=data.dkim_selector,
            return_path_domain=data.return_path_domain,
            verification_status="PENDING",
            active=True,
            created_by=user.id,
        )
        self.session.add(record)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Email domain already exists") from exc
        await self.session.refresh(record)
        return record

    async def list_domains(self, user: User) -> list[EmailDomain]:
        rows = list((await self.session.scalars(select(EmailDomain).order_by(EmailDomain.domain))).all())
        allowed: list[EmailDomain] = []
        for row in rows:
            try:
                await self.assert_scope(user, row.brand_key, row.vendor_id)
                allowed.append(row)
            except HTTPException:
                continue
        return allowed

    async def set_domain_verification(self, domain_id: uuid.UUID, verified: bool, user: User) -> EmailDomain:
        record = await self.session.get(EmailDomain, domain_id)
        if not record:
            raise HTTPException(404, "Email domain not found")
        await self.assert_scope(user, record.brand_key, record.vendor_id)
        record.verification_status = "VERIFIED" if verified else "PENDING"
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def create_sender(self, data: EmailSenderCreate, user: User) -> EmailSender:
        await self.assert_scope(user, data.brand_key, data.vendor_id)
        domain = await self.session.get(EmailDomain, data.domain_id)
        if not domain:
            raise HTTPException(404, "Email domain not found")
        if domain.brand_key != data.brand_key or domain.vendor_id != data.vendor_id:
            raise HTTPException(409, "Sender scope must match domain scope")
        record = EmailSender(
            brand_key=data.brand_key,
            vendor_id=data.vendor_id,
            domain_id=data.domain_id,
            local_part=data.local_part.lower(),
            display_name=data.display_name.strip(),
            reply_to=str(data.reply_to) if data.reply_to else None,
            active=True,
            created_by=user.id,
        )
        self.session.add(record)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Sender already exists") from exc
        await self.session.refresh(record)
        return record

    async def list_senders(self, user: User) -> list[EmailSender]:
        rows = list((await self.session.scalars(select(EmailSender).order_by(EmailSender.created_at))).all())
        allowed: list[EmailSender] = []
        for row in rows:
            try:
                await self.assert_scope(user, row.brand_key, row.vendor_id)
                allowed.append(row)
            except HTTPException:
                continue
        return allowed

    async def create_credential(self, data: EmailCredentialCreate, user: User) -> EmailCredentialRead:
        await self.assert_scope(user, data.brand_key, data.vendor_id)
        expected_prefix = self.expected_secret_prefix(data.brand_key, data.vendor_id)
        normalized = self.validate_secret_ref(data.secret_ref, expected_prefix)
        record = EmailCredential(
            brand_key=data.brand_key,
            vendor_id=data.vendor_id,
            provider=data.provider,
            label=data.label.strip(),
            username=data.username,
            secret_ref=normalized,
            smtp_host=data.smtp_host,
            smtp_port=data.smtp_port,
            use_tls=data.use_tls,
            active=True,
            created_by=user.id,
        )
        self.session.add(record)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Credential secret reference already exists") from exc
        await self.session.refresh(record)
        return self._credential_read(record)

    async def list_credentials(self, user: User) -> list[EmailCredentialRead]:
        rows = list(
            (await self.session.scalars(select(EmailCredential).order_by(EmailCredential.created_at))).all()
        )
        allowed: list[EmailCredentialRead] = []
        for row in rows:
            try:
                await self.assert_scope(user, row.brand_key, row.vendor_id)
                allowed.append(self._credential_read(row))
            except HTTPException:
                continue
        return allowed

    async def compose(self, data: EmailComposeRequest, user: User) -> EmailMessageRead:
        await self.assert_scope(user, data.brand_key, data.vendor_id)
        existing = await self.session.scalar(
            select(EmailMessage).where(EmailMessage.idempotency_key == data.idempotency_key)
        )
        if existing:
            if existing.brand_key != data.brand_key or existing.vendor_id != data.vendor_id:
                raise HTTPException(409, "Idempotency key belongs to another tenant scope")
            return EmailMessageRead.model_validate(existing)

        sender = await self.session.get(EmailSender, data.sender_id)
        credential = await self.session.get(EmailCredential, data.credential_id)
        if not sender or not credential:
            raise HTTPException(404, "Sender or credential not found")
        if not sender.active or not credential.active:
            raise HTTPException(409, "Sender or credential is inactive")
        if (
            sender.brand_key != data.brand_key
            or credential.brand_key != data.brand_key
            or sender.vendor_id != data.vendor_id
            or credential.vendor_id != data.vendor_id
        ):
            raise HTTPException(403, "Cross-tenant email resources are not allowed")
        domain = await self.session.get(EmailDomain, sender.domain_id)
        if not domain or domain.verification_status != "VERIFIED" or not domain.active:
            raise HTTPException(409, "Sender domain is not verified")

        now = datetime.now(UTC)
        message = EmailMessage(
            brand_key=data.brand_key,
            vendor_id=data.vendor_id,
            sender_id=sender.id,
            credential_id=credential.id,
            to_email=str(data.to_email).lower(),
            subject=data.subject.strip(),
            text_body=data.text_body,
            status="QUEUED",
            idempotency_key=data.idempotency_key,
            created_by=user.id,
            queued_at=now,
        )
        self.session.add(message)
        await self.session.flush()
        delivery_ready = settings.email_enabled and settings.transactional_email_mode != "disabled"
        self.session.add(
            IntegrationEvent(
                aggregate_type="email_message",
                aggregate_id=message.id,
                event_type="email.message.queued",
                aggregate_version=1,
                schema_version=1,
                idempotency_key=f"email:{data.idempotency_key}",
                payload={
                    "message_id": str(message.id),
                    "brand_key": data.brand_key,
                    "vendor_id": str(data.vendor_id) if data.vendor_id else None,
                },
                status=EventStatus.PENDING if delivery_ready else EventStatus.PENDING_CONFIGURATION,
                attempt_count=0,
                next_attempt_at=now,
            )
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(EmailMessage).where(EmailMessage.idempotency_key == data.idempotency_key)
            )
            if existing:
                # The idempotency key is only unique globally, not per tenant, so the
                # loser of a concurrent compose race must not be handed back a record
                # it lost the race to see -- re-run the same scope comparison the
                # pre-check above performs before treating this as "your own replay".
                if existing.brand_key != data.brand_key or existing.vendor_id != data.vendor_id:
                    raise HTTPException(409, "Idempotency key belongs to another tenant scope") from exc
                return EmailMessageRead.model_validate(existing)
            raise HTTPException(409, "Email message could not be queued") from exc
        await self.session.refresh(message)
        return EmailMessageRead.model_validate(message)

    async def get_message(self, message_id: uuid.UUID, user: User) -> EmailMessage:
        message = await self.session.get(EmailMessage, message_id)
        if not message:
            raise HTTPException(404, "Email message not found")
        await self.assert_scope(user, message.brand_key, message.vendor_id)
        return message
