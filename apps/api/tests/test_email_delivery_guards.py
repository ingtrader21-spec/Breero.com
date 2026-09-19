from unittest.mock import AsyncMock, MagicMock, Mock

import httpx
import pytest

from app.config import Settings, settings
from app.integrations import email


def configure(monkeypatch):
    monkeypatch.setattr(settings, "live_email_delivery", True)
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "transactional_email_mode", "controlled_canary")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.invalid")
    monkeypatch.setattr(settings, "smtp_from_email", "breero@example.invalid")
    monkeypatch.setenv("EMAIL_DELIVERY_URL", "https://email.example.invalid/send")


def test_live_email_is_dark_by_default(monkeypatch):
    monkeypatch.delenv("LIVE_EMAIL_DELIVERY", raising=False)
    assert Settings(app_env="test", _env_file=None).live_email_delivery is False


@pytest.mark.parametrize("flag,value", [
    ("live_email_delivery", False), ("email_enabled", False),
    ("transactional_email_mode", "disabled"), ("transactional_email_mode", "unknown"),
])
@pytest.mark.parametrize("transport", ["http", "smtp"])
async def test_disabled_delivery_cannot_open_network(monkeypatch, flag, value, transport):
    configure(monkeypatch)
    adapter = email.EmailAdapter() if transport == "http" else email.SmtpEmailGateway()
    monkeypatch.setattr(settings, flag, value)
    http, smtp = Mock(), Mock()
    monkeypatch.setattr(email.httpx, "AsyncClient", http)
    monkeypatch.setattr(email.smtplib, "SMTP", smtp)
    with pytest.raises(email.EmailDeliveryDisabled) as error:
        if transport == "http":
            await adapter.send("password_changed", {"email": "synthetic@example.invalid"})
        else:
            await adapter.send(to="synthetic@example.invalid", subject="Test", text="Synthetic")
    assert error.value.pending_configuration is True
    assert error.value.code == "EMAIL_DELIVERY_DISABLED"
    http.assert_not_called()
    smtp.assert_not_called()


async def test_http_delivery_rechecks_gate_on_same_adapter(monkeypatch):
    configure(monkeypatch)
    client = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = client
    client.post.return_value = httpx.Response(202, request=httpx.Request("POST", "https://email.example.invalid/send"))
    monkeypatch.setattr(email.httpx, "AsyncClient", Mock(return_value=context))
    adapter = email.EmailAdapter()
    await adapter.send("password_changed", {"fixture": True})
    monkeypatch.setattr(settings, "live_email_delivery", False)
    with pytest.raises(email.EmailDeliveryDisabled):
        await adapter.send("password_changed", {"fixture": True})
    client.post.assert_awaited_once()


async def test_smtp_rechecks_after_thread_dispatch(monkeypatch):
    configure(monkeypatch)
    smtp = Mock()
    monkeypatch.setattr(email.smtplib, "SMTP", smtp)

    async def deferred(function):
        monkeypatch.setattr(settings, "live_email_delivery", False)
        function()

    monkeypatch.setattr(email.asyncio, "to_thread", deferred)
    with pytest.raises(email.EmailDeliveryDisabled):
        await email.SmtpEmailGateway().send(to="synthetic@example.invalid", subject="Test", text="Synthetic")
    smtp.assert_not_called()


async def test_enabled_smtp_preserves_transport_sequence_with_mock(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(settings, "smtp_username", "")
    client, context = Mock(), MagicMock()
    context.__enter__.return_value = client
    smtp = Mock(return_value=context)
    monkeypatch.setattr(email.smtplib, "SMTP", smtp)
    result = await email.SmtpEmailGateway().send(
        to="synthetic@example.invalid", subject="Test", text="Synthetic",
    )
    assert result == "smtp-accepted"
    client.starttls.assert_called_once()
    client.send_message.assert_called_once()
    client.login.assert_not_called()


async def test_missing_http_configuration_cannot_report_local_success(monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv("EMAIL_DELIVERY_URL", raising=False)
    with pytest.raises(email.EmailDeliveryDisabled, match="not configured"):
        await email.EmailAdapter().send("password_changed", {"fixture": True})
