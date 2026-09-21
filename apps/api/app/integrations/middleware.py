"""Typed BREERO-to-Codestra-middleware delivery using HMAC-V2.

Odoo credentials and generic model names never cross this boundary.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import settings
from app.integrations.contracts import EventDeliveryError, EventDeliveryResult
from app.integrations.event_envelope import build_event_envelope

OdooDeliveryError = EventDeliveryError
OdooResult = EventDeliveryResult

PATH = "/api/v1/integrations/breero/events"
VERSION = "HMAC-V2"
ALLOWED_EVENTS = {
    "breero.service_request.created",
    "breero.contact_request.created",
    "breero.provider_interest.created",
    "breero.lead_dispute.created",
}


def canonical_body(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


class MiddlewareAdapter:
    @staticmethod
    def envelope(event: object) -> dict:
        envelope = build_event_envelope(event)
        if envelope["event_type"] not in ALLOWED_EVENTS:
            raise OdooDeliveryError("MIDDLEWARE_EVENT_NOT_ALLOWED", terminal=True)
        return envelope

    @staticmethod
    def _secret() -> bytes:
        path = Path(settings.middleware_hmac_secret_file)
        try:
            secret = path.read_bytes().strip()
        except OSError as exc:
            raise OdooDeliveryError("MIDDLEWARE_SECRET_UNAVAILABLE", terminal=True) from exc
        if len(secret) < 32:
            raise OdooDeliveryError("MIDDLEWARE_SECRET_INVALID", terminal=True)
        return secret

    @staticmethod
    def headers(
        body: bytes,
        idempotency_key: str,
        timestamp: str,
        nonce: str,
    ) -> dict[str, str]:
        digest = hashlib.sha256(body).hexdigest()
        values = (
            VERSION,
            "POST",
            PATH,
            timestamp,
            nonce,
            settings.middleware_service_identity,
            settings.middleware_audience,
            settings.app_env,
            settings.middleware_scope,
            idempotency_key,
            digest,
        )
        if any(not value or "\n" in value or "\r" in value for value in values):
            raise OdooDeliveryError(
                "MIDDLEWARE_SIGNING_CONFIGURATION_INVALID", terminal=True
            )
        signature = hmac.new(
            MiddlewareAdapter._secret(),
            "\n".join(values).encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "Content-Type": "application/json",
            "X-Codestra-Signature-Version": VERSION,
            "X-Service-Identity": settings.middleware_service_identity,
            "X-Service-Audience": settings.middleware_audience,
            "X-Codestra-Timestamp": timestamp,
            "X-Codestra-Nonce": nonce,
            "X-Codestra-Content-SHA256": digest,
            "X-Codestra-Signature": signature,
            "X-HMAC-Key-ID": settings.middleware_hmac_key_id,
            "X-Codestra-Environment": settings.app_env,
            "X-Codestra-Scope": settings.middleware_scope,
            "X-Codestra-Tenant": settings.middleware_tenant,
            "Idempotency-Key": idempotency_key,
        }

    async def deliver(self, event: object) -> OdooResult:
        if not settings.middleware_enabled:
            raise OdooDeliveryError("MIDDLEWARE_DISABLED", terminal=True)
        envelope = self.envelope(event)
        body = canonical_body(envelope)
        headers = self.headers(
            body,
            envelope["idempotency_key"],
            datetime.now(UTC).isoformat(),
            str(uuid.uuid4()),
        )
        try:
            async with httpx.AsyncClient(
                timeout=20,
                verify=settings.middleware_ca_file,
                cert=(
                    settings.middleware_client_cert_file,
                    settings.middleware_client_key_file,
                ),
            ) as client:
                response = await client.post(
                    settings.middleware_url.rstrip("/") + PATH,
                    content=body,
                    headers=headers,
                )
                response.raise_for_status()
                acknowledgement = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise OdooDeliveryError("MIDDLEWARE_UNAVAILABLE") from exc
        except httpx.HTTPStatusError as exc:
            terminal = exc.response.status_code in {400, 401, 403, 404, 409, 422}
            raise OdooDeliveryError(
                f"MIDDLEWARE_HTTP_{exc.response.status_code}", terminal=terminal
            ) from exc
        if acknowledgement.get("event_id") != envelope["event_id"] or acknowledgement.get(
            "status"
        ) not in {"queued", "delivered", "replayed"}:
            raise OdooDeliveryError("MIDDLEWARE_INVALID_ACK", terminal=True)
        external_id = acknowledgement.get("odoo_record_id") or 0
        return OdooResult(
            int(external_id),
            str(acknowledgement.get("odoo_model", "middleware.pending")),
        )
