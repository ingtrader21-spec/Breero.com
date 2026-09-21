import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.domains.payments.exceptions import InvalidWebhook, PaymentError
from app.domains.payments.schemas import ProviderIntent, ProviderRefund
from app.integrations.contracts import PaymentProvider

__all__ = ["PaymentProvider", "StripeAdapter"]


@dataclass(slots=True)
class StripeAdapter:
    secret_key: str
    webhook_secret: str
    api_base: str = "https://api.stripe.com/v1"
    webhook_tolerance_seconds: int = 300

    @classmethod
    def from_environment(cls) -> "StripeAdapter":
        # Settings resolves supported *_FILE bindings without copying secrets
        # into environment variables, command arguments, or image layers.
        from app.config import settings

        return cls(
            secret_key=settings.stripe_secret_key,
            webhook_secret=settings.stripe_webhook_secret,
            api_base=os.getenv("STRIPE_API_BASE", "https://api.stripe.com/v1"),
        )

    async def _post(self, path: str, data: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        if not self.secret_key:
            raise PaymentError("Stripe is not configured")
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.api_base}{path}",
                data=data,
                auth=(self.secret_key, ""),
                headers={"Idempotency-Key": idempotency_key},
            )
        if response.is_error:
            try:
                message = response.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = "Payment provider request failed"
            raise PaymentError(message)
        return response.json()

    async def create_intent(
        self,
        *,
        amount_minor: int,
        currency: str,
        capture_method: str,
        metadata: dict[str, str],
        idempotency_key: str,
    ) -> ProviderIntent:
        data: dict[str, Any] = {
            "amount": amount_minor,
            "currency": currency,
            "capture_method": capture_method,
            "automatic_payment_methods[enabled]": "true",
        }
        data.update({f"metadata[{key}]": value for key, value in metadata.items()})
        raw = await self._post("/payment_intents", data, idempotency_key)
        return self._to_intent(raw)

    async def capture_intent(
        self,
        provider_payment_id: str,
        *,
        amount_minor: int | None,
        idempotency_key: str,
    ) -> ProviderIntent:
        data = {"amount_to_capture": amount_minor} if amount_minor is not None else {}
        raw = await self._post(
            f"/payment_intents/{provider_payment_id}/capture", data, idempotency_key
        )
        return self._to_intent(raw)

    async def create_refund(
        self, provider_payment_id: str, *, amount_minor: int, idempotency_key: str
    ) -> ProviderRefund:
        raw = await self._post(
            "/refunds",
            {"payment_intent": provider_payment_id, "amount": amount_minor},
            idempotency_key,
        )
        return ProviderRefund(id=raw["id"], status=raw.get("status", "pending"))

    def verify_webhook(self, body: bytes, signature: str) -> dict[str, Any]:
        if not self.webhook_secret:
            raise InvalidWebhook("Stripe webhook secret is not configured")
        parts: dict[str, list[str]] = {}
        for item in signature.split(","):
            key, separator, value = item.partition("=")
            if separator:
                parts.setdefault(key, []).append(value)
        try:
            timestamp = int(parts["t"][0])
            signatures = parts["v1"]
        except (KeyError, ValueError, IndexError) as exc:
            raise InvalidWebhook("Malformed Stripe-Signature header") from exc
        if abs(int(time.time()) - timestamp) > self.webhook_tolerance_seconds:
            raise InvalidWebhook("Webhook signature timestamp is outside tolerance")
        signed = f"{timestamp}.".encode() + body
        expected = hmac.new(self.webhook_secret.encode(), signed, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
            raise InvalidWebhook("Webhook signature verification failed")
        try:
            event = json.loads(body)
        except json.JSONDecodeError as exc:
            raise InvalidWebhook("Webhook payload is not valid JSON") from exc
        if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
            raise InvalidWebhook("Webhook payload is missing event identity")
        return event

    @staticmethod
    def _to_intent(raw: dict[str, Any]) -> ProviderIntent:
        return ProviderIntent(
            id=raw["id"],
            status=raw.get("status", ""),
            client_secret=raw.get("client_secret"),
            amount_received=raw.get("amount_received", 0),
            raw=raw,
        )
