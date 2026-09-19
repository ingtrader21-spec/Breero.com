import pytest

from app.api.v1.public_forms import validate_channel_contract
from app.core.errors import DomainError
from app.domains.public_submissions.consent import DEFAULT_CONSENT_POLICY_VERSION
from app.domains.public_submissions.schemas import ContactCreate, ServiceRequestCreate


def test_sms_consent_requires_a_phone_number() -> None:
    contact = ContactCreate(
        name="SMS consent customer",
        email="sms-consent@example.com",
        category="general",
        subject="SMS consent",
        message="This contact intentionally omits a phone number.",
        source_url="https://breero.com/contact",
        transactional_contact_allowed=True,
        transactional_sms_consent=True,
        policy_version=DEFAULT_CONSENT_POLICY_VERSION,
    )

    with pytest.raises(DomainError) as exc_info:
        validate_channel_contract(contact)

    assert exc_info.value.code == "PHONE_REQUIRED_FOR_SMS_CONSENT"
    assert exc_info.value.status_code == 422


def test_text_preference_requires_transactional_sms_consent() -> None:
    request = ServiceRequestCreate(
        name="Text preference customer",
        email="text-preference@example.com",
        phone="+1 281 555 0199",
        service_slug="plumbing",
        service_description="A request that asks to be contacted by text.",
        address_line1="1 Main Street",
        city="Houston",
        state="TX",
        postal_code="77002",
        contact_preference="text",
        source_url="https://breero.com/request-service",
        transactional_contact_allowed=True,
        policy_version=DEFAULT_CONSENT_POLICY_VERSION,
    )

    with pytest.raises(DomainError) as exc_info:
        validate_channel_contract(request)

    assert exc_info.value.code == "SMS_CONSENT_REQUIRED"
    assert exc_info.value.status_code == 422


def test_text_preference_with_sms_consent_is_valid() -> None:
    request = ServiceRequestCreate(
        name="Text preference customer",
        email="text-preference-valid@example.com",
        phone="+1 281 555 0199",
        service_slug="plumbing",
        service_description="A request with explicit transactional SMS consent.",
        address_line1="1 Main Street",
        city="Houston",
        state="TX",
        postal_code="77002",
        contact_preference="text",
        source_url="https://breero.com/request-service",
        transactional_contact_allowed=True,
        transactional_sms_consent=True,
        policy_version=DEFAULT_CONSENT_POLICY_VERSION,
    )

    validate_channel_contract(request)
