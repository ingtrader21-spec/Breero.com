"""Canonical runtime endpoint ownership and policy registry.

The registry is deliberately generated from the routes that FastAPI actually
mounts. A route cannot silently appear without matching exactly one explicit
policy rule.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any, Final, cast

from fastapi import FastAPI
from fastapi import routing as fastapi_routing
from fastapi.routing import APIRoute

from app.observability import observability_settings

OPENAPI_METHODS: Final[frozenset[str]] = frozenset(
    {"GET", "PUT", "POST", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"}
)
SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})
DOCUMENTATION_PATHS: Final[frozenset[str]] = frozenset(
    {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
)
PATH_PARAMETER_RE: Final[re.Pattern[str]] = re.compile(r"\{[^{}]+\}")


def _route_shape(path: str) -> str:
    """Normalize parameter names so dispatch-equivalent routes share one shape."""

    return PATH_PARAMETER_RE.sub("{param}", path)



@dataclass(frozen=True, slots=True)
class EndpointPolicyRule:
    """Policy shared by one explicit route family."""

    name: str
    path_pattern: str
    methods: frozenset[str]
    resource_owner: str
    audience: str
    authentication: str
    permission: str
    tenant_scope: str
    record_policy: str
    capability_gate: str
    write_idempotency_key_policy: str = "legacy-not-enforced"
    write_request_hash_policy: str = "legacy-not-enforced"
    write_if_match_version_policy: str = "legacy-not-enforced"
    emitted_effect: str = "route-defined"
    deprecation_status: str = "active"
    rate_limit_class: str = "standard"
    pii_classification: str = "internal"


@dataclass(frozen=True, slots=True)
class EndpointPolicy:
    """Fully expanded policy for one runtime method and path."""

    method: str
    path: str
    operation_id: str
    policy_rule: str
    resource_owner: str
    audience: str
    authentication: str
    permission: str
    tenant_scope: str
    record_policy: str
    capability_gate: str
    idempotency_key_policy: str
    request_hash_policy: str
    if_match_version_policy: str
    request_schema: str
    response_schema: str
    emitted_effect: str
    deprecation_status: str
    rate_limit_class: str
    pii_classification: str


def _methods(*methods: str) -> frozenset[str]:
    return frozenset(method.upper() for method in methods)


def _rule(
    name: str,
    path_pattern: str,
    *,
    methods: frozenset[str] = OPENAPI_METHODS,
    resource_owner: str,
    audience: str,
    authentication: str,
    permission: str,
    tenant_scope: str,
    record_policy: str,
    capability_gate: str,
    write_idempotency_key_policy: str = "legacy-not-enforced",
    write_request_hash_policy: str = "legacy-not-enforced",
    write_if_match_version_policy: str = "legacy-not-enforced",
    emitted_effect: str = "route-defined",
    rate_limit_class: str = "standard",
    pii_classification: str = "internal",
) -> EndpointPolicyRule:
    return EndpointPolicyRule(
        name=name,
        path_pattern=path_pattern,
        methods=methods,
        resource_owner=resource_owner,
        audience=audience,
        authentication=authentication,
        permission=permission,
        tenant_scope=tenant_scope,
        record_policy=record_policy,
        capability_gate=capability_gate,
        write_idempotency_key_policy=write_idempotency_key_policy,
        write_request_hash_policy=write_request_hash_policy,
        write_if_match_version_policy=write_if_match_version_policy,
        emitted_effect=emitted_effect,
        rate_limit_class=rate_limit_class,
        pii_classification=pii_classification,
    )


POLICY_RULES: Final[tuple[EndpointPolicyRule, ...]] = (
    _rule(
        'metrics',
        re.escape(observability_settings.metrics_path),
        methods=_methods('GET'),
        resource_owner='platform-runtime',
        audience='operations',
        authentication='network-policy',
        permission='metrics.read',
        tenant_scope='global',
        record_policy='aggregated-runtime-metrics',
        capability_gate='settings.metrics_enabled',
    ),
    _rule(
        'analytics-marketplace-metrics',
        r'/api/v1/analytics/marketplace/metrics',
        methods=_methods('GET'),
        resource_owner='analytics',
        audience='internal',
        authentication='bearer',
        permission='analytics.marketplace.read',
        tenant_scope='internal-global-or-brand-assignment-without-vendor-scope',
        record_policy='aggregated-read-only-projection',
        capability_gate='always',
        emitted_effect='none',
        pii_classification='aggregated-no-pii',
    ),
    _rule(
        'analytics-provider-metrics',
        r'/api/v1/analytics/provider/metrics',
        methods=_methods('GET'),
        resource_owner='analytics',
        audience='provider',
        authentication='bearer',
        permission='analytics.provider.read',
        tenant_scope='provider-membership',
        record_policy='aggregated-read-only-projection-current-provider',
        capability_gate='always',
        emitted_effect='none',
        pii_classification='aggregated-no-pii',
    ),
    _rule(
        'login-mode',
        r'/api/v1/auth/login-mode',
        methods=_methods('GET'),
        resource_owner='identity',
        audience='public',
        authentication='none',
        permission='identity.login-mode.read',
        tenant_scope='global',
        record_policy='public-login-configuration',
        capability_gate='always',
    ),
    _rule(
        'provider-registration',
        r'/api/v1/auth/register/provider',
        methods=_methods('POST'),
        resource_owner='provider-onboarding',
        audience='public',
        authentication='registration-credentials',
        permission='provider.register',
        tenant_scope='identity',
        record_policy='new-provider-application',
        capability_gate='settings.provider_self_service_enabled && !settings.keycloak_enabled',
    ),
    _rule(
        'access-administration',
        r'/api/v1/auth/access/(?:catalog|users/\{user_id\})',
        methods=_methods('GET','PUT'),
        resource_owner='identity',
        audience='admin',
        authentication='bearer',
        permission='admin.access.manage',
        tenant_scope='route-defined-current-scope',
        record_policy='authorized-access-administrator',
        capability_gate='always',
    ),
    _rule(
        'internal-user-provisioning',
        r'/api/v1/admin/users',
        methods=_methods('POST'),
        resource_owner='identity',
        audience='admin',
        authentication='bearer',
        permission='admin.access.manage',
        tenant_scope='route-defined-current-scope',
        record_policy='authorized-access-administrator',
        capability_gate='always',
    ),
    _rule(
        'provider-profile-read-GET',
        r'/api/v1/provider/(?:profile|onboarding(?:/submit)?)',
        methods=_methods('GET'),
        resource_owner='provider-onboarding',
        audience='provider',
        authentication='bearer',
        permission='provider.profile.read',
        tenant_scope='provider-membership',
        record_policy='current-provider-profile',
        capability_gate='always',
    ),
    _rule(
        'provider-profile-write-PATCH',
        r'/api/v1/provider/(?:profile|onboarding(?:/submit)?)',
        methods=_methods('PATCH'),
        resource_owner='provider-onboarding',
        audience='provider',
        authentication='bearer',
        permission='provider.profile.write',
        tenant_scope='provider-membership',
        record_policy='current-provider-profile',
        capability_gate='always',
    ),
    _rule(
        'provider-profile-write-POST',
        r'/api/v1/provider/(?:profile|onboarding(?:/submit)?)',
        methods=_methods('POST'),
        resource_owner='provider-onboarding',
        audience='provider',
        authentication='bearer',
        permission='provider.profile.write',
        tenant_scope='provider-membership',
        record_policy='current-provider-profile',
        capability_gate='always',
    ),
    _rule(
        'provider-services-read',
        r'/api/v1/provider/services(?:/\{provider_service_id\})?',
        methods=_methods('GET'),
        resource_owner='provider-catalog',
        audience='provider',
        authentication='bearer',
        permission='provider.services.read',
        tenant_scope='provider-membership',
        record_policy='current-provider-record',
        capability_gate='always',
        write_if_match_version_policy='required-on-update-and-delete',
    ),
    _rule(
        'provider-services-manage',
        r'/api/v1/provider/services(?:/\{provider_service_id\})?',
        methods=_methods('POST','PATCH','DELETE'),
        resource_owner='provider-catalog',
        audience='provider',
        authentication='bearer',
        permission='provider.services.manage',
        tenant_scope='provider-membership',
        record_policy='current-provider-record',
        capability_gate='always',
        write_if_match_version_policy='required-on-update-and-delete',
    ),
    _rule(
        'provider-skills-read',
        r'/api/v1/provider/skills(?:/\{provider_skill_id\})?',
        methods=_methods('GET'),
        resource_owner='provider-catalog',
        audience='provider',
        authentication='bearer',
        permission='provider.skills.read',
        tenant_scope='provider-membership',
        record_policy='current-provider-record',
        capability_gate='always',
        write_if_match_version_policy='required-on-update-and-delete',
    ),
    _rule(
        'provider-skills-manage',
        r'/api/v1/provider/skills(?:/\{provider_skill_id\})?',
        methods=_methods('POST','PATCH','DELETE'),
        resource_owner='provider-catalog',
        audience='provider',
        authentication='bearer',
        permission='provider.skills.manage',
        tenant_scope='provider-membership',
        record_policy='current-provider-record',
        capability_gate='always',
        write_if_match_version_policy='required-on-update-and-delete',
    ),
    _rule(
        'provider-application-review',
        r'/api/v1/admin/provider-applications(?:/\{application_id\}(?:/(?:approve|reject|request-information))?)?',
        methods=_methods('GET','POST'),
        resource_owner='provider-onboarding',
        audience='admin',
        authentication='bearer',
        permission='admin.access.manage',
        tenant_scope='route-defined-current-scope',
        record_policy='authorized-application-reviewer',
        capability_gate='always',
    ),
    _rule(
        'geography-administration',
        r'/api/v1/admin/(?:service-zones(?:/\{service_area_id\}(?:/coverage)?)?|postal-codes(?:/\{postal_code_id\}|/import|/imports/\{import_id\})?)',
        methods=_methods('GET','POST','PATCH','DELETE'),
        resource_owner='service-coverage',
        audience='admin',
        authentication='bearer',
        permission='admin.access.manage',
        tenant_scope='route-defined-current-scope',
        record_policy='authorized-geography-administrator',
        capability_gate='always',
    ),
    _rule(
        'booking-intent-session',
        r'/api/v1/booking/intents(?:/\{intent_id\}(?:/submit)?)?',
        methods=_methods('GET','POST','PATCH','DELETE'),
        resource_owner='booking-intents',
        audience='public-session',
        authentication='booking-session-cookie',
        permission='booking.intent.session-owner',
        tenant_scope='session',
        record_policy='matching-session-and-unexpired-intent',
        capability_gate='submission delegates to booking service capability gates',
        write_if_match_version_policy='required-on-update-delete-submit',
    ),

    _rule(
        "operational-health",
        r"/(?:health(?:/live|/ready)?|ready)",
        methods=_methods("GET"),
        resource_owner="platform-runtime",
        audience="operations",
        authentication="network-policy",
        permission="platform.health.read",
        tenant_scope="global",
        record_policy="dependency-status-only",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="health-probe",
        pii_classification="none",
    ),
    _rule(
        "internal-odoo-read",
        r"/internal/v1/integrations/odoo/(?:health|failures|deliveries/\{event_id\})",
        methods=_methods("GET"),
        resource_owner="integration-delivery",
        audience="internal-operations",
        authentication="bearer",
        permission="integration.odoo.read",
        tenant_scope="tenant-and-legal-entity",
        record_policy="roles:operations|finance|admin; event-prefix:breero.",
        capability_gate="odoo-observability-always; delivery=settings.odoo_enabled",
        emitted_effect="none",
        rate_limit_class="internal-read",
        pii_classification="operational",
    ),
    _rule(
        "internal-odoo-retry",
        r"/internal/v1/integrations/odoo/deliveries/\{event_id\}/retry",
        methods=_methods("POST"),
        resource_owner="integration-delivery",
        audience="internal-operations",
        authentication="bearer",
        permission="integration.odoo.retry",
        tenant_scope="tenant-and-legal-entity",
        record_policy="roles:operations|finance|admin; event-prefix:breero.",
        capability_gate="always; enqueue only; worker enforces delivery capability",
        write_idempotency_key_policy="command-id-required-before-activation",
        write_request_hash_policy="required-before-activation",
        write_if_match_version_policy="delivery-claim-token",
        emitted_effect="outbox-delivery-retry",
        rate_limit_class="privileged-command",
        pii_classification="operational",
    ),
    _rule(
        "v2-public-capabilities",
        r"/api/v2/capabilities",
        methods=_methods("GET"),
        resource_owner="platform-capabilities",
        audience="public",
        authentication="none",
        permission="capabilities.read",
        tenant_scope="global",
        record_policy="public-release-flags-only",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="public-read",
        pii_classification="none",
    ),
    _rule(
        "v1-public-capabilities",
        r"/api/v1/public/capabilities",
        methods=_methods("GET"),
        resource_owner="platform-capabilities",
        audience="public",
        authentication="none",
        permission="capabilities.read",
        tenant_scope="global",
        record_policy="public-release-flags-only",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="public-read",
        pii_classification="none",
    ),
    _rule(
        "public-auth-commands",
        r"/api/v1/auth/(?:register(?:/client)?|login|refresh|logout|password/set|password/forgot|password/reset|email/verify)",
        methods=_methods("POST"),
        resource_owner="identity",
        audience="public-or-token-holder",
        authentication="credential-or-refresh-token",
        permission="identity.session.command",
        tenant_scope="identity",
        record_policy="subject-owned-session-or-token",
        capability_gate="local-auth-disabled-when-settings.keycloak_enabled where applicable",
        write_idempotency_key_policy="not-required-security-command",
        write_request_hash_policy="not-applicable",
        write_if_match_version_policy="not-applicable",
        emitted_effect="identity-audit-and-session-state",
        rate_limit_class="auth-sensitive",
        pii_classification="restricted-auth",
    ),
    _rule(
        "authenticated-auth-commands",
        r"/api/v1/auth/(?:logout-all|password/change|email/resend-verification|email/resend)",
        methods=_methods("POST"),
        resource_owner="identity",
        audience="authenticated-user",
        authentication="bearer",
        permission="identity.self.manage",
        tenant_scope="identity",
        record_policy="subject-self",
        capability_gate="always",
        write_idempotency_key_policy="not-required-security-command",
        write_request_hash_policy="not-applicable",
        write_if_match_version_policy="session-version",
        emitted_effect="identity-audit-and-session-state",
        rate_limit_class="auth-sensitive",
        pii_classification="restricted-auth",
    ),
    _rule(
        "authenticated-user-read",
        r"/api/v1/auth/(?:me|context)",
        methods=_methods("GET"),
        resource_owner="identity",
        audience="authenticated-user",
        authentication="bearer",
        permission="identity.self.read",
        tenant_scope="identity",
        record_policy="subject-self",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="authenticated-read",
        pii_classification="restricted-auth",
    ),
    _rule(
        "public-catalog-read",
        r"/api/v1/services(?:/\{service_id\}(?:/questions)?)?",
        methods=_methods("GET"),
        resource_owner="catalog",
        audience="public",
        authentication="none",
        permission="catalog.read",
        tenant_scope="global-or-legal-entity-catalog",
        record_policy="active-public-services",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="public-read",
        pii_classification="none",
    ),
    _rule(
        "catalog-admin-write",
        r"/api/v1/services",
        methods=_methods("POST"),
        resource_owner="catalog",
        audience="operations-admin",
        authentication="bearer",
        permission="catalog.create",
        tenant_scope="tenant-and-legal-entity",
        record_policy="roles:operations|admin",
        capability_gate="always",
        write_idempotency_key_policy="required-target; legacy-not-enforced",
        write_request_hash_policy="required-target; legacy-not-enforced",
        write_if_match_version_policy="not-applicable-on-create",
        emitted_effect="catalog-service-created",
        rate_limit_class="privileged-command",
        pii_classification="internal",
    ),
    _rule(
        "public-address-validation",
        r"/api/v1/addresses/validate",
        methods=_methods("POST"),
        resource_owner="booking-address",
        audience="public",
        authentication="none",
        permission="address.validate",
        tenant_scope="legal-entity-resolution",
        record_policy="normalized-address-response",
        capability_gate="settings.geocoding_enabled",
        write_idempotency_key_policy="not-required-read-like-command",
        write_request_hash_policy="request-digest-for-cache-target",
        write_if_match_version_policy="not-applicable",
        emitted_effect="none",
        rate_limit_class="public-expensive-read",
        pii_classification="sensitive-location",
    ),
    _rule(
        "public-availability-search",
        r"/api/v1/availability/search",
        methods=_methods("POST"),
        resource_owner="booking-availability",
        audience="public",
        authentication="none",
        permission="availability.search",
        tenant_scope="legal-entity-and-service-area",
        record_policy="eligible-slots-only",
        capability_gate="settings.scheduling_enabled",
        write_idempotency_key_policy="not-required-read-like-command",
        write_request_hash_policy="request-digest-for-cache-target",
        write_if_match_version_policy="not-applicable",
        emitted_effect="none",
        rate_limit_class="public-expensive-read",
        pii_classification="sensitive-location",
    ),
    _rule(
        "booking-lifecycle",
        r"/api/v1/bookings(?:/.*)?",
        resource_owner="booking",
        audience="guest-customer-or-operations",
        authentication="guest-credential-or-bearer",
        permission="booking.route-defined-legacy",
        tenant_scope="tenant-and-legal-entity",
        record_policy="booking-owner-or-authorized-operator",
        capability_gate="settings.scheduling_enabled; automatic confirmation remains disabled",
        write_idempotency_key_policy="required-target; route-specific-legacy",
        write_request_hash_policy="required-target; route-specific-legacy",
        write_if_match_version_policy="aggregate-version-target; route-specific-legacy",
        emitted_effect="booking-lifecycle-event",
        rate_limit_class="customer-command",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "customer-account",
        r"/api/v1/customer(?:/.*)?",
        resource_owner="customer-account",
        audience="customer",
        authentication="bearer",
        permission="customer.route-defined-legacy",
        tenant_scope="tenant-and-legal-entity",
        record_policy="customer-self-and-owned-records",
        capability_gate="route-defined; financial routes require payments flags",
        write_idempotency_key_policy="required-target; route-specific-legacy",
        write_request_hash_policy="required-target; route-specific-legacy",
        write_if_match_version_policy="aggregate-version-target; route-specific-legacy",
        emitted_effect="customer-domain-event",
        rate_limit_class="authenticated-customer",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "privacy-request-create",
        r"/api/v1/privacy-requests",
        methods=_methods("POST"),
        resource_owner="privacy-compliance",
        audience="public-data-subject",
        authentication="none",
        permission="privacy.request.create",
        tenant_scope="legal-entity-resolution",
        record_policy="receipt-token-protected",
        capability_gate="always",
        write_idempotency_key_policy="required-target; legacy-not-enforced",
        write_request_hash_policy="required-target; legacy-not-enforced",
        write_if_match_version_policy="not-applicable-on-create",
        emitted_effect="privacy-request-created",
        rate_limit_class="public-compliance",
        pii_classification="restricted-privacy",
    ),
    _rule(
        "privacy-request-status",
        r"/api/v1/privacy-requests/\{request_id\}",
        methods=_methods("GET"),
        resource_owner="privacy-compliance",
        audience="data-subject",
        authentication="receipt-bearer-token",
        permission="privacy.request.read",
        tenant_scope="receipt-bound",
        record_policy="matching-receipt-token-only",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="public-compliance",
        pii_classification="restricted-privacy",
    ),
    _rule(
        "communication-compliance",
        r"/api/v1/communications/(?:preferences|sms-revocations)",
        methods=_methods("POST"),
        resource_owner="communications-compliance",
        audience="public-recipient",
        authentication="none-or-provider-inbound",
        permission="communications.preference.write",
        tenant_scope="legal-entity-resolution",
        record_policy="recipient-suppression-scope",
        capability_gate="suppression-always-on",
        write_idempotency_key_policy="required-target; legacy-not-enforced",
        write_request_hash_policy="required-target; legacy-not-enforced",
        write_if_match_version_policy="suppression-upsert",
        emitted_effect="communication-preference-or-revocation",
        rate_limit_class="public-compliance",
        pii_classification="restricted-contact",
    ),
    _rule(
        "public-submission-intake",
        r"/api/v1/(?:service-requests|contact|provider-interest)",
        methods=_methods("POST"),
        resource_owner="public-submissions",
        audience="public",
        authentication="none",
        permission="public-submission.create",
        tenant_scope="legal-entity-resolution",
        record_policy="submission-receipt-only",
        capability_gate="request_intake for service requests; route-defined for contact/provider interest",
        write_idempotency_key_policy="required",
        write_request_hash_policy="required",
        write_if_match_version_policy="not-applicable-on-create",
        emitted_effect="submission-created-and-outbox-event",
        rate_limit_class="public-intake",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "payment-intent",
        r"/api/v1/payments/intents",
        methods=_methods("POST"),
        resource_owner="finance-payments",
        audience="customer",
        authentication="none; legacy guest route",
        permission="legacy-owner-authorization-not-enforced",
        tenant_scope="booking-legal-entity",
        record_policy="booking-or-quote-existence-amount-currency-state; ownership-required-before-activation",
        capability_gate="settings.payments_enabled && settings.stripe_enabled",
        write_idempotency_key_policy="required",
        write_request_hash_policy="required",
        emitted_effect="payment-intent",
        pii_classification="restricted-financial",
    ),
    _rule(
        "stripe-webhook",
        r"/api/v1/payments/webhooks/stripe",
        methods=_methods("POST"),
        resource_owner="finance-payments",
        audience="stripe",
        authentication="Stripe-Signature",
        permission="verified-provider-event",
        tenant_scope="resolved-payment-legal-entity",
        record_policy="verified-provider-event",
        capability_gate="settings.payments_enabled && settings.stripe_enabled",
        write_idempotency_key_policy="provider-event-id",
        emitted_effect="payment-lifecycle-event",
        pii_classification="restricted-financial",
    ),
    _rule(
        "payments",
        r"/api/v1/payments/\{payment_id\}(?:/(?:capture|refunds))?",
        resource_owner="finance-payments",
        audience="customer-or-finance",
        authentication="bearer",
        permission="payment.route-defined-legacy",
        tenant_scope="tenant-and-legal-entity",
        record_policy="payment-owner-or-finance-role",
        capability_gate="settings.payments_enabled && settings.stripe_enabled",
        write_idempotency_key_policy="required",
        write_request_hash_policy="required",
        write_if_match_version_policy="provider-and-aggregate-version",
        emitted_effect="payment-lifecycle-event",
        rate_limit_class="financial-command",
        pii_classification="restricted-financial",
    ),
    _rule(
        "jobs-and-work-requests",
        r"/api/v1/jobs(?:/.*)?",
        resource_owner="job-execution",
        audience="customer-provider-worker-or-operations",
        authentication="bearer",
        permission="job.route-defined-legacy",
        tenant_scope="tenant-and-legal-entity",
        record_policy="job-party-or-authorized-operator",
        capability_gate="manual-job-execution-only",
        write_idempotency_key_policy="required-target; route-specific-legacy",
        write_request_hash_policy="required-target; route-specific-legacy",
        write_if_match_version_policy="job-version-target; route-specific-legacy",
        emitted_effect="job-or-work-request-event",
        rate_limit_class="authenticated-command",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "vendors-and-workforce",
        r"/api/v1/vendors(?:/.*)?",
        resource_owner="provider-workforce",
        audience="provider-worker-or-operations",
        authentication="bearer",
        permission="provider.route-defined-legacy",
        tenant_scope="tenant-and-legal-entity",
        record_policy="provider-membership-or-authorized-operator",
        capability_gate="provider-self-service disabled unless explicitly enabled",
        write_idempotency_key_policy="required-target; route-specific-legacy",
        write_request_hash_policy="required-target; route-specific-legacy",
        write_if_match_version_policy="provider-version-target; route-specific-legacy",
        emitted_effect="provider-or-workforce-event",
        rate_limit_class="authenticated-command",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "operations",
        r"/api/v1/operations(?:/.*)?",
        resource_owner="marketplace-operations",
        audience="operations-admin",
        authentication="bearer",
        permission="operations.route-defined-legacy",
        tenant_scope="tenant-and-legal-entity",
        record_policy="authorized-operator-and-record-policy",
        capability_gate="matching/assignment/confirmation flags remain fail-closed",
        write_idempotency_key_policy="required-target; route-specific-legacy",
        write_request_hash_policy="required-target; route-specific-legacy",
        write_if_match_version_policy="aggregate-version-target; route-specific-legacy",
        emitted_effect="operations-command-event",
        rate_limit_class="privileged-command",
        pii_classification="operational-sensitive",
    ),
    _rule(
        "finance-and-payouts",
        r"/api/v1/finance(?:/.*)?",
        resource_owner="finance-payouts",
        audience="finance-admin",
        authentication="bearer",
        permission="finance.route-defined-legacy",
        tenant_scope="tenant-and-legal-entity",
        record_policy="roles:finance|admin",
        capability_gate="settings.payout_enabled",
        write_idempotency_key_policy="required",
        write_request_hash_policy="required",
        write_if_match_version_policy="financial-aggregate-and-provider-version",
        emitted_effect="payout-or-ledger-event",
        rate_limit_class="financial-command",
        pii_classification="restricted-financial",
    ),
    _rule(
        "integration-observation",
        r"/api/v1/integrations(?:/.*)?",
        methods=_methods("GET"),
        resource_owner="integration-delivery",
        audience="finance-admin",
        authentication="bearer",
        permission="integration.delivery.read",
        tenant_scope="tenant-and-legal-entity",
        record_policy="roles:finance|admin",
        capability_gate="always",
        emitted_effect="none",
        pii_classification="operational",
    ),
    _rule(
        "integration-operations",
        r"/api/v1/integrations(?:/.*)?",
        methods=_methods("POST"),
        resource_owner="integration-delivery",
        audience="finance-admin",
        authentication="bearer",
        permission="integration.delivery.manage",
        tenant_scope="tenant-and-legal-entity",
        record_policy="roles:finance|admin",
        capability_gate="always; enqueue only; worker enforces delivery capability",
        write_idempotency_key_policy="command-id-required-before-activation",
        write_request_hash_policy="required-before-activation",
        write_if_match_version_policy="delivery-claim-token",
        emitted_effect="delivery-retry",
        rate_limit_class="privileged-command",
        pii_classification="operational",
    ),
    _rule(
        "client-account",
        r"/api/v1/client(?:/.*)?",
        resource_owner="customer-account",
        audience="customer",
        authentication="bearer",
        permission="customer.route-defined-legacy",
        tenant_scope="tenant-and-legal-entity",
        record_policy="customer-self-and-owned-records",
        capability_gate="route-defined; financial routes require payments flags",
        write_idempotency_key_policy="required-target; route-specific-legacy",
        write_request_hash_policy="required-target; route-specific-legacy",
        write_if_match_version_policy="aggregate-version-target; route-specific-legacy",
        emitted_effect="customer-domain-event",
        rate_limit_class="authenticated-customer",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "admin-provider-directory-read",
        r"/api/v1/admin/providers(?:/\{provider_id\})?",
        methods=_methods("GET"),
        resource_owner="provider-directory",
        audience="operations-admin-support",
        authentication="bearer",
        permission="roles:breero_admin|breero_dispatch|breero_support",
        tenant_scope="global-operations",
        record_policy="authorized-internal-provider-read",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="internal-read",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "admin-feature-flags-read",
        r"/api/v1/admin/feature-flags",
        methods=_methods("GET"),
        resource_owner="release-capabilities",
        audience="operations-admin-support",
        authentication="bearer",
        permission="roles:breero_admin|breero_dispatch|breero_support",
        tenant_scope="global-operations",
        record_policy="protected-feature-flag-read",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="internal-read",
        pii_classification="internal",
    ),
    _rule(
        "admin-feature-flags-disable",
        r"/api/v1/admin/feature-flags/\{flag\}",
        methods=_methods("PATCH"),
        resource_owner="release-capabilities",
        audience="admin",
        authentication="bearer",
        permission="role:breero_admin",
        tenant_scope="global-operations",
        record_policy="protected-flags-disable-only",
        capability_gate="api-cannot-enable-protected-effects",
        write_idempotency_key_policy="recommended-command-id",
        write_request_hash_policy="required-target-before-production-activation",
        write_if_match_version_policy="not-yet-enforced",
        emitted_effect="feature-flag-disabled-and-audited",
        rate_limit_class="privileged-command",
        pii_classification="internal",
    ),
    _rule(
        "admin-operating-hours-read",
        r"/api/v1/admin/operating-hours",
        methods=_methods("GET"),
        resource_owner="operating-hours",
        audience="operations-admin-support",
        authentication="bearer",
        permission="roles:breero_admin|breero_dispatch|breero_support",
        tenant_scope="global-operations",
        record_policy="authorized-operating-hours-read",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="internal-read",
        pii_classification="internal",
    ),
    _rule(
        "admin-operating-hours-write",
        r"/api/v1/admin/operating-hours",
        methods=_methods("PUT"),
        resource_owner="operating-hours",
        audience="admin",
        authentication="bearer",
        permission="role:breero_admin",
        tenant_scope="global-operations",
        record_policy="complete-seven-day-replacement",
        capability_gate="always",
        write_idempotency_key_policy="required-target",
        write_request_hash_policy="required-target",
        write_if_match_version_policy="not-yet-enforced",
        emitted_effect="operating-hours-changed-and-audited",
        rate_limit_class="privileged-command",
        pii_classification="internal",
    ),
    _rule(
        "admin-audit-read",
        r"/api/v1/admin/audit-events(?:/\{event_id\})?",
        methods=_methods("GET"),
        resource_owner="audit",
        audience="operations-admin-support",
        authentication="bearer",
        permission="roles:breero_admin|breero_dispatch|breero_support",
        tenant_scope="global-operations",
        record_policy="authorized-audit-read",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="internal-read",
        pii_classification="restricted-audit",
    ),
    _rule(
        "admin-booking-read",
        r"/api/v1/admin/bookings(?:/\{booking_id\}(?:/provider-candidates)?)?",
        methods=_methods("GET"),
        resource_owner="booking-dispatch",
        audience="operations-admin",
        authentication="bearer",
        permission="roles:operations|admin",
        tenant_scope="global-operations",
        record_policy="authorized-dispatch-booking-read",
        capability_gate="settings.scheduling_enabled",
        emitted_effect="none",
        rate_limit_class="internal-read",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "admin-booking-assignment",
        r"/api/v1/admin/bookings/\{booking_id\}/(?:assign|reassign|unassign)",
        methods=_methods("POST"),
        resource_owner="booking-dispatch",
        audience="operations-admin",
        authentication="bearer",
        permission="roles:operations|admin",
        tenant_scope="global-operations",
        record_policy="authorized-dispatch-assignment",
        capability_gate="manual-dispatch-only; automatic assignment remains disabled",
        write_idempotency_key_policy="required-target",
        write_request_hash_policy="required-target",
        write_if_match_version_policy="booking-and-assignment-locking",
        emitted_effect="booking-assignment-history-and-audit",
        rate_limit_class="privileged-command",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "browser-csrf-read",
        r"/api/v1/auth/csrf",
        methods=_methods("GET"),
        resource_owner="identity",
        audience="browser-session",
        authentication="browser-session-cookie",
        permission="identity.session.csrf.read",
        tenant_scope="identity",
        record_policy="approved-origin-and-current-browser-session",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="auth-sensitive",
        pii_classification="restricted-auth",
    ),
    _rule(
        "browser-auth-public",
        r"/api/v1/auth/browser/(?:login|register/client|register/provider)",
        methods=_methods("POST"),
        resource_owner="identity",
        audience="public-browser",
        authentication="credentials-or-registration-payload",
        permission="identity.browser.session.create",
        tenant_scope="identity",
        record_policy="public-registration-or-login",
        capability_gate="local-auth-only; registration disabled when Keycloak owns identity",
        write_idempotency_key_policy="not-required-security-command",
        write_request_hash_policy="not-applicable",
        write_if_match_version_policy="not-applicable",
        emitted_effect="browser-session-created",
        rate_limit_class="auth-sensitive",
        pii_classification="restricted-auth",
    ),
    _rule(
        "browser-session-command",
        r"/api/v1/auth/browser/(?:refresh|logout|password/set)",
        methods=_methods("POST"),
        resource_owner="identity",
        audience="browser-session",
        authentication="browser-session-cookie-and-csrf",
        permission="identity.session.manage",
        tenant_scope="identity",
        record_policy="current-browser-session",
        capability_gate="route-defined; password set requires local auth",
        write_idempotency_key_policy="not-required-security-command",
        write_request_hash_policy="not-applicable",
        write_if_match_version_policy="session-version",
        emitted_effect="session-state-and-identity-audit",
        rate_limit_class="auth-sensitive",
        pii_classification="restricted-auth",
    ),
    _rule(
        "phone-verification",
        r"/api/v1/auth/phone/verify",
        methods=_methods("POST"),
        resource_owner="identity",
        audience="authenticated-user",
        authentication="bearer",
        permission="identity.self.manage",
        tenant_scope="identity",
        record_policy="subject-self",
        capability_gate="always",
        write_idempotency_key_policy="not-required-security-command",
        write_request_hash_policy="not-applicable",
        write_if_match_version_policy="identity-version",
        emitted_effect="phone-verification-state",
        rate_limit_class="auth-sensitive",
        pii_classification="restricted-auth",
    ),
    _rule(
        "keycloak-login-status",
        r"/api/v1/auth/keycloak/(?:login|status)",
        methods=_methods("GET"),
        resource_owner="identity",
        audience="browser",
        authentication="none",
        permission="identity.keycloak.read",
        tenant_scope="identity",
        record_policy="public-oidc-configuration-or-login-start",
        capability_gate="route-defined; login requires settings.keycloak_enabled",
        emitted_effect="oidc-login-transaction-on-login",
        rate_limit_class="auth-sensitive",
        pii_classification="none",
    ),
    _rule(
        "keycloak-callback",
        r"/api/v1/auth/keycloak/callback",
        methods=_methods("GET"),
        resource_owner="identity",
        audience="browser",
        authentication="oidc-code-state-nonce-transaction-cookie",
        permission="identity.keycloak.callback",
        tenant_scope="identity",
        record_policy="matching-oidc-transaction",
        capability_gate="settings.keycloak_enabled",
        emitted_effect="identity-link-and-browser-session",
        rate_limit_class="auth-sensitive",
        pii_classification="restricted-auth",
    ),
    _rule(
        "keycloak-logout",
        r"/api/v1/auth/keycloak/logout",
        methods=_methods("POST"),
        resource_owner="identity",
        audience="browser-session",
        authentication="browser-session-cookie-and-csrf",
        permission="identity.session.manage",
        tenant_scope="identity",
        record_policy="current-browser-session",
        capability_gate="settings.keycloak_enabled",
        write_idempotency_key_policy="not-required-security-command",
        write_request_hash_policy="not-applicable",
        write_if_match_version_policy="session-version",
        emitted_effect="local-and-keycloak-session-close",
        rate_limit_class="auth-sensitive",
        pii_classification="restricted-auth",
    ),
    _rule(
        "public-booking-geography",
        r"/api/v1/booking/(?:address/validate|service-area/check|timezone/resolve)",
        methods=_methods("POST"),
        resource_owner="booking-intake",
        audience="public",
        authentication="none",
        permission="booking.public.geography",
        tenant_scope="legal-entity-and-service-area-resolution",
        record_policy="normalized-address-serviceability-timezone",
        capability_gate="settings.public_booking_api_enabled && settings.geocoding_enabled",
        write_idempotency_key_policy="not-required-read-like-command",
        write_request_hash_policy="request-digest-for-cache-target",
        write_if_match_version_policy="not-applicable",
        emitted_effect="none",
        rate_limit_class="public-expensive-read",
        pii_classification="sensitive-location",
    ),
    _rule(
        "public-booking-availability",
        r"/api/v1/booking/availability",
        methods=_methods("POST"),
        resource_owner="booking-availability",
        audience="public",
        authentication="none",
        permission="booking.public.availability",
        tenant_scope="legal-entity-and-service-area",
        record_policy="eligible-public-slots-only",
        capability_gate="settings.public_booking_api_enabled && settings.scheduling_enabled",
        write_idempotency_key_policy="not-required-read-like-command",
        write_request_hash_policy="request-digest-for-cache-target",
        write_if_match_version_policy="not-applicable",
        emitted_effect="none",
        rate_limit_class="public-expensive-read",
        pii_classification="sensitive-location",
    ),
    _rule(
        "public-booking-holds",
        r"/api/v1/booking/holds(?:/\{hold_id\})?",
        methods=_methods("POST", "GET", "DELETE"),
        resource_owner="booking-capacity",
        audience="public-booking-session",
        authentication="booking-session-header",
        permission="booking.hold.session-owner",
        tenant_scope="booking-session-and-service-area",
        record_policy="matching-booking-session",
        capability_gate="settings.public_booking_api_enabled && settings.scheduling_enabled",
        write_idempotency_key_policy="required-on-create",
        write_request_hash_policy="required-on-create",
        write_if_match_version_policy="capacity-lock-and-hold-state",
        emitted_effect="capacity-hold-created-or-released",
        rate_limit_class="customer-command",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "public-booking-requests",
        r"/api/v1/booking/requests(?:/\{public_reference\})?",
        methods=_methods("POST", "GET"),
        resource_owner="booking-request",
        audience="public-or-authenticated-customer",
        authentication="optional-bearer-or-public-reference",
        permission="booking.request.create-or-public-status",
        tenant_scope="booking-request-resolution",
        record_policy="created-request-or-public-reference-status",
        capability_gate="settings.public_booking_api_enabled",
        write_idempotency_key_policy="request-defined-idempotency",
        write_request_hash_policy="request-defined-hash",
        write_if_match_version_policy="booking-request-state",
        emitted_effect="booking-request-created",
        rate_limit_class="customer-command",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "provider-jobs-read",
        r"/api/v1/provider/jobs(?:/\{job_id\})?",
        methods=_methods("GET"),
        resource_owner="provider-jobs",
        audience="provider",
        authentication="bearer",
        permission="roles:vendor_admin|technician",
        tenant_scope="provider-membership",
        record_policy="current-provider-owned-jobs",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="authenticated-provider",
        pii_classification="customer-sensitive",
    ),
    _rule(
        "provider-service-areas-read",
        r"/api/v1/provider/service-areas(?:/\{item_id\})?",
        methods=_methods("GET"),
        resource_owner="provider-coverage",
        audience="provider",
        authentication="bearer",
        permission="roles:vendor_admin|technician",
        tenant_scope="provider-membership",
        record_policy="current-provider-service-areas",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="authenticated-provider",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "provider-service-areas-manage",
        r"/api/v1/provider/service-areas(?:/\{item_id\})?",
        methods=_methods("POST", "PATCH", "DELETE"),
        resource_owner="provider-coverage",
        audience="provider",
        authentication="bearer",
        permission="role:vendor_admin",
        tenant_scope="provider-membership",
        record_policy="current-provider-service-areas",
        capability_gate="always",
        write_idempotency_key_policy="required-target",
        write_request_hash_policy="required-target",
        write_if_match_version_policy="provider-area-state",
        emitted_effect="provider-service-area-changed",
        rate_limit_class="provider-command",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "provider-availability-read",
        r"/api/v1/provider/availability(?:/exceptions)?",
        methods=_methods("GET"),
        resource_owner="provider-scheduling",
        audience="provider",
        authentication="bearer",
        permission="roles:vendor_admin|technician",
        tenant_scope="provider-membership",
        record_policy="current-provider-availability",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="authenticated-provider",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "provider-availability-replace",
        r"/api/v1/provider/availability",
        methods=_methods("PUT"),
        resource_owner="provider-scheduling",
        audience="provider",
        authentication="bearer",
        permission="role:vendor_admin",
        tenant_scope="provider-membership",
        record_policy="replace-current-provider-availability",
        capability_gate="always",
        write_idempotency_key_policy="required-target",
        write_request_hash_policy="required-target",
        write_if_match_version_policy="provider-schedule-version-target",
        emitted_effect="provider-availability-replaced",
        rate_limit_class="provider-command",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "provider-availability-exceptions-manage",
        r"/api/v1/provider/availability/exceptions(?:/\{item_id\})?",
        methods=_methods("POST", "PATCH", "DELETE"),
        resource_owner="provider-scheduling",
        audience="provider",
        authentication="bearer",
        permission="role:vendor_admin",
        tenant_scope="provider-membership",
        record_policy="current-provider-availability-exception",
        capability_gate="always",
        write_idempotency_key_policy="required-target",
        write_request_hash_policy="required-target",
        write_if_match_version_policy="provider-schedule-version-target",
        emitted_effect="provider-availability-exception-changed",
        rate_limit_class="provider-command",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "provider-capacity-read",
        r"/api/v1/provider/capacity(?:/calendar)?",
        methods=_methods("GET"),
        resource_owner="provider-capacity",
        audience="provider",
        authentication="bearer",
        permission="roles:vendor_admin|technician",
        tenant_scope="provider-membership",
        record_policy="current-provider-capacity",
        capability_gate="always",
        emitted_effect="none",
        rate_limit_class="authenticated-provider",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "provider-capacity-manage",
        r"/api/v1/provider/capacity",
        methods=_methods("PATCH"),
        resource_owner="provider-capacity",
        audience="provider",
        authentication="bearer",
        permission="role:vendor_admin",
        tenant_scope="provider-membership",
        record_policy="current-provider-capacity",
        capability_gate="always",
        write_idempotency_key_policy="required-target",
        write_request_hash_policy="required-target",
        write_if_match_version_policy="capacity-rule-version-target",
        emitted_effect="provider-capacity-changed",
        rate_limit_class="provider-command",
        pii_classification="provider-sensitive",
    ),
    _rule(
        "provider-paid-leads",
        r"/api/v1/provider/leads(?:/.*)?",
        resource_owner="professional-leads",
        audience="provider",
        authentication="bearer",
        permission="provider.lead.route-defined",
        tenant_scope="tenant-and-legal-entity",
        record_policy="provider-context-and-purchased-record",
        capability_gate=(
            "settings.paid_leads_enabled && settings.payments_enabled && settings.stripe_enabled"
        ),
        write_idempotency_key_policy="required-for-purchase; required-target-for-dispute",
        write_request_hash_policy="required-for-purchase; required-target-for-dispute",
        write_if_match_version_policy="lead-and-purchase-version",
        emitted_effect="lead-purchase-or-dispute-event",
        rate_limit_class="financial-command",
        pii_classification="restricted-lead",
    ),
)


def _schema_name(value: object | None) -> str:
    if value is None:
        return "none"
    module = getattr(value, "__module__", None)
    qualified_name = getattr(value, "__qualname__", None) or getattr(value, "__name__", None)
    if module and qualified_name:
        return f"{module}.{qualified_name}"
    return str(value).replace("typing.", "")


def _matching_rules(method: str, path: str) -> list[EndpointPolicyRule]:
    return [
        rule
        for rule in POLICY_RULES
        if method in rule.methods and re.fullmatch(rule.path_pattern, path)
    ]


def _expand_policy(rule: EndpointPolicyRule, route: APIRoute, method: str) -> EndpointPolicy:
    is_write = method not in SAFE_METHODS
    body_type = getattr(route.body_field, "type_", None) if route.body_field is not None else None
    response_type = route.response_model
    return EndpointPolicy(
        method=method,
        path=route.path,
        operation_id=route.unique_id,
        policy_rule=rule.name,
        resource_owner=rule.resource_owner,
        audience=rule.audience,
        authentication=rule.authentication,
        permission=rule.permission,
        tenant_scope=rule.tenant_scope,
        record_policy=rule.record_policy,
        capability_gate=rule.capability_gate,
        idempotency_key_policy=(
            rule.write_idempotency_key_policy if is_write else "not-applicable"
        ),
        request_hash_policy=(rule.write_request_hash_policy if is_write else "not-applicable"),
        if_match_version_policy=(
            rule.write_if_match_version_policy if is_write else "not-applicable"
        ),
        request_schema=_schema_name(body_type),
        response_schema=_schema_name(response_type),
        emitted_effect=rule.emitted_effect if is_write else "none",
        deprecation_status="deprecated" if route.deprecated else rule.deprecation_status,
        rate_limit_class=rule.rate_limit_class,
        pii_classification=rule.pii_classification,
    )


def iter_api_route_contexts(app: FastAPI) -> Iterator[Any]:
    """Yield FastAPI's effective APIRoute contexts, including nested routers."""

    for route_context in fastapi_routing.iter_route_contexts(app.routes):
        if isinstance(route_context.original_route, APIRoute):
            yield route_context


