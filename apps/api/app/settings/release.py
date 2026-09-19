from typing import Any


def disabled_release_flags(settings: Any) -> dict[str, bool]:
    """Return capability flags that must remain disabled for this release."""

    return {
        "AUTO_ASSIGN_PROVIDER": settings.auto_assign_provider,
        "AUTO_CONFIRM_BOOKING": settings.auto_confirm_booking,
        "LIVE_PROVIDER_DISPATCH": settings.live_provider_dispatch,
        "LIVE_SMS_DELIVERY": settings.live_sms_delivery,
        "LIVE_CALLBACKS": settings.live_callbacks,
        "ODOO_DELIVERY_ENABLED": settings.odoo_delivery_enabled,
        "ODOO_WRITE_ENABLED": settings.odoo_write_enabled,
        "PUBLIC_BOOKING_API_ENABLED": settings.public_booking_api_enabled,

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
    if settings.provider_assignment_mode not in {"MANUAL", "SUGGESTED", "AUTOMATIC"}:
        raise ValueError("PROVIDER_ASSIGNMENT_MODE must be MANUAL, SUGGESTED, or AUTOMATIC")
    if settings.provider_assignment_mode == "AUTOMATIC" and not settings.auto_assign_provider:
        raise ValueError("AUTOMATIC provider assignment mode requires AUTO_ASSIGN_PROVIDER")
    if settings.public_booking_api_enabled and not settings.geocoding_enabled:
        raise ValueError("PUBLIC_BOOKING_API_ENABLED requires GEOCODING_ENABLED")
    if settings.public_booking_api_enabled and not settings.scheduling_enabled:
        raise ValueError("PUBLIC_BOOKING_API_ENABLED requires SCHEDULING_ENABLED")
    if settings.transactional_email_mode not in {"disabled", "controlled_canary"}:
        raise ValueError(
            "TRANSACTIONAL_EMAIL_MODE must be disabled or controlled_canary"
        )
    if settings.transactional_sms_mode not in {"disabled", "controlled_canary"}:
        raise ValueError(
            "TRANSACTIONAL_SMS_MODE must be disabled or controlled_canary"
        )
