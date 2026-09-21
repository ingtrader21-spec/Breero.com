import ast
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.integrations.contracts import (
    EmailGateway,
    EventDeliveryError,
    EventDeliveryResult,
    GeocodedAddress,
    GeocodingGateway,
    IntegrationNotConfigured,
    PaymentProvider,
    PayoutGateway,
    SmsGateway,
    TransferResult,
)
from app.integrations.email import (
    EmailGateway as CompatibilityEmailGateway,
)
from app.integrations.email import (
    FakeEmailGateway,
)
from app.integrations.event_envelope import build_event_envelope
from app.integrations.geocoding import (
    FakeGeocodingAdapter,
)
from app.integrations.geocoding import (
    GeocodedAddress as CompatibilityGeocodedAddress,
)
from app.integrations.geocoding import (
    GeocodingGateway as CompatibilityGeocodingGateway,
)
from app.integrations.middleware import (
    MiddlewareAdapter,
)
from app.integrations.middleware import (
    OdooDeliveryError as MiddlewareDeliveryError,
)
from app.integrations.middleware import (
    OdooResult as MiddlewareDeliveryResult,
)
from app.integrations.odoo import OdooAdapter, OdooDeliveryError, OdooResult
from app.integrations.payouts import (
    FakePayoutGateway,
)
from app.integrations.payouts import (
    IntegrationNotConfigured as CompatibilityNotConfigured,
)
from app.integrations.payouts import (
    PayoutGateway as CompatibilityPayoutGateway,
)
from app.integrations.payouts import (
    TransferResult as CompatibilityTransferResult,
)
from app.integrations.sms import FakeSmsGateway
from app.integrations.sms import SmsGateway as CompatibilitySmsGateway
from app.integrations.stripe import (
    PaymentProvider as CompatibilityPaymentProvider,
)
from app.integrations.stripe import (
    StripeAdapter,
)

API_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_MODULES = {
    "email.py": {"EmailGateway"},
    "geocoding.py": {"GeocodedAddress", "GeocodingGateway"},
    "odoo.py": {"OdooDeliveryError", "OdooResult"},
    "payouts.py": {"IntegrationNotConfigured", "PayoutGateway", "TransferResult"},
    "sms.py": {"SmsGateway"},
    "stripe.py": {"PaymentProvider"},
}


def test_compatibility_exports_share_one_contract_authority() -> None:
    assert CompatibilityEmailGateway is EmailGateway
    assert CompatibilityGeocodedAddress is GeocodedAddress
    assert CompatibilityGeocodingGateway is GeocodingGateway
    assert CompatibilityNotConfigured is IntegrationNotConfigured
    assert CompatibilityPayoutGateway is PayoutGateway
    assert CompatibilityTransferResult is TransferResult
    assert CompatibilitySmsGateway is SmsGateway
    assert CompatibilityPaymentProvider is PaymentProvider
    assert OdooDeliveryError is EventDeliveryError
    assert OdooResult is EventDeliveryResult
    assert MiddlewareDeliveryError is EventDeliveryError
    assert MiddlewareDeliveryResult is EventDeliveryResult


def test_provider_modules_do_not_redeclare_shared_contracts() -> None:
    integration_root = API_ROOT / "app" / "integrations"
    for filename, prohibited_names in PROVIDER_MODULES.items():
        tree = ast.parse((integration_root / filename).read_text())
        declared = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        assert declared.isdisjoint(prohibited_names), (
            f"{filename} redeclared provider-neutral contracts: "
            f"{sorted(declared & prohibited_names)}"
        )


def test_middleware_does_not_import_the_odoo_provider() -> None:
    source = (API_ROOT / "app" / "integrations" / "middleware.py").read_text()
    assert "app.integrations.odoo" not in source
    assert "OdooAdapter" not in source


def test_odoo_and_middleware_share_the_canonical_event_envelope() -> None:
    event = SimpleNamespace(
        id="event-1",
        event_type="breero.service_request.created",
        schema_version=2,
        aggregate_id="request-1",
        aggregate_version=3,
        created_at=datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        idempotency_key="delivery-key-1",
        payload={"request_id": "request-1"},
    )
    canonical = build_event_envelope(event)
    assert OdooAdapter.envelope(event) == canonical
    assert MiddlewareAdapter.envelope(event) == canonical


def test_existing_adapters_satisfy_the_neutral_protocols() -> None:
    address = GeocodedAddress(
        formatted_address="1 Main St",
        line1="1 Main St",
        city="Austin",
        postal_code="78701",
        country_code="US",
        latitude=30.0,
        longitude=-97.0,
        provider="fake",
    )
    email: EmailGateway = FakeEmailGateway()
    sms: SmsGateway = FakeSmsGateway()
    geocoder: GeocodingGateway = FakeGeocodingAdapter(address)
    payment: PaymentProvider = StripeAdapter(secret_key="", webhook_secret="")
    payout: PayoutGateway = FakePayoutGateway()
    assert email is not None
    assert sms is not None
    assert geocoder is not None
    assert payment is not None
    assert payout is not None
