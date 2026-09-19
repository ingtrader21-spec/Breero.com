from pathlib import Path

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
