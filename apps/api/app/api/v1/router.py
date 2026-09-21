from fastapi import APIRouter

from app.api.v1 import (
    access,
    addresses,
    admin,
    admin_dispatch,
    admin_geography,
    admin_users,
    auth,
    availability,
    booking_geography,
    booking_intents,
    bookings,
    capabilities,
    compliance,
    customers,
    finance,
    integrations,
    jobs,
    operations,
    payments,
    provider,
    provider_catalog,
    provider_leads,
    provider_onboarding,
    public_booking,
    public_forms,
    services,
    vendors,
)
from app.config import settings

api_router = APIRouter()
api_router.include_router(capabilities.router, prefix="/public", tags=["public-capabilities"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(access.router, prefix="/auth/access", tags=["auth-access"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["admin-users"])
api_router.include_router(
    admin_geography.service_zones_router, prefix="/admin/service-zones", tags=["admin-service-zones"]
)
api_router.include_router(
    admin_geography.postal_codes_router, prefix="/admin/postal-codes", tags=["admin-postal-codes"]
)
api_router.include_router(
    provider_onboarding.provider_router, prefix="/provider", tags=["provider-onboarding"]
)
api_router.include_router(provider_catalog.router, prefix="/provider", tags=["provider-catalog"])
api_router.include_router(
    provider_onboarding.admin_router,
    prefix="/admin/provider-applications",
    tags=["admin-provider-applications"],
)
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(customers.router, prefix="/customer", tags=["customer"])
api_router.include_router(customers.router, prefix="/client", tags=["client"])
api_router.include_router(compliance.router, tags=["compliance"])
if settings.geocoding_enabled:
    api_router.include_router(addresses.router, prefix="/addresses", tags=["addresses"])
    api_router.include_router(booking_geography.router, prefix="/booking", tags=["booking-geography"])
if settings.scheduling_enabled:
    api_router.include_router(availability.router, prefix="/availability", tags=["availability"])
    api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
    api_router.include_router(booking_intents.router, prefix="/booking", tags=["booking-intents"])
if settings.public_booking_api_enabled:
    api_router.include_router(public_booking.router, prefix="/booking", tags=["public-booking"])
if settings.payments_enabled and settings.stripe_enabled:
    api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
    api_router.include_router(
        customers.payment_router, prefix="/customer", tags=["customer-payments"]
    )
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])
api_router.include_router(provider.router, prefix="/provider", tags=["provider"])
api_router.include_router(operations.router, prefix="/operations", tags=["operations"])
api_router.include_router(admin_dispatch.router, prefix="/admin", tags=["admin-dispatch"])
api_router.include_router(admin.router, prefix="/admin", tags=["administration"])
if settings.payout_enabled:
    api_router.include_router(finance.router, prefix="/finance", tags=["finance"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(public_forms.router, tags=["public-forms"])
if settings.paid_leads_enabled and settings.payments_enabled and settings.stripe_enabled:
    api_router.include_router(provider_leads.router, prefix="/provider/leads", tags=["provider-leads"])
