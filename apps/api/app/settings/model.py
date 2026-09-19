from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.settings.environment import validate_environment
from app.settings.release import validate_release_boundary
from app.settings.secrets import resolve_secret_files, validate_stripe_credentials


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
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @model_validator(mode="after")
    def validate_runtime(self) -> "Settings":
        if self.odoo_enabled or self.odoo_api_key or self.odoo_api_key_file:
            raise ValueError("Direct Odoo credentials and delivery are prohibited; use Middleware")
        resolve_secret_files(self)
        validate_stripe_credentials(self)
        validate_release_boundary(self)
        validate_environment(self)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
