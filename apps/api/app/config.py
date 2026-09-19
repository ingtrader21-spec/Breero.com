from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .secret_files import apply_secret_files


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    # Require an explicit environment so typos or omission cannot skip release checks.
    app_env: Literal["development", "test", "staging", "production"]
    app_name: str = "BREERO API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(
        default="postgresql+psycopg://breero:breero@postgres:5432/breero", repr=False
    )
    database_url_file: str = ""
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=5, ge=0, le=100)
    database_pool_timeout_seconds: float = Field(default=5.0, gt=0, le=120)
    database_pool_recycle_seconds: int = Field(default=300, ge=30, le=86_400)
    redis_url: str = Field(default="redis://redis:6379/0", repr=False)
    redis_url_file: str = ""
    redis_max_connections: int = Field(default=64, ge=4, le=1_000)
    redis_socket_connect_timeout_seconds: float = Field(default=1.0, gt=0, le=30)
    redis_socket_timeout_seconds: float = Field(default=1.0, gt=0, le=30)
    jwt_secret: str = Field(default="development-only-change-me", repr=False)
    jwt_secret_file: str = ""
    jwt_refresh_secret: str = Field(default="development-only-change-me-too", repr=False)
    jwt_refresh_secret_file: str = ""
    jwt_algorithm: str = "HS256"
    keycloak_enabled: bool = False
    keycloak_issuer: str = ""
    keycloak_audience: str = "breero-api-production"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    stripe_secret_key: str = Field(default="", repr=False)
    stripe_secret_key_file: str = ""
    stripe_webhook_secret: str = Field(default="", repr=False)
    stripe_webhook_secret_file: str = ""
    stripe_publishable_key: str = Field(default="", repr=False)
    stripe_publishable_key_file: str = ""
    stripe_enabled: bool = False
    payments_enabled: bool = False
    online_checkout_enabled: bool = False
    paid_leads_enabled: bool = False
    automatic_refunds_enabled: bool = False
    automatic_booking_enabled: bool = False
    scheduling_enabled: bool = True
    automatic_provider_assignment_enabled: bool = False
    automatic_confirmed_bookings: bool = False
    provider_self_service_enabled: bool = False
    marketplace_matching_enabled: bool = False
    marketplace_messaging_enabled: bool = False
    marketplace_reviews_enabled: bool = False
    transactional_email_mode: str = "controlled_canary"
    transactional_sms_mode: str = "controlled_canary"
    marketing_email_enabled: bool = False
    marketing_sms_enabled: bool = False
    geocoding_api_key: str = Field(default="", repr=False)
    geocoding_api_key_file: str = ""
    geocoding_provider: str = "geoapify"
    geocoding_enabled: bool = False
    odoo_url: str = ""
    odoo_database: str = ""
    odoo_username: str = ""
    odoo_api_key: str = Field(default="", repr=False)
    # Retained only to reject legacy direct-Odoo configuration without reading it.
    odoo_api_key_file: str = ""
    odoo_enabled: bool = False
    middleware_enabled: bool = False
    middleware_url: str = ""
    middleware_ca_file: str = ""
    middleware_client_cert_file: str = ""
    middleware_client_key_file: str = ""
    middleware_hmac_key_id: str = ""
    middleware_hmac_secret_file: str = ""
    middleware_service_identity: str = ""
    middleware_audience: str = ""
    middleware_tenant: str = ""
    middleware_scope: str = "breero.crm.events.submit"
    payout_api_key: str = Field(default="", repr=False)
    payout_api_key_file: str = ""
    metrics_enabled: bool = True
    payout_provider: str = ""
    payout_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_password_file: str = ""
    smtp_from_email: str = ""
    email_enabled: bool = False
    live_email_delivery: bool = False
    sms_provider: str = ""
    sms_api_key: str = Field(default="", repr=False)
    sms_api_key_file: str = ""
    sms_enabled: bool = False
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003"
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.odoo_enabled or self.odoo_api_key or self.odoo_api_key_file:
            raise ValueError("Direct Odoo credentials and delivery are prohibited; use Middleware")

        apply_secret_files(
            self,
            (
                "database_url",
                "redis_url",
                "jwt_secret",
                "jwt_refresh_secret",
                "stripe_secret_key",
                "stripe_webhook_secret",
                "stripe_publishable_key",
                "geocoding_api_key",
                "payout_api_key",
                "smtp_password",
                "sms_api_key",
            ),
        )

        stripe_secret_mode = next(
            (mode for mode in ("test", "live") if self.stripe_secret_key.startswith(f"sk_{mode}_")),
            None,
        )
        stripe_publishable_mode = next(
            (
                mode
                for mode in ("test", "live")
                if self.stripe_publishable_key.startswith(f"pk_{mode}_")
            ),
            None,
        )
        if self.stripe_secret_key and stripe_secret_mode is None:
            raise ValueError("STRIPE_SECRET_KEY has an unsupported format")
        if self.stripe_publishable_key and stripe_publishable_mode is None:
            raise ValueError("STRIPE_PUBLISHABLE_KEY has an unsupported format")
        if (
            stripe_secret_mode
            and stripe_publishable_mode
            and stripe_secret_mode != stripe_publishable_mode
        ):
            raise ValueError("Stripe secret and publishable keys must use the same mode")
        if self.stripe_webhook_secret and not self.stripe_webhook_secret.startswith("whsec_"):
            raise ValueError("STRIPE_WEBHOOK_SECRET has an unsupported format")

        release_payment_flags = {
            "STRIPE_ENABLED": self.stripe_enabled,
            "PAYMENTS_ENABLED": self.payments_enabled,
            "ONLINE_CHECKOUT_ENABLED": self.online_checkout_enabled,
            "PAID_LEADS_ENABLED": self.paid_leads_enabled,
            "AUTOMATIC_REFUNDS_ENABLED": self.automatic_refunds_enabled,
            "PAYOUT_ENABLED": self.payout_enabled,
            "AUTOMATIC_BOOKING_ENABLED": self.automatic_booking_enabled,
            "AUTOMATIC_PROVIDER_ASSIGNMENT_ENABLED": self.automatic_provider_assignment_enabled,
            "AUTOMATIC_CONFIRMED_BOOKINGS": self.automatic_confirmed_bookings,
            "PROVIDER_SELF_SERVICE_ENABLED": self.provider_self_service_enabled,
            "MARKETPLACE_MATCHING_ENABLED": self.marketplace_matching_enabled,
            "MARKETPLACE_MESSAGING_ENABLED": self.marketplace_messaging_enabled,
            "MARKETPLACE_REVIEWS_ENABLED": self.marketplace_reviews_enabled,
            "MARKETING_EMAIL_ENABLED": self.marketing_email_enabled,
            "LIVE_EMAIL_DELIVERY": self.live_email_delivery,
            "MARKETING_SMS_ENABLED": self.marketing_sms_enabled,
        }
        enabled_release_flags = [name for name, enabled in release_payment_flags.items() if enabled]
        if self.app_env.lower() == "production" and enabled_release_flags:
            raise ValueError(
                "request-service release requires disabled flags: "
                + ", ".join(enabled_release_flags)
            )
        if self.app_env.lower() == "production" and not self.scheduling_enabled:
            raise ValueError("SCHEDULING_ENABLED must remain enabled for this release")
        if self.transactional_email_mode not in {"disabled", "controlled_canary"}:
            raise ValueError("TRANSACTIONAL_EMAIL_MODE must be disabled or controlled_canary")
        if self.transactional_sms_mode not in {"disabled", "controlled_canary"}:
            raise ValueError("TRANSACTIONAL_SMS_MODE must be disabled or controlled_canary")

        if self.app_env.lower() == "production":
            missing_file_bindings = [
                name
                for name in ("database_url", "redis_url", "jwt_secret", "jwt_refresh_secret")
                if not getattr(self, f"{name}_file")
            ]
            if missing_file_bindings:
                raise ValueError(
                    "production credentials require secret-file bindings: "
                    + ", ".join(name.upper() for name in missing_file_bindings)
                )

        if self.app_env.lower() not in {"production", "staging"}:
            return self
        required = {
            "DATABASE_URL": self.database_url,
            "REDIS_URL": self.redis_url,
            "JWT_SECRET": self.jwt_secret,
            "JWT_REFRESH_SECRET": self.jwt_refresh_secret,
        }
        if self.stripe_enabled:
            required |= {
                "STRIPE_SECRET_KEY": self.stripe_secret_key,
                "STRIPE_WEBHOOK_SECRET": self.stripe_webhook_secret,
                "STRIPE_PUBLISHABLE_KEY": self.stripe_publishable_key,
            }
        if self.geocoding_enabled:
            required["GEOCODING_API_KEY"] = self.geocoding_api_key
        if self.keycloak_enabled:
            required |= {
                "KEYCLOAK_ISSUER": self.keycloak_issuer,
                "KEYCLOAK_AUDIENCE": self.keycloak_audience,
            }
        if self.odoo_enabled:
            required["DIRECT_ODOO_PROHIBITED_USE_MIDDLEWARE"] = ""
        if self.middleware_enabled:
            required |= {
                "MIDDLEWARE_URL": self.middleware_url,
                "MIDDLEWARE_CA_FILE": self.middleware_ca_file,
                "MIDDLEWARE_CLIENT_CERT_FILE": self.middleware_client_cert_file,
                "MIDDLEWARE_CLIENT_KEY_FILE": self.middleware_client_key_file,
                "MIDDLEWARE_HMAC_KEY_ID": self.middleware_hmac_key_id,
                "MIDDLEWARE_HMAC_SECRET_FILE": self.middleware_hmac_secret_file,
                "MIDDLEWARE_SERVICE_IDENTITY": self.middleware_service_identity,
                "MIDDLEWARE_AUDIENCE": self.middleware_audience,
                "MIDDLEWARE_TENANT": self.middleware_tenant,
                "MIDDLEWARE_SCOPE": self.middleware_scope,
            }
        if self.email_enabled:
            required |= {
                "SMTP_HOST": self.smtp_host,
                "SMTP_USERNAME": self.smtp_username,
                "SMTP_PASSWORD": self.smtp_password,
                "SMTP_FROM_EMAIL": self.smtp_from_email,
            }
        if self.sms_enabled:
            required |= {"SMS_PROVIDER": self.sms_provider, "SMS_API_KEY": self.sms_api_key}
        if self.payout_enabled:
            required |= {
                "PAYOUT_PROVIDER": self.payout_provider,
                "PAYOUT_API_KEY": self.payout_api_key,
            }
        insecure = {
            "development-only-change-me",
            "development-only-change-me-too",
            "change-me",
            "change-me-too",
            "breero",
        }
        # ``breero`` is the canonical middleware tenant identifier, not a
        # credential. Keep rejecting it as a development/default value for
        # secrets and connection settings, while allowing the explicitly
        # named tenant field required by the signed middleware contract.
        missing = [
            name
            for name, value in required.items()
            if not value or (value in insecure and name != "MIDDLEWARE_TENANT")
        ]
        if len(self.jwt_secret) < 32 or len(self.jwt_refresh_secret) < 32:
            missing.append("JWT secrets (minimum 32 characters)")
        if self.jwt_secret == self.jwt_refresh_secret:
            missing.append("distinct JWT access and refresh secrets")
        if "breero:breero@" in self.database_url:
            missing.append("non-default DATABASE_URL credentials")
        if "*" in self.allowed_origins:
            missing.append("explicit CORS_ORIGINS")
        if not self.allowed_origins or all(
            "localhost" in origin for origin in self.allowed_origins
        ):
            missing.append("production CORS_ORIGINS")
        if missing:
            raise ValueError("unsafe production configuration: " + ", ".join(sorted(set(missing))))
        return self


@lru_cache
def get_settings() -> Settings:
    # app_env has no Python-level default by design (see the field comment above) --
    # pydantic-settings still supplies it from the environment/.env file at runtime,
    # but mypy's call-arg check doesn't know that, hence the ignore.
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
