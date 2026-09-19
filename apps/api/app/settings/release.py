from typing import Any


def disabled_release_flags(settings: Any) -> dict[str, bool]:
    """Return capability flags that must remain disabled for this release."""

    return {
        "STRIPE_ENABLED": settings.stripe_enabled,
        "PAYMENTS_ENABLED": settings.payments_enabled,
        "ONLINE_CHECKOUT_ENABLED": settings.online_checkout_enabled,
        "PAID_LEADS_ENABLED": settings.paid_leads_enabled,
        "AUTOMATIC_REFUNDS_ENABLED": settings.automatic_refunds_enabled,
        "PAYOUT_ENABLED": settings.payout_enabled,
        "AUTOMATIC_BOOKING_ENABLED": settings.automatic_booking_enabled,
        "AUTOMATIC_PROVIDER_ASSIGNMENT_ENABLED": (
            settings.automatic_provider_assignment_enabled
        ),
        "AUTOMATIC_CONFIRMED_BOOKINGS": settings.automatic_confirmed_bookings,
        "PROVIDER_SELF_SERVICE_ENABLED": settings.provider_self_service_enabled,
        "MARKETPLACE_MATCHING_ENABLED": settings.marketplace_matching_enabled,
        "MARKETPLACE_MESSAGING_ENABLED": settings.marketplace_messaging_enabled,
        "MARKETPLACE_REVIEWS_ENABLED": settings.marketplace_reviews_enabled,
        "MARKETING_EMAIL_ENABLED": settings.marketing_email_enabled,
        "LIVE_EMAIL_DELIVERY": settings.live_email_delivery,
        "MARKETING_SMS_ENABLED": settings.marketing_sms_enabled,
    }


def validate_release_boundary(settings: Any) -> None:
    enabled = [
        name for name, value in disabled_release_flags(settings).items() if value
    ]
    if settings.app_env.lower() == "production" and enabled:
        raise ValueError(
            "request-service release requires disabled flags: " + ", ".join(enabled)
        )
    if settings.app_env.lower() == "production" and not settings.scheduling_enabled:
        raise ValueError("SCHEDULING_ENABLED must remain enabled for this release")
    if settings.transactional_email_mode not in {"disabled", "controlled_canary"}:
        raise ValueError(
            "TRANSACTIONAL_EMAIL_MODE must be disabled or controlled_canary"
        )
    if settings.transactional_sms_mode not in {"disabled", "controlled_canary"}:
        raise ValueError(
            "TRANSACTIONAL_SMS_MODE must be disabled or controlled_canary"
        )