def build_endpoint_policies(app: FastAPI) -> tuple[EndpointPolicy, ...]:
    """Expand and validate the policy for every mounted runtime operation."""

    policies: list[EndpointPolicy] = []
    unmatched: list[str] = []
    ambiguous: list[str] = []
    route_shapes: dict[tuple[str, str], list[str]] = {}

    for route in iter_api_route_contexts(app):
        if route.path in DOCUMENTATION_PATHS:
            continue
        for method in sorted((route.methods or set()) & OPENAPI_METHODS):
            route_shapes.setdefault((method, _route_shape(route.path)), []).append(route.path)
            matches = _matching_rules(method, route.path)
            if not matches:
                unmatched.append(f"{method} {route.path}")
                continue
            if len(matches) != 1:
                ambiguous.append(
                    f"{method} {route.path}: {', '.join(rule.name for rule in matches)}"
                )
                continue
            policies.append(_expand_policy(matches[0], route, method))

    structural_duplicates = [
        f"{method} {shape}: {', '.join(sorted(set(paths)))}"
        for (method, shape), paths in route_shapes.items()
        if len(set(paths)) > 1
    ]

    if unmatched or ambiguous or structural_duplicates:
        details: list[str] = []
        if unmatched:
            details.append("unmatched=" + ", ".join(sorted(unmatched)))
        if ambiguous:
            details.append("ambiguous=" + "; ".join(sorted(ambiguous)))
        if structural_duplicates:
            details.append(
                "structural_duplicates=" + "; ".join(sorted(structural_duplicates))
            )
        raise RuntimeError("Endpoint policy registry is incomplete: " + " | ".join(details))

    identities = [(policy.method, policy.path) for policy in policies]
    if len(identities) != len(set(identities)):
        raise RuntimeError("Endpoint policy registry contains duplicate method/path identities")

    return tuple(sorted(policies, key=lambda item: (item.path, item.method)))


