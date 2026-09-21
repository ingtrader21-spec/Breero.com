from pathlib import Path

import pytest

from app import config
from app.settings import Settings, get_settings, settings
from app.settings.release import disabled_release_flags
from app.settings.secrets import SECRET_BINDINGS


def test_config_module_is_a_compatibility_facade() -> None:
    assert config.Settings is Settings
    assert config.get_settings is get_settings
    assert config.settings is settings


def test_config_facade_stays_small() -> None:
    path = Path(__file__).resolve().parents[1] / "app" / "config.py"
    assert len(path.read_text(encoding="utf-8").splitlines()) <= 12


def test_secret_file_bindings_are_explicit() -> None:
    assert ("database_url", "database_url_file") in SECRET_BINDINGS
    assert ("redis_url", "redis_url_file") in SECRET_BINDINGS
    assert ("jwt_secret", "jwt_secret_file") in SECRET_BINDINGS
    assert ("jwt_refresh_secret", "jwt_refresh_secret_file") in SECRET_BINDINGS


def test_release_boundary_lists_every_high_risk_capability() -> None:
    flags = disabled_release_flags(Settings())
    expected = {
        "AUTO_ASSIGN_PROVIDER",
        "AUTO_CONFIRM_BOOKING",
        "LIVE_PROVIDER_DISPATCH",
        "LIVE_SMS_DELIVERY",
        "LIVE_CALLBACKS",
        "ODOO_DELIVERY_ENABLED",
        "ODOO_WRITE_ENABLED",
        "PUBLIC_BOOKING_API_ENABLED",

        "STRIPE_ENABLED",
        "PAYMENTS_ENABLED",
        "ONLINE_CHECKOUT_ENABLED",
        "PAID_LEADS_ENABLED",
        "AUTOMATIC_REFUNDS_ENABLED",
        "PAYOUT_ENABLED",
        "AUTOMATIC_BOOKING_ENABLED",
        "AUTOMATIC_PROVIDER_ASSIGNMENT_ENABLED",
        "AUTOMATIC_CONFIRMED_BOOKINGS",
        "PROVIDER_SELF_SERVICE_ENABLED",
        "MARKETPLACE_MATCHING_ENABLED",
        "MARKETPLACE_MESSAGING_ENABLED",
        "MARKETPLACE_REVIEWS_ENABLED",
        "MARKETING_EMAIL_ENABLED",
        "LIVE_EMAIL_DELIVERY",
        "MARKETING_SMS_ENABLED",
    }
    assert expected == set(flags)


def test_keycloak_secret_files_are_loaded(tmp_path: Path) -> None:
    client = tmp_path / "client"
    provisioner = tmp_path / "provisioner"
    client.write_text("SYNTHETIC-client-file")
    provisioner.write_text("SYNTHETIC-provisioner-file")
    client.chmod(0o600)
    provisioner.chmod(0o600)
    configured = Settings(
        app_env="test",
        keycloak_client_secret_file=str(client),
        keycloak_provisioner_client_secret_file=str(provisioner),
    )
    assert configured.keycloak_client_secret == "SYNTHETIC-client-file"
    assert configured.keycloak_provisioner_client_secret == "SYNTHETIC-provisioner-file"


@pytest.mark.parametrize("name", ["keycloak_client_secret", "keycloak_provisioner_client_secret"])
def test_keycloak_secret_sources_cannot_conflict(name: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="configure only one source"):
        Settings(app_env="test", **{name: "SYNTHETIC-inline", f"{name}_file": str(tmp_path / "secret")})
