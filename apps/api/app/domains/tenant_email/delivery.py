import asyncio
import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage as MimeMessage
from pathlib import Path
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.common.outbox import IntegrationEvent
from app.domains.tenant_email.models import EmailCredential, EmailDomain, EmailMessage, EmailSender

SECRET_ROOT = Path("/run/secrets")


class EmailDeliveryError(RuntimeError):
    code = "EMAIL_DELIVERY_ERROR"
    terminal = False


class EmailDeliveryConfigurationError(EmailDeliveryError):
    code = "EMAIL_CONFIGURATION_ERROR"
    terminal = True


class SecretResolver(Protocol):
    def resolve(self, reference: str) -> str: ...


class FileSecretResolver:
    def resolve(self, reference: str) -> str:
        if not reference.startswith("breero-email/"):
            raise EmailDeliveryConfigurationError("Unsupported email secret reference")
        path = (SECRET_ROOT / reference).resolve()
        root = SECRET_ROOT.resolve()
        if root not in path.parents:
            raise EmailDeliveryConfigurationError("Email secret reference escapes secret root")
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise EmailDeliveryConfigurationError("Email secret is not available") from exc
        if not value:
            raise EmailDeliveryConfigurationError("Email secret is empty")
        return value


class TenantEmailGateway(Protocol):
    async def send(
        self,
        *,
        credential: EmailCredential,
        secret: str,
        from_email: str,
        display_name: str,
        reply_to: str | None,
        to_email: str,
        subject: str,
        text_body: str,
    ) -> str: ...


class SmtpTenantEmailGateway:
    async def send(
        self,
        *,
        credential: EmailCredential,
        secret: str,
        from_email: str,
        display_name: str,
        reply_to: str | None,
        to_email: str,
        subject: str,
        text_body: str,
    ) -> str:
        smtp_host = credential.smtp_host
        smtp_port = credential.smtp_port
        if credential.provider != "smtp" or smtp_host is None or smtp_port is None:
            raise EmailDeliveryConfigurationError("SMTP credential is incomplete")
        mime = MimeMessage()
        mime["From"] = f"{display_name} <{from_email}>"
        mime["To"] = to_email
        mime["Subject"] = subject
        if reply_to:
            mime["Reply-To"] = reply_to
        mime.set_content(text_body)

        def deliver() -> None:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as client:
                if credential.use_tls:
                    client.starttls()
                if credential.username:
                    client.login(credential.username, secret)
                client.send_message(mime)

        await asyncio.to_thread(deliver)
        return mime["Message-ID"] or "smtp-accepted"


@dataclass
class FakeTenantEmailGateway:
    sent: list[dict[str, str]]

    async def send(
        self,
        *,
        credential: EmailCredential,
        secret: str,
        from_email: str,
        display_name: str,
        reply_to: str | None,
        to_email: str,
        subject: str,
        text_body: str,
    ) -> str:
        self.sent.append(
            {
                "provider": credential.provider,
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "text": text_body,
                "secret": "[REDACTED]" if secret else "",
            }
        )
        return f"fake-tenant-email-{len(self.sent)}"


class TenantEmailDeliveryService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        gateway: TenantEmailGateway | None = None,
        secret_resolver: SecretResolver | None = None,
    ) -> None:
        self.session = session
        self.gateway = gateway or SmtpTenantEmailGateway()
        self.secret_resolver = secret_resolver or FileSecretResolver()

    async def deliver(self, event: IntegrationEvent) -> object:
        if event.aggregate_type != "email_message" or event.event_type != "email.message.queued":
            raise EmailDeliveryConfigurationError("Unsupported email outbox event")
        message = await self.session.get(EmailMessage, event.aggregate_id)
        if not message:
            raise EmailDeliveryConfigurationError("Email message does not exist")
        sender = await self.session.get(EmailSender, message.sender_id)
        credential = await self.session.get(EmailCredential, message.credential_id)
        if not sender or not credential:
            raise EmailDeliveryConfigurationError("Email sender or credential does not exist")
        domain = await self.session.get(EmailDomain, sender.domain_id)
        if not domain or domain.verification_status != "VERIFIED":
            raise EmailDeliveryConfigurationError("Email domain is not verified")
        if not sender.active or not credential.active or not domain.active:
            raise EmailDeliveryConfigurationError("Email delivery resource is inactive")
        if (
            sender.brand_key != message.brand_key
            or credential.brand_key != message.brand_key
            or domain.brand_key != message.brand_key
            or sender.vendor_id != message.vendor_id
            or credential.vendor_id != message.vendor_id
            or domain.vendor_id != message.vendor_id
        ):
            raise EmailDeliveryConfigurationError("Cross-tenant email delivery is blocked")
        secret = self.secret_resolver.resolve(credential.secret_ref)
        provider_message_id = await self.gateway.send(
            credential=credential,
            secret=secret,
            from_email=f"{sender.local_part}@{domain.domain}",
            display_name=sender.display_name,
            reply_to=sender.reply_to,
            to_email=message.to_email,
            subject=message.subject,
            text_body=message.text_body,
        )
        message.status = "DELIVERED"
        message.provider_message_id = provider_message_id
        message.delivered_at = datetime.now(UTC)
        await self.session.flush()

        @dataclass(frozen=True)
        class DeliveryResult:
            model: str = "email_message"
            external_id: str = provider_message_id

        return DeliveryResult()
