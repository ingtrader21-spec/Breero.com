from app.integrations.contracts import IntegrationNotConfigured, SmsGateway

__all__ = ["FakeSmsGateway", "SmsGateway", "UnconfiguredSmsGateway", "render_sms"]


class FakeSmsGateway:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, text: str) -> str:
        self.sent.append({"to": to, "text": text})
        return f"fake-sms-{len(self.sent)}"


class UnconfiguredSmsGateway:
    async def send(self, *, to: str, text: str) -> str:
        raise IntegrationNotConfigured("SMS provider is not configured")


SMS_TEMPLATES = {
    "booking.confirmed": "Your BREERO booking is confirmed.",
    "technician.on_the_way": "Your BREERO technician is on the way.",
    "technician.arrived": "Your BREERO technician has arrived.",
    "quote.available": "Your BREERO quote is ready.",
    "payment.required": "Important: payment action is required for your BREERO booking.",
}


def render_sms(event_type: str) -> str:
    try:
        return SMS_TEMPLATES[event_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported SMS event: {event_type}") from exc