def endpoint_registry_document(app: FastAPI) -> dict[str, Any]:
    endpoints = [asdict(policy) for policy in build_endpoint_policies(app)]
    canonical = {"schema_version": "1.0", "endpoints": endpoints}
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {**canonical, "digest": f"sha256:{digest}"}


def install_endpoint_registry(app: FastAPI) -> dict[str, Any]:
    """Install a version-resilient OpenAPI policy overlay and store the registry."""

    existing = getattr(app.state, "endpoint_registry", None)
    if existing is not None:
        return cast(dict[str, Any], existing)

    document = endpoint_registry_document(app)
    policies_by_path: dict[str, dict[str, dict[str, object]]] = {}
    for policy in document["endpoints"]:
        assert isinstance(policy, dict)
        path = str(policy["path"])
        method = str(policy["method"])
        policies_by_path.setdefault(path, {})[method] = {
            key: value
            for key, value in policy.items()
            if key not in {"path", "method", "operation_id"}
        }

    schema_operations = {
        (route.path, method)
        for route in iter_api_route_contexts(app)
        if route.include_in_schema
        for method in (route.methods or set())
    }

    original_openapi = app.openapi

    def openapi_with_policy() -> dict[str, Any]:
        schema = original_openapi()
        paths = schema.get("paths")
        if not isinstance(paths, dict):
            raise RuntimeError("OpenAPI schema is missing its paths object")

        for path, runtime_policies in policies_by_path.items():
            method_policies = {method: policy for method, policy in runtime_policies.items()
                               if (path, method) in schema_operations}
            if not method_policies:
                continue
            path_item = paths.get(path)
            if not isinstance(path_item, dict):
                raise RuntimeError(f"OpenAPI is missing registered path {path}")
            for method in method_policies:
                operation = path_item.get(method.lower())
                if not isinstance(operation, dict):
                    raise RuntimeError(f"OpenAPI is missing registered operation {method} {path}")
                operation["x-breero-policy"] = {method: method_policies[method]}

        schema["x-breero-endpoint-registry-digest"] = document["digest"]
        app.openapi_schema = schema
        return schema

    app.openapi = openapi_with_policy  # type: ignore[method-assign]
    app.openapi_schema = None
    app.state.endpoint_registry = document
    return document


def get_endpoint_registry(app: FastAPI) -> dict[str, Any]:
    document = getattr(app.state, "endpoint_registry", None)
    if document is None:
        document = install_endpoint_registry(app)
    return cast(dict[str, Any], document)
