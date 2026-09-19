from typing import Any

PRODUCTION_FILE_BINDINGS = (
    "database_url",
    "redis_url",
    "jwt_secret",
    "jwt_refresh_secret",
)

INSECURE_DEFAULTS = {
    "development-only-change-me",
    "development-only-change-me-too",
    "change-me",
    "change-me-too",
    "breero",
}


def required_environment_values(settings: Any) -> dict[str, str]:
    required = {
        "DATABASE_URL": settings.database_url,
        "REDIS_URL": settings.redis_url,
        "JWT_SECRET": settings.jwt_secret,
        "JWT_REFRESH_SECRET": settings.jwt_refresh_secret,
    }
    if settings.stripe_enabled:
        required |= {
            "STRIPE_SECRET_KEY": settings.stripe_secret_key,
            "STRIPE_WEBHOOK_SECRET": settings.stripe_webhook_secret,
            "STRIPE_PUBLISHABLE_KEY": settings.stripe_publishable_key,
        }
    if settings.geocoding_enabled:
        required["GEOCODING_API_KEY"] = settings.geocoding_api_key
    if settings.keycloak_enabled:
        required |= {
            "KEYCLOAK_ISSUER": settings.keycloak_issuer,
            "KEYCLOAK_AUDIENCE": settings.keycloak_audience,
        }
    if settings.odoo_enabled:
        required["DIRECT_ODOO_PROHIBITED_USE_MIDDLEWARE"] = ""
    if settings.middleware_enabled:
        required |= {
            "MIDDLEWARE_URL": settings.middleware_url,
            "MIDDLEWARE_CA_FILE": settings.middleware_ca_file,
            "MIDDLEWARE_CLIENT_CERT_FILE": settings.middleware_client_cert_file,
            "MIDDLEWARE_CLIENT_KEY_FILE": settings.middleware_client_key_file,
            "MIDDLEWARE_HMAC_KEY_ID": settings.middleware_hmac_key_id,
            "MIDDLEWARE_HMAC_SECRET_FILE": settings.middleware_hmac_secret_file,
            "MIDDLEWARE_SERVICE_IDENTITY": settings.middleware_service_identity,
            "MIDDLEWARE_AUDIENCE": settings.middleware_audience,
            "MIDDLEWARE_TENANT": settings.middleware_tenant,
            "MIDDLEWARE_SCOPE": settings.middleware_scope,
        }
    if settings.email_enabled:
        required |= {
            "SMTP_HOST": settings.smtp_host,
            "SMTP_USERNAME": settings.smtp_username,
            "SMTP_PASSWORD": settings.smtp_password,
            "SMTP_FROM_EMAIL": settings.smtp_from_email,
        }
    if settings.sms_enabled:
        required |= {
            "SMS_PROVIDER": settings.sms_provider,
            "SMS_API_KEY": settings.sms_api_key,
        }
    if settings.payout_enabled:
        required |= {
            "PAYOUT_PROVIDER": settings.payout_provider,
            "PAYOUT_API_KEY": settings.payout_api_key,
        }
    return required


def validate_environment(settings: Any) -> None:
    environment = settings.app_env.lower()
    if environment == "production":
        missing_bindings = [
            name
            for name in PRODUCTION_FILE_BINDINGS
            if not getattr(settings, f"{name}_file")
        ]
        if missing_bindings:
            raise ValueError(
                "production credentials require secret-file bindings: "
                + ", ".join(name.upper() for name in missing_bindings)
            )

    if environment not in {"production", "staging"}:
        return

    required = required_environment_values(settings)
    missing = [
        name
        for name, value in required.items()
        if not value or (value in INSECURE_DEFAULTS and name != "MIDDLEWARE_TENANT")
    ]
    if len(settings.jwt_secret) < 32 or len(settings.jwt_refresh_secret) < 32:
        missing.append("JWT secrets (minimum 32 characters)")
    if settings.jwt_secret == settings.jwt_refresh_secret:
        missing.append("distinct JWT access and refresh secrets")
    if "breero:breero@" in settings.database_url:
        missing.append("non-default DATABASE_URL credentials")
    if "*" in settings.allowed_origins:
        missing.append("explicit CORS_ORIGINS")
    if not settings.allowed_origins or all(
        "localhost" in origin for origin in settings.allowed_origins
    ):
        missing.append("production CORS_ORIGINS")
    if missing:
        raise ValueError(
            "unsafe production configuration: " + ", ".join(sorted(set(missing)))
        )
