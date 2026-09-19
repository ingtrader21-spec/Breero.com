import pytest
from pydantic import ValidationError

from app.domains.public_submissions.consent import (
    DEFAULT_CONSENT_POLICY_VERSION,
    canonical_disclosures,
)
from app.domains.public_submissions.schemas import ContactCreate

BASE_CONTACT = {
    "name": "Consent Customer",
    "email": "consent@example.com",
    "category": "general",
    "subject": "Consent question",
    "message": "This is a valid consent-contract test message.",
    "source_url": "https://breero.com/contact",
    "transactional_contact_allowed": True,
    "policy_version": DEFAULT_CONSENT_POLICY_VERSION,
}


def test_required_contact_permission_requires_policy_version() -> None:
    payload = dict(BASE_CONTACT)
    payload.pop("policy_version")

    with pytest.raises(ValidationError, match="policy version"):
        ContactCreate(**payload)


def test_consent_rejects_unknown_policy_version() -> None:
    with pytest.raises(ValidationError, match="not supported"):
        ContactCreate(**{**BASE_CONTACT, "policy_version": "unknown-policy"})


def test_channel_specific_consent_accepts_supported_version_without_trusting_client_text() -> None:
    contact = ContactCreate(
        **BASE_CONTACT,
        transactional_email_consent=True,
        transactional_sms_consent=True,
        marketing_email_consent=True,
        marketing_sms_consent=True,
        consent_disclosures={
            "transactional_sms": "Client-supplied evidence retained separately by the service."
        },
    )

    disclosures = canonical_disclosures(
        {
            "transactional_contact_allowed": contact.transactional_contact_allowed,
            "transactional_email_consent": contact.transactional_email_consent,
            "transactional_sms_consent": contact.transactional_sms_consent,
            "marketing_email_consent": contact.marketing_email_consent,
            "marketing_sms_consent": contact.marketing_sms_consent,
        },
        contact.policy_version or "",
    )

    assert set(disclosures) == {
        "transactional_contact",
        "transactional_email",
        "transactional_sms",
        "marketing_email",
        "marketing_sms",
    }
    assert disclosures["transactional_contact"].startswith(
        "I agree that BREERO may contact me"
    )
    assert disclosures["transactional_sms"].startswith(
        "I agree to receive recurring automated appointment"
    )
    assert disclosures["transactional_sms"] != contact.consent_disclosures["transactional_sms"]


def test_legacy_aggregate_consent_flags_are_rejected() -> None:
    for flag in ("email_consent", "sms_consent", "marketing_consent"):
        with pytest.raises(ValidationError, match="Legacy aggregate consent"):
            ContactCreate(**BASE_CONTACT, **{flag: True})


def test_no_optional_channel_consent_does_not_require_client_disclosures() -> None:
    contact = ContactCreate(**BASE_CONTACT)

    assert contact.consent_disclosures == {}
    assert contact.transactional_email_consent is False
    assert contact.transactional_sms_consent is False


def test_canonical_disclosure_registry_rejects_unknown_versions() -> None:
    with pytest.raises(ValueError, match="Unsupported consent policy"):
        canonical_disclosures({}, "unknown-policy")


def test_padded_policy_version_is_rejected_before_persistence() -> None:
    payload = {**BASE_CONTACT, "policy_version": " " + DEFAULT_CONSENT_POLICY_VERSION}
    with pytest.raises(ValidationError, match="not supported"):
        ContactCreate(**payload)
