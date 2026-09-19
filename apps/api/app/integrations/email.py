import asyncio
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Protocol

import httpx
import structlog

from app.config import settings
from app.integrations.payouts import IntegrationNotConfigured


class EmailDeliveryDisabled(IntegrationNotConfigured):
    code = "EMAIL_DELIVERY_DISABLED"
    pending_configuration = True


def require_live_email_delivery() -> None:
    if not (
        settings.live_email_delivery
        and settings.email_enabled
        and settings.transactional_email_mode == "controlled_canary"
    ):
        raise EmailDeliveryDisabled("Email delivery is disabled or awaiting configuration")


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str


class EmailGateway(Protocol):
    async def send(self, *, to: str, subject: str, text: str) -> str: ...


class FakeEmailGateway:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, text: str) -> str:
        self.sent.append({"to": to, "subject": subject, "text": text})
        return f"fake-email-{len(self.sent)}"


class ConsoleEmailGateway(FakeEmailGateway):
    async def send(self, **message: str) -> str:
        identifier = await super().send(**message)
        structlog.get_logger(__name__).info(
            "local_email_delivery", message_id=identifier, recipient=message["to"]
        )
        return identifier


class SmtpEmailGateway:
    async def send(self, *, to: str, subject: str, text: str) -> str:
        require_live_email_delivery()
        if not settings.smtp_host or not settings.smtp_from_email:
            raise EmailDeliveryDisabled("Email provider is not configured")
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = settings.smtp_from_email, to, subject
        message.set_content(text)

        def deliver() -> None:
            require_live_email_delivery()
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as client:
                client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)

        await asyncio.to_thread(deliver)
        return message["Message-ID"] or "smtp-accepted"


class EmailAdapter:
    """Compatibility event adapter for auth events and configurable HTTP delivery."""

    def __init__(self) -> None:
        self.delivery_url = os.getenv("EMAIL_DELIVERY_URL", "")
        self.api_key = os.getenv("EMAIL_DELIVERY_API_KEY", "")

    async def send(self, event_type: str, payload: dict[str, Any]) -> None:
        require_live_email_delivery()
        if not self.delivery_url:
            raise EmailDeliveryDisabled("Email provider is not configured")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.delivery_url,
                json={"event_type": event_type, "payload": payload},
                headers=headers,
            )
        response.raise_for_status()


EMAIL_TEMPLATES = {
    "booking.confirmed": ("Booking confirmed", "Your BREERO booking is confirmed."),
    "technician.assigned": ("Technician assigned", "A technician has been assigned."),
    "quote.available": ("Quote available", "Your quote is ready for review."),
    "quote.approved": ("Quote approved", "Your quote has been approved."),
    "payment.receipt": ("Payment receipt", "Thank you. Your payment was received."),
    "password.reset": ("Reset your password", "Use the secure reset link supplied."),
    "email.verification": ("Verify your email", "Use the secure verification link supplied."),
    "job.completed": ("Job complete", "Your BREERO job has been completed."),
}


def render_email(event_type: str, context: dict[str, Any] | None = None) -> RenderedEmail:
    if event_type not in EMAIL_TEMPLATES:
        raise ValueError(f"Unsupported email event: {event_type}")
    subject, body = EMAIL_TEMPLATES[event_type]
    values = context or {}
    return RenderedEmail(subject.format_map(values), body.format_map(values))
