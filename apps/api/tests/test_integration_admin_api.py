import uuid
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import integrations
from app.config import settings
from app.domains.auth.access_service import DEFAULT_PERMISSIONS
from app.domains.auth.models import AccessRole, User
from app.main import app


def test_admin_integration_endpoints_are_in_openapi() -> None:
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/integrations/config"]
    assert "get" in paths["/api/v1/integrations/operations"]
    assert "post" in paths["/api/v1/integrations/outbox/activate-pending"]
    assert "post" in paths["/api/v1/integrations/outbox/park-unconfigured"]


def test_admin_default_access_separates_integration_read_and_control() -> None:
    permissions = DEFAULT_PERMISSIONS[AccessRole.admin]
    assert "admin.integrations.read" in permissions
    assert "admin.integrations.manage" in permissions
    assert "admin.integrations.manage" not in DEFAULT_PERMISSIONS[AccessRole.finance]


def test_integration_config_exposes_only_configuration_signals(monkeypatch) -> None:
    monkeypatch.setattr(settings, "middleware_enabled", True)
    monkeypatch.setattr(settings, "middleware_url", "https://middleware.internal.example")
    monkeypatch.setattr(settings, "middleware_ca_file", "/run/secrets/ca.pem")
    monkeypatch.setattr(settings, "middleware_client_cert_file", "/run/secrets/client.crt")
    monkeypatch.setattr(settings, "middleware_client_key_file", "/run/secrets/client.key")
    monkeypatch.setattr(settings, "middleware_hmac_key_id", "breero-production")
    monkeypatch.setattr(settings, "middleware_hmac_secret_file", "/run/secrets/hmac")
    monkeypatch.setattr(settings, "middleware_service_identity", "breero-production")
    monkeypatch.setattr(settings, "middleware_audience", "codestra-middleware-breero")
    monkeypatch.setattr(settings, "middleware_tenant", "breero")
    monkeypatch.setattr(settings, "middleware_scope", "breero.crm.events.submit")
    monkeypatch.setattr(settings, "odoo_enabled", True)
    monkeypatch.setattr(settings, "odoo_url", "https://odoo.internal.example")
    monkeypatch.setattr(settings, "odoo_database", "breero")
    monkeypatch.setattr(settings, "odoo_username", "service-user")
    monkeypatch.setattr(settings, "odoo_api_key", "must-not-be-returned")

    payload = integrations._integration_config().model_dump()

    assert all(payload.values())
    assert not any("secret" in key or "password" in key or "api_key" in key for key in payload)
    serialized = repr(payload)
    assert "must-not-be-returned" not in serialized
    assert "/run/secrets/" not in serialized
    assert "middleware.internal.example" not in serialized
    assert "odoo.internal.example" not in serialized


@pytest.mark.asyncio
async def test_activate_pending_fails_closed_without_complete_middleware(monkeypatch) -> None:
    monkeypatch.setattr(settings, "middleware_enabled", False)
    monkeypatch.setattr(integrations, "_status_counts", AsyncMock(return_value={}))
    actor = cast(User, SimpleNamespace(id=uuid.uuid4()))

    with pytest.raises(HTTPException) as exc_info:
        await integrations._operate_outbox(
            cast(AsyncSession, SimpleNamespace()),
            actor,
            "activate_pending",
        )

    assert exc_info.value.status_code == 409
    assert "incompletely configured" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_park_operation_commits_audited_before_after_evidence(monkeypatch) -> None:
    before = {"PENDING": 2}
    after = {"PENDING_CONFIGURATION": 2}
    monkeypatch.setattr(
        integrations,
        "_status_counts",
        AsyncMock(side_effect=[before, after]),
    )
    park = AsyncMock(return_value=2)
    monkeypatch.setattr(
        integrations,
        "OutboxService",
        lambda _session: SimpleNamespace(park_unconfigured=park),
    )
    added = []
    session = SimpleNamespace(add=added.append, commit=AsyncMock())
    actor_id = uuid.uuid4()
    actor = cast(User, SimpleNamespace(id=actor_id))

    result = await integrations._operate_outbox(
        cast(AsyncSession, session),
        actor,
        "park_unconfigured",
    )

    park.assert_awaited_once_with(commit=False)
    session.commit.assert_awaited_once()
    assert result.operation_type == "park_unconfigured"
    assert result.actor_id == actor_id
    assert result.before_counts == before
    assert result.after_counts == after
    assert result.affected_count == 2
    assert len(added) == 1
    audit = added[0]
    assert audit.action == "integration.outbox.park_unconfigured"
    assert audit.resource_type == "integration_outbox_operation"
    assert audit.metadata_json["before_counts"] == before
    assert audit.metadata_json["after_counts"] == after
