"""Audit event taxonomy, security-view membership, and the retention contract.

Categories are a pure function of ``action`` so they apply to historical rows and to
rows written by workers without request context; nothing category-shaped is stored.
"""

import enum
from dataclasses import dataclass


class AuditResult(enum.StrEnum):
    success = "success"
    denied = "denied"
    failure = "failure"


class AuditCategory(enum.StrEnum):
    access_denied = "access_denied"
    auth_lifecycle = "auth_lifecycle"
    access_change = "access_change"
    privileged_admin = "privileged_admin"
    provider_decision = "provider_decision"
    dispatch = "dispatch"
    finance = "finance"
    integration = "integration"
    privacy = "privacy"
    domain = "domain"


@dataclass(frozen=True, slots=True)
class CategoryRule:
    actions: frozenset[str] = frozenset()
    prefixes: tuple[str, ...] = ()

    def matches(self, action: str) -> bool:
        return action in self.actions or action.startswith(self.prefixes)


ACCESS_DENIED_ACTION = "authz.denied"
ACCESS_ASSIGNMENTS_REPLACED_ACTION = "access.assignments.replace"

# Ordered: the first matching rule wins. ``domain`` is the residual category.
CATEGORY_RULES: dict[AuditCategory, CategoryRule] = {
    AuditCategory.access_denied: CategoryRule(actions=frozenset({ACCESS_DENIED_ACTION})),
    AuditCategory.auth_lifecycle: CategoryRule(
        actions=frozenset({"client.register", "provider.register"}),
        prefixes=("auth.",),
    ),
    AuditCategory.access_change: CategoryRule(prefixes=("access.", "admin.user.")),
    AuditCategory.privileged_admin: CategoryRule(
        prefixes=("service_zone.", "postal_code.", "capability.")
    ),
    AuditCategory.provider_decision: CategoryRule(
        actions=frozenset(
            {
                "provider.onboarding.approve",
                "provider.onboarding.reject",
                "provider.onboarding.request_information",
                "provider_credential.update",
            }
        )
    ),
    AuditCategory.dispatch: CategoryRule(
        actions=frozenset({"booking.operator_confirm"}),
        prefixes=("assignment.", "manual_dispatch.", "dispatch."),
    ),
    AuditCategory.finance: CategoryRule(
        prefixes=("payout.", "earning.", "compensation_plan.", "refund.")
    ),
    AuditCategory.integration: CategoryRule(prefixes=("integration.",)),
    AuditCategory.privacy: CategoryRule(prefixes=("privacy_request.",)),
}

# Security activity view: every non-success row plus these high-risk families.
SECURITY_CATEGORIES: frozenset[AuditCategory] = frozenset(
    {
        AuditCategory.access_denied,
        AuditCategory.auth_lifecycle,
        AuditCategory.access_change,
        AuditCategory.privileged_admin,
        AuditCategory.provider_decision,
        AuditCategory.integration,
    }
)
SECURITY_ACTIONS: frozenset[str] = frozenset({"payout.approve", "payout.submit"})


def categorize(action: str) -> AuditCategory:
    for category, rule in CATEGORY_RULES.items():
        if rule.matches(action):
            return category
    return AuditCategory.domain


def is_security_event(action: str, result: str) -> bool:
    return (
        result != AuditResult.success
        or action in SECURITY_ACTIONS
        or categorize(action) in SECURITY_CATEGORIES
    )


# Retention contract. Encoded, documented, and served read-only; this codebase
# implements no purge, archival, or deletion job for audit rows. Any future purge
# must be a separately reviewed, legally approved change (docs/compliance/AUDIT_READ_MODEL.md).
RETENTION_POLICY = {
    "policy_version": "2026-09-25",
    "storage": "postgresql:audit_logs",
    "mutability": "append_only_by_convention",
    "minimum_retention_days": 2555,
    "security_event_minimum_retention_days": 2555,
    "automated_purge": False,
    "legal_hold_supported": False,
    "deletion_requires": "separately reviewed migration or job with legal/compliance approval",
    "pii_minimization": [
        "raw IP addresses are never stored; source_ip_hash is a keyed HMAC",
        "metadata is exposed only through a per-key allowlist",
        "free-text notes, tokens, secrets, credentials and contact details are never exposed",
    ],
}
