"""Private, asynchronous Odoo CRM delivery boundary.

BREERO sends typed events to the dedicated ``breero_crm`` module. It never exposes a
generic model-write API and never delegates operational or financial authority to Odoo.
"""

from typing import Any

import httpx

from app.config import settings
from app.integrations.contracts import EventDeliveryError, EventDeliveryResult
from app.integrations.event_envelope import build_event_envelope, value_from

OdooDeliveryError = EventDeliveryError
OdooResult = EventDeliveryResult

__all__ = [
    "BookingOdooMapper",
    "CustomerOdooMapper",
    "JobOdooMapper",
    "OdooAdapter",
    "OdooDeliveryError",
    "OdooMapper",
    "OdooResult",
    "PaymentOdooMapper",
    "PayoutOdooMapper",
    "PublicSubmissionOdooMapper",
    "VendorOdooMapper",
]


def _value(source: object, name: str, default: Any = None) -> Any:
    return value_from(source, name, default)


class OdooMapper:
    model: str

    def map(self, source: object) -> dict:
        raise NotImplementedError


class CustomerOdooMapper(OdooMapper):
    model = "res.partner"

    def map(self, source: object) -> dict:
        return {
            "name": f"{_value(source, 'first_name', '')} {_value(source, 'last_name', '')}".strip(),
            "email": _value(source, "email"),
            "phone": _value(source, "phone"),
            "x_breero_customer_id": str(_value(source, "id")),
        }


class VendorOdooMapper(OdooMapper):
    model = "res.partner"

    def map(self, source: object) -> dict:
        return {
            "name": _value(source, "name"),
            "x_breero_provider_id": str(_value(source, "id")),
        }


class BookingOdooMapper(OdooMapper):
    model = "crm.lead"

    def map(self, source: object) -> dict:
        return {
            "x_breero_booking_id": str(_value(source, "id")),
            "x_breero_booking_status": str(_value(source, "status", "")),
        }


class JobOdooMapper(OdooMapper):
    model = "crm.lead"

    def map(self, source: object) -> dict:
        return {
            "x_breero_job_id": str(_value(source, "id")),
            "x_breero_job_status": str(_value(source, "status", "")),
        }


class PaymentOdooMapper(OdooMapper):
    model = "crm.lead"

    def map(self, source: object) -> dict:
        return {"x_breero_payment_status": str(_value(source, "status", ""))}


class PayoutOdooMapper(OdooMapper):
    """Payouts are intentionally not written to Odoo by this CRM integration."""

    model = "crm.lead"

    def map(self, source: object) -> dict:
        return {}


class PublicSubmissionOdooMapper(OdooMapper):
    model = "crm.lead"

    def map(self, source: object) -> dict:
        payload = _value(source, "payload", source)
        route = str(_value(source, "route", "CONTACT"))
        record_type = {
            "SERVICE_REQUEST": "service_request",
            "CONTACT": "contact_request",
            "PROVIDER_INTEREST": "provider_interest",
        }.get(route, "contact_request")
        return {
            "x_breero_request_id": str(_value(source, "submission_id")),
            "x_breero_external_reference": str(_value(source, "submission_id")),
            "x_breero_record_type": record_type,
            "contact_name": _value(payload, "name") or _value(payload, "contact_name"),
            "partner_name": _value(payload, "business_name"),
            "email_from": _value(payload, "email"),
            "phone": _value(payload, "phone"),
            "x_breero_contact_preference": _value(payload, "contact_preference"),
            "x_breero_source_url": _value(payload, "source_url"),
        }


MAPPERS = {
    "customer": CustomerOdooMapper(),
    "vendor": VendorOdooMapper(),
    "booking": BookingOdooMapper(),
    "job": JobOdooMapper(),
    "payment": PaymentOdooMapper(),
    "payout": PayoutOdooMapper(),
    "public_submission": PublicSubmissionOdooMapper(),
}


class OdooAdapter:
    async def execute(
        self,
        model: str,
        method: str,
        args: list,
        kwargs: dict | None = None,
    ) -> Any:
        if not all(
            (
                settings.odoo_url,
                settings.odoo_database,
                settings.odoo_username,
                settings.odoo_api_key,
            )
        ):
            raise OdooDeliveryError("ODOO_NOT_CONFIGURED", terminal=True)
        rpc = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    settings.odoo_database,
                    settings.odoo_username,
                    settings.odoo_api_key,
                    model,
                    method,
                    args,
                    kwargs or {},
                ],
            },
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{settings.odoo_url.rstrip('/')}/jsonrpc", json=rpc
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise OdooDeliveryError("ODOO_UNAVAILABLE") from exc
        except httpx.HTTPStatusError as exc:
            terminal = exc.response.status_code in {400, 401, 403}
            raise OdooDeliveryError(
                f"ODOO_HTTP_{exc.response.status_code}", terminal=terminal
            ) from exc
        if body.get("error"):
            data = body["error"].get("data", {})
            name = str(data.get("name", ""))
            terminal = any(term in name for term in ("AccessDenied", "ValidationError", "AccessError"))
            raise OdooDeliveryError(
                "ODOO_AUTH_OR_VALIDATION" if terminal else "ODOO_RPC_ERROR",
                terminal=terminal,
            )
        return body.get("result")

    @staticmethod
    def envelope(event: object) -> dict:
        return build_event_envelope(event)

    async def deliver(self, event: object) -> OdooResult:
        result = await self.execute(
            "breero.sync.event", "process_breero_event", [self.envelope(event)]
        )
        if not isinstance(result, dict) or not result.get("odoo_record_id"):
            raise OdooDeliveryError("ODOO_INVALID_ACK", terminal=True)
        return OdooResult(
            int(result["odoo_record_id"]),
            str(result.get("odoo_model", "crm.lead")),
        )

    async def health(self) -> dict:
        result = await self.execute("breero.sync.event", "integration_health", [])
        return result if isinstance(result, dict) else {"status": "invalid"}

    async def upsert(self, aggregate_type: str, source: object) -> object:
        # Compatibility helper for unit callers; worker delivery always uses typed events.
        mapper = MAPPERS.get(aggregate_type.lower())
        if not mapper:
            raise ValueError(f"No Odoo mapper for {aggregate_type}")
        return await self.execute(mapper.model, "create", [mapper.map(source)])
