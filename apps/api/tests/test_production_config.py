import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_environment_credentials():
    with pytest.raises(ValidationError, match="secret-file bindings"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://breero:breero@postgres:5432/breero",
            redis_url="redis://redis:6379/0",
            jwt_secret="development-only-change-me",
            jwt_refresh_secret="development-only-change-me-too",
            cors_origins="http://localhost:3000",
        )


def test_liveness_has_no_dependency_calls():
    from app.main import live

    assert live.__name__ == "live"


def test_staging_allows_explicitly_disabled_optional_providers():
    settings = Settings(
        app_env="staging",
        database_url="postgresql+psycopg://staging:strong-password@postgres:5432/staging",
        redis_url="redis://:strong-password@redis:6379/0",
        jwt_secret="a" * 32,
        jwt_refresh_secret="b" * 32,
        cors_origins="https://staging.breero.com",
    )

    assert settings.stripe_enabled is False
    assert settings.geocoding_enabled is False
    assert settings.email_enabled is False


def test_staging_requires_credentials_for_enabled_provider():
    with pytest.raises(ValidationError, match="STRIPE_SECRET_KEY"):
        Settings(
            app_env="staging",
            database_url="postgresql+psycopg://staging:strong-password@postgres:5432/staging",
            redis_url="redis://:strong-password@redis:6379/0",
            jwt_secret="a" * 32,
            jwt_refresh_secret="b" * 32,
            cors_origins="https://staging.breero.com",
            stripe_enabled=True,
        )


def test_secret_file_bindings_are_resolved_without_environment_values(tmp_path, monkeypatch):
    for variable in ("DATABASE_URL", "REDIS_URL", "JWT_SECRET", "JWT_REFRESH_SECRET"):
        monkeypatch.delenv(variable, raising=False)
    database_url = tmp_path / "database-url"
    redis_url = tmp_path / "redis-url"
    jwt_secret = tmp_path / "jwt-secret"
    jwt_refresh_secret = tmp_path / "jwt-refresh-secret"
    stripe_secret = tmp_path / "stripe-secret"
    stripe_webhook = tmp_path / "stripe-webhook"
    stripe_publishable = tmp_path / "stripe-publishable"
    geoapify = tmp_path / "geoapify"
    database_url.write_text("postgresql+psycopg://prod:secret@postgres/prod", encoding="ascii")
    redis_url.write_text("redis://:secret@redis:6379/0", encoding="ascii")
    jwt_secret.write_text("a" * 32, encoding="ascii")
    jwt_refresh_secret.write_text("b" * 32, encoding="ascii")
    stripe_secret.write_text("sk_test_abcdefghijklmnopqrstuvwxyz", encoding="ascii")
    stripe_webhook.write_text("whsec_abcdefghijklmnopqrstuvwxyz", encoding="ascii")
    stripe_publishable.write_text("pk_test_abcdefghijklmnopqrstuvwxyz", encoding="ascii")
    geoapify.write_text("geoapify-key-material", encoding="ascii")

    for secret_path in tmp_path.iterdir():
        secret_path.chmod(0o400)

    settings = Settings(
        database_url_file=str(database_url),
        redis_url_file=str(redis_url),
        jwt_secret_file=str(jwt_secret),
        jwt_refresh_secret_file=str(jwt_refresh_secret),
        stripe_secret_key_file=str(stripe_secret),
        stripe_webhook_secret_file=str(stripe_webhook),
        stripe_publishable_key_file=str(stripe_publishable),
        geocoding_api_key_file=str(geoapify),
    )

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url.startswith("redis://")
    assert settings.jwt_secret == "a" * 32
    assert settings.jwt_refresh_secret == "b" * 32
    assert settings.stripe_secret_key.startswith("sk_test_")
    assert settings.stripe_webhook_secret.startswith("whsec_")
    assert settings.stripe_publishable_key.startswith("pk_test_")
    assert settings.geocoding_api_key == "geoapify-key-material"


def test_secret_file_binding_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing-secret"
    with pytest.raises(ValidationError, match="cannot read configured secret file"):
        Settings(database_url="", database_url_file=str(missing))


def test_secret_file_binding_rejects_empty_file(tmp_path):
    empty = tmp_path / "empty-secret"
    empty.write_text("", encoding="ascii")
    empty.chmod(0o400)
    with pytest.raises(ValidationError, match="configured secret file.*is empty"):
        Settings(redis_url="", redis_url_file=str(empty))


