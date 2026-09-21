"""Provider-neutral integration contracts.

Domain and application code may depend on these protocols and immutable result
objects. Concrete provider modules implement them but do not own the contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.domains.payments.schemas import ProviderIntent, ProviderRefund


class IntegrationNotConfigured(RuntimeError):
    """Raised when a disabled or unconfigured provider is invoked."""

    code = "integration_not_configured"


@dataclass(frozen=True, slots=True)
class GeocodedAddress:
    formatted_address: str
    line1: str
    city: str
    postal_code: str
    country_code: str
    latitude: float
    longitude: float
    provider: str
    provider_reference: str | None = None
    confidence: float | None = None
    quality: str | None = None
    state_code: str | None = None
    timezone_name: str | None = None
    line2: str | None = None
    county: str | None = None
    postal_code_plus4: str | None = None


class GeocodingGateway(Protocol):
    async def resolve_timezone(self, latitude: float, longitude: float) -> str: ...

    async def geocode(self, address: str) -> GeocodedAddress: ...


class PaymentProvider(Protocol):
    async def create_intent(
        self,
        *,
        amount_minor: int,
        currency: str,
        capture_method: str,
        metadata: dict[str, str],
        idempotency_key: str,
    ) -> ProviderIntent: ...

    async def capture_intent(
        self,
        provider_payment_id: str,
        *,
        amount_minor: int | None,
        idempotency_key: str,
    ) -> ProviderIntent: ...

    def verify_webhook(self, body: bytes, signature: str) -> dict[str, Any]: ...

    async def create_refund(
        self,
        provider_payment_id: str,
        *,
        amount_minor: int,
        idempotency_key: str,
    ) -> ProviderRefund: ...


class EmailGateway(Protocol):
    async def send(self, *, to: str, subject: str, text: str) -> str: ...


class SmsGateway(Protocol):
    async def send(self, *, to: str, text: str) -> str: ...


@dataclass(frozen=True, slots=True)
class TransferResult:
    transfer_id: str
    status: str
    provider_reference: str | None = None


class PayoutGateway(Protocol):
    async def create_transfer(
        self,
        *,
        amount_minor: int,
        currency: str,
        destination: str,
        idempotency_key: str,
    ) -> TransferResult: ...

    async def get_transfer(self, transfer_id: str) -> TransferResult: ...

    async def cancel_transfer(self, transfer_id: str) -> TransferResult: ...


class EventDeliveryError(RuntimeError):
    def __init__(self, code: str, *, terminal: bool = False):
        super().__init__(code)
        self.code = code
        self.terminal = terminal


@dataclass(frozen=True, slots=True)
class EventDeliveryResult:
    external_id: int
    model: str


class CrmEventDeliveryGateway(Protocol):
    async def deliver(self, event: object) -> EventDeliveryResult: ...

    async def health(self) -> dict[str, Any]: ...
