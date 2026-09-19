from typing import Any

from app.secret_files import apply_secret_files

SECRET_BINDINGS: tuple[tuple[str, str], ...] = (
    ("database_url", "database_url_file"),
    ("redis_url", "redis_url_file"),
    ("jwt_secret", "jwt_secret_file"),
    ("jwt_refresh_secret", "jwt_refresh_secret_file"),
    ("stripe_secret_key", "stripe_secret_key_file"),
    ("stripe_webhook_secret", "stripe_webhook_secret_file"),
    ("stripe_publishable_key", "stripe_publishable_key_file"),
    ("geocoding_api_key", "geocoding_api_key_file"),
    ("payout_api_key", "payout_api_key_file"),
    ("smtp_password", "smtp_password_file"),
    ("sms_api_key", "sms_api_key_file"),
)


def resolve_secret_files(settings: Any) -> None:
    """Load configured file-backed values without exposing their contents."""

    apply_secret_files(settings, tuple(name for name, _ in SECRET_BINDINGS))


def validate_stripe_credentials(settings: Any) -> None:
    """Validate Stripe key formats and ensure key modes agree."""

    secret_mode = next(
        (
            mode
            for mode in ("test", "live")
            if settings.stripe_secret_key.startswith(f"sk_{mode}_")
        ),
        None,
    )
    publishable_mode = next(
        (
            mode
            for mode in ("test", "live")
            if settings.stripe_publishable_key.startswith(f"pk_{mode}_")
        ),
        None,
    )
    if settings.stripe_secret_key and secret_mode is None:
        raise ValueError("STRIPE_SECRET_KEY has an unsupported format")
    if settings.stripe_publishable_key and publishable_mode is None:
        raise ValueError("STRIPE_PUBLISHABLE_KEY has an unsupported format")
    if secret_mode and publishable_mode and secret_mode != publishable_mode:
        raise ValueError("Stripe secret and publishable keys must use the same mode")
    if settings.stripe_webhook_secret and not settings.stripe_webhook_secret.startswith(
        "whsec_"
    ):
        raise ValueError("STRIPE_WEBHOOK_SECRET has an unsupported format")