def test_secret_file_binding_rejects_inline_secret_too(tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("file-value", encoding="ascii")
    with pytest.raises(ValidationError, match="configure only one"):
        Settings(stripe_secret_key="inline-value", stripe_secret_key_file=str(secret))


def test_stripe_keys_cannot_mix_test_and_live_modes():
    with pytest.raises(ValidationError, match="same mode"):
        Settings(
            stripe_secret_key="sk_test_abcdefghijklmnopqrstuvwxyz",
            stripe_publishable_key="pk_live_abcdefghijklmnopqrstuvwxyz",
        )


@pytest.mark.parametrize(
    "flag",
    [
        "stripe_enabled",
        "payments_enabled",
        "online_checkout_enabled",
        "paid_leads_enabled",
        "automatic_refunds_enabled",
        "payout_enabled",
        "automatic_booking_enabled",
        "automatic_provider_assignment_enabled",
        "automatic_confirmed_bookings",
        "provider_self_service_enabled",
        "marketplace_matching_enabled",
        "marketplace_messaging_enabled",
        "marketplace_reviews_enabled",
        "marketing_email_enabled",
        "live_email_delivery",
        "marketing_sms_enabled",
    ],
)
def test_request_only_production_rejects_prohibited_capability_flags(flag):
    values = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://prod:strong-password@postgres:5432/prod",
        "redis_url": "redis://:strong-password@redis:6379/0",
        "jwt_secret": "a" * 32,
        "jwt_refresh_secret": "b" * 32,
        "cors_origins": "https://breero.com",
        flag: True,
    }
    with pytest.raises(ValidationError, match="request-service release"):
        Settings(**values)


@pytest.mark.parametrize("bad_value", ["prod", "Production", "live", "PRODUCTION ", ""])
def test_app_env_rejects_anything_outside_the_known_set(bad_value):
    # Regression test: app_env used to be a free string, and every production
    # safety check (default JWT secret, default DB credentials, wildcard CORS)
    # only fires when it's spelled exactly "production"/"staging" -- a typo or
    # unset value silently fell through to permissive development defaults with
    # no warning. It must now be rejected outright at startup instead.
    with pytest.raises(ValidationError):
        Settings(app_env=bad_value)


@pytest.mark.parametrize("good_value", ["development", "test"])
def test_app_env_accepts_the_known_set(good_value):
    assert Settings(app_env=good_value).app_env == good_value


def test_app_env_accepts_staging_with_secure_settings():
    settings = Settings(
        app_env="staging",
        database_url="postgresql+psycopg://staging:strong-password@postgres:5432/staging",
        redis_url="redis://:strong-password@redis:6379/0",
        jwt_secret="a" * 32,
        jwt_refresh_secret="b" * 32,
        cors_origins="https://staging.breero.com",
    )
    assert settings.app_env == "staging"


def test_app_env_accepts_production_with_secret_file_bindings(tmp_path, monkeypatch):
    for variable in ("DATABASE_URL", "REDIS_URL", "JWT_SECRET", "JWT_REFRESH_SECRET"):
        monkeypatch.delenv(variable, raising=False)
    database_url = tmp_path / "database-url"
    redis_url = tmp_path / "redis-url"
    jwt_secret = tmp_path / "jwt-secret"
    jwt_refresh_secret = tmp_path / "jwt-refresh-secret"
    database_url.write_text("postgresql+psycopg://prod:strong-password@postgres/prod", encoding="ascii")
    redis_url.write_text("redis://:strong-password@redis:6379/0", encoding="ascii")
    jwt_secret.write_text("a" * 32, encoding="ascii")
    jwt_refresh_secret.write_text("b" * 32, encoding="ascii")

    for path in (database_url, redis_url, jwt_secret, jwt_refresh_secret):
        path.chmod(0o400)

    settings = Settings(
        app_env="production",
        database_url_file=str(database_url),
        redis_url_file=str(redis_url),
        jwt_secret_file=str(jwt_secret),
        jwt_refresh_secret_file=str(jwt_refresh_secret),
        cors_origins="https://breero.com",
    )
    assert settings.app_env == "production"


def test_staging_allows_canonical_breero_middleware_tenant():
    settings = Settings(
        app_env="staging",
        database_url="postgresql+psycopg://staging:strong-password@postgres:5432/staging",
        redis_url="redis://:strong-password@redis:6379/0",
        jwt_secret="a" * 32,
        jwt_refresh_secret="b" * 32,
        cors_origins="https://staging.breero.com",
        middleware_enabled=True,
        middleware_url="https://middleware.internal.codestra.agency",
        middleware_ca_file="/run/secrets/codestra_private_ca.pem",
        middleware_client_cert_file="/run/secrets/breero_middleware_client.pem",
        middleware_client_key_file="/run/secrets/breero_middleware_client.key",
        middleware_hmac_key_id="breero-staging-key-v1",
        middleware_hmac_secret_file="/run/secrets/breero_middleware_hmac",
        middleware_service_identity="breero-staging",
        middleware_audience="codestra-middleware-breero",
        middleware_tenant="breero",
        middleware_scope="breero.crm.events.submit",
    )

    assert settings.middleware_tenant == "breero"


def test_app_env_must_be_explicit_when_environment_and_dotenv_omit_it(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert any(detail["loc"] == ("app_env",) and detail["type"] == "missing"
               for detail in error.value.errors())
