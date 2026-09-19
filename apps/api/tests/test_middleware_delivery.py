import hashlib
import hmac
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.config import settings
from app.integrations.middleware import MiddlewareAdapter, canonical_body
from app.integrations.odoo import OdooDeliveryError


def configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    secret = tmp_path / "hmac"
    secret.write_bytes(b"x" * 48)
    monkeypatch.setattr(settings, "middleware_enabled", True)
    monkeypatch.setattr(settings, "middleware_url", "https://middleware.internal.codestra.agency")
    monkeypatch.setattr(settings, "middleware_ca_file", "/run/secrets/codestra-ca.pem")
    monkeypatch.setattr(settings, "middleware_client_cert_file", "/run/secrets/breero-client.pem")
    monkeypatch.setattr(settings, "middleware_client_key_file", "/run/secrets/breero-client.key")
    monkeypatch.setattr(settings, "middleware_hmac_key_id", "breero-key-1")
    monkeypatch.setattr(settings, "middleware_hmac_secret_file", str(secret))
    monkeypatch.setattr(settings, "middleware_service_identity", "breero-staging")
    monkeypatch.setattr(settings, "middleware_audience", "codestra-middleware-breero")
    monkeypatch.setattr(settings, "middleware_tenant", "breero")
    monkeypatch.setattr(settings, "middleware_scope", "breero.crm.events.submit")
    monkeypatch.setattr(settings, "app_env", "staging")
    return secret


def event(event_type: str = "breero.service_request.created") -> SimpleNamespace:
    identifier = uuid.uuid4()
    return SimpleNamespace(id=identifier, event_type=event_type, aggregate_id=identifier,
        aggregate_version=1, schema_version=1, idempotency_key=f"breero:{identifier}:1",
        created_at=None, payload={"submission_id": str(identifier), "route": "SERVICE_REQUEST"})


def test_hmac_binds_identity_tenant_scope_and_exact_body(monkeypatch, tmp_path):
    secret = configure(monkeypatch, tmp_path)
    body = canonical_body({"event_id": "event-1"})
    headers = MiddlewareAdapter.headers(body, "idem-1", "2026-08-13T00:00:00+00:00", "nonce-1")
    material = "\n".join(("HMAC-V2", "POST", "/api/v1/integrations/breero/events",
        headers["X-Codestra-Timestamp"], headers["X-Codestra-Nonce"], "breero-staging",
        "codestra-middleware-breero", "staging", "breero.crm.events.submit", "idem-1",
        hashlib.sha256(body).hexdigest())).encode()
    assert hmac.compare_digest(headers["X-Codestra-Signature"], hmac.new(secret.read_bytes(), material, hashlib.sha256).hexdigest())
    assert headers["X-Codestra-Tenant"] == "breero"
    assert headers["X-HMAC-Key-ID"] == "breero-key-1"


def test_rejects_non_allowlisted_event():
    with pytest.raises(OdooDeliveryError, match="MIDDLEWARE_EVENT_NOT_ALLOWED"):
        MiddlewareAdapter.envelope(event("breero.payment.created"))


@pytest.mark.asyncio
async def test_delivery_uses_typed_route_and_ack(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    requests = []
    def handler(request: httpx.Request):
        requests.append(request)
        envelope = json.loads(request.content)
        return httpx.Response(202, json={"event_id": envelope["event_id"], "status": "queued"})
    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **{k:v for k,v in kwargs.items() if k not in {"verify", "cert"}}))
    result = await MiddlewareAdapter().deliver(event())
    assert result.model == "middleware.pending"
    assert requests[0].url.path == "/api/v1/integrations/breero/events"
    assert b"odoo_api_key" not in requests[0].content


@pytest.mark.asyncio
async def test_disabled_delivery_fails_closed():
    previous = settings.middleware_enabled
    settings.middleware_enabled = False
    try:
        with pytest.raises(OdooDeliveryError, match="MIDDLEWARE_DISABLED"):
            await MiddlewareAdapter().deliver(event())
    finally:
        settings.middleware_enabled = previous


def test_private_middleware_hostname_is_pinned_in_delivery_overlays():
    repository = Path(__file__).resolve().parents[3]
    compose_paths = (
        repository / "deploy/staging/docker-compose.middleware.yml",
        repository / "docker-compose.middleware.yml",
    )
    for compose_path in compose_paths:
        compose = compose_path.read_text()
        assert 'middleware.internal.codestra.agency:10.40.0.1' in compose
