"""Metadata minimization for audit rows.

Two independent layers:

* ``scrub_for_storage`` runs on insert and replaces values under secret-shaped keys, so
  a careless emitter cannot persist a token or password into ``audit_logs``.
* ``project_metadata`` runs on read and returns only allowlisted keys with bounded
  scalar values. Anything not explicitly allowlisted is dropped, never echoed.
"""

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"
MAX_VALUE_LENGTH = 200
MAX_LIST_ITEMS = 20

_SECRET_KEY = re.compile(
    r"(?i)(password|passwd|passphrase|secret|token|api[_-]?key|authorization|cookie"
    r"|private[_-]?key)"
)
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]{8,}"
    r"|eyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}"  # JWT header/payload
    r"|\b(sk|rk|pk)_(live|test)_[a-z0-9]{8,}"  # Stripe-style keys
    r"|(password|secret|token|api[_-]?key)\s*[:=]\s*\S+)"
)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.IGNORECASE)

# Keys an administrator may see. Values are still type/length bounded and re-checked
# against secret and e-mail patterns. Free-text fields (notes, previous_error, reason
# bodies from customers) are deliberately absent.
METADATA_ALLOWLIST: frozenset[str] = frozenset(
    {
        "aggregate_type",
        "application_status",
        "brand_key",
        "credential_type",
        "currency",
        "earning_count",
        "event_type",
        "expires_on",
        "from_status",
        "gpc",
        "identity_mode",
        "jurisdiction",
        "method",
        "new_roles",
        "new_status",
        "password_rehashed",
        "path_template",
        "payment_required",
        "previous_error_code",
        "previous_roles",
        "previous_status",
        "provider_status",
        "reason_code",
        "refund_automatic",
        "request_type",
        "required",
        "role",
        "sessions_revoked",
        "status",
        "target_user_id",
        "total_minor",
        "vendor_id",
        "verified",
        "version",
        "worker_id",
    }
)


def _is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY.search(key))


def scrub_for_storage(value: Any) -> Any:
    """Recursively replace values stored under secret-shaped keys."""
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_secret_key(str(key)) else scrub_for_storage(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub_for_storage(item) for item in value]
    if isinstance(value, str) and _SECRET_VALUE.search(value):
        return REDACTED
    return value


def _safe_scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, bool | int | float):
        return value
    if not isinstance(value, str):
        return None
    if _SECRET_VALUE.search(value) or _EMAIL.search(value):
        return REDACTED
    return value[:MAX_VALUE_LENGTH]


def project_metadata(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the admin-safe view of stored metadata."""
    if not isinstance(raw, Mapping):
        return {}
    safe: dict[str, Any] = {}
    for key in sorted(raw):
        if key not in METADATA_ALLOWLIST or _is_secret_key(key):
            continue
        value = raw[key]
        if isinstance(value, list):
            items = [_safe_scalar(item) for item in value[:MAX_LIST_ITEMS]]
            safe[key] = [item for item in items if item is not None]
        elif isinstance(value, Mapping):
            continue
        else:
            scalar = _safe_scalar(value)
            if scalar is not None or value is None:
                safe[key] = scalar
    return safe


def redacted_key_count(raw: Mapping[str, Any] | None) -> int:
    """How many stored keys were withheld, so reviewers know the view is partial."""
    if not isinstance(raw, Mapping):
        return 0
    return len(raw) - len(project_metadata(raw))
