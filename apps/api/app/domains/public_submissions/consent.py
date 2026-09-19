from collections.abc import Mapping

DEFAULT_CONSENT_POLICY_VERSION = "2026-08-13-request-only"

CONSENT_FLAGS = {
    "transactional_contact_allowed": "transactional_contact",
    "transactional_email_consent": "transactional_email",
    "transactional_sms_consent": "transactional_sms",
    "marketing_email_consent": "marketing_email",
    "marketing_sms_consent": "marketing_sms",
}

CONSENT_DISCLOSURES_BY_POLICY: dict[str, dict[str, str]] = {
    DEFAULT_CONSENT_POLICY_VERSION: {
        "transactional_contact": (
            "I agree that BREERO may contact me about this request. "
            "I understand this is not a confirmed appointment."
        ),
        "transactional_email": (
            "I agree to receive appointment and service-status email from BREERO."
        ),
        "transactional_sms": (
            "I agree to receive recurring automated appointment and service-status text "
            "messages from BREERO at the number provided. Message frequency varies. "
            "Message and data rates may apply. Reply STOP to opt out or HELP for help. "
            "Consent is not a condition of purchase."
        ),
        "marketing_email": (
            "I separately agree to marketing email. Marketing email is currently disabled."
        ),
        "marketing_sms": (
            "I agree to receive recurring automated promotional and marketing text "
            "messages from BREERO at the number provided. Message frequency varies. "
            "Message and data rates may apply. Reply STOP to opt out or HELP for help. "
            "Consent is not a condition of purchase. Marketing SMS is currently disabled."
        ),
    }
}


def canonical_disclosures(
    consent_flags: Mapping[str, bool],
    policy_version: str,
) -> dict[str, str]:
    policy = CONSENT_DISCLOSURES_BY_POLICY.get(policy_version)
    if policy is None:
        raise ValueError(f"Unsupported consent policy version: {policy_version}")
    return {
        disclosure_key: policy[disclosure_key]
        for flag, disclosure_key in CONSENT_FLAGS.items()
        if consent_flags.get(flag, False)
    }
