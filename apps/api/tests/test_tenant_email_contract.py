import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.domains.tenant_email.delivery import EmailDeliveryConfigurationError, FileSecretResolver
from app.domains.tenant_email.schemas import EmailCredentialCreate
from app.domains.tenant_email.service import TenantEmailService


def test_smtp_credential_requires_complete_transport() -> None:
    with pytest.raises(ValidationError, match="smtp credentials require smtp_host and smtp_port"):
        EmailCredentialCreate(
            provider="smtp",
            label="Incomplete SMTP",
            secret_ref="breero-email/brand/breero/smtp/main",
            smtp_port=587,
        )


def test_email_secret_reference_rejects_secret_root_escape() -> None:
    resolver = FileSecretResolver()
    with pytest.raises(EmailDeliveryConfigurationError, match="escapes secret root"):
        resolver.resolve("breero-email/../../outside-secret")


def test_email_secret_reference_namespace_is_required() -> None:
    resolver = FileSecretResolver()
    with pytest.raises(EmailDeliveryConfigurationError, match="Unsupported email secret reference"):
        resolver.resolve("other-service/smtp/main")


def test_credential_secret_ref_rejects_traversal_within_own_namespace() -> None:
    # Regression test: "starts with the tenant prefix" is not enough -- a reference
    # like "<prefix>/../../../database-secret" starts with the prefix, and would
    # still resolve under /run/secrets, just as an unrelated file.
    expected_prefix = "breero-email/vendor/11111111-1111-1111-1111-111111111111/"
    with pytest.raises(HTTPException) as exc_info:
        TenantEmailService.validate_secret_ref(
            expected_prefix + "../../../database-secret", expected_prefix
        )
    assert exc_info.value.status_code == 400
    assert "'..'" in exc_info.value.detail


def test_credential_secret_ref_rejects_sibling_tenant_after_normalization() -> None:
    # A single ".." can step sideways into a sibling tenant's namespace without ever
    # leaving the shared secret root, so the check must run on the normalized path.
    expected_prefix = "breero-email/vendor/11111111-1111-1111-1111-111111111111/"
    other_tenant_ref = "breero-email/vendor/11111111-1111-1111-1111-111111111111/../22222222-2222-2222-2222-222222222222/smtp"
    with pytest.raises(HTTPException) as exc_info:
        TenantEmailService.validate_secret_ref(other_tenant_ref, expected_prefix)
    assert exc_info.value.status_code == 400


def test_credential_secret_ref_accepts_well_formed_reference() -> None:
    expected_prefix = "breero-email/vendor/11111111-1111-1111-1111-111111111111/"
    ref = expected_prefix + "smtp/primary"
    assert TenantEmailService.validate_secret_ref(ref, expected_prefix) == ref
