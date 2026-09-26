"""Request-scoped audit context.

The HTTP middleware binds request/correlation IDs and a keyed source hash once per
request; the insert listener copies them onto every ``AuditLog`` written during that
request so existing emitters gain trace context without changing their signatures.
"""

import hashlib
import hmac
from contextvars import ContextVar, Token
from dataclasses import dataclass

from app.config import settings

_SOURCE_HASH_DOMAIN = b"breero.audit.source-ip.v1"


@dataclass(frozen=True, slots=True)
class AuditRequestContext:
    request_id: str | None
    correlation_id: str | None
    source_ip_hash: str | None


_current: ContextVar[AuditRequestContext | None] = ContextVar(
    "breero_audit_request_context", default=None
)


def hash_source_ip(value: str | None) -> str | None:
    """Keyed, non-reversible source fingerprint; the raw address is never stored.

    A plain digest of an IPv4 address is trivially brute-forced, so the hash is an
    HMAC under a key derived from the server signing secret. Rotating that secret
    only changes fingerprints for rows written afterwards.
    """
    if not value or value == "unknown":
        return None
    key = hmac.new(settings.jwt_secret.encode(), _SOURCE_HASH_DOMAIN, hashlib.sha256).digest()
    return hmac.new(key, value.strip().lower().encode(), hashlib.sha256).hexdigest()


def bind_request_context(
    *, request_id: str | None, correlation_id: str | None, client_ip: str | None
) -> Token[AuditRequestContext | None]:
    return _current.set(
        AuditRequestContext(
            request_id=request_id,
            correlation_id=correlation_id,
            source_ip_hash=hash_source_ip(client_ip),
        )
    )


def reset_request_context(token: Token[AuditRequestContext | None]) -> None:
    _current.reset(token)


def current_request_context() -> AuditRequestContext | None:
    return _current.get()
