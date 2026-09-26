import base64
import binascii
import hashlib
import json
import uuid
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.common.outbox import AuditLog

from .catalog import (
    RETENTION_POLICY,
    SECURITY_ACTIONS,
    SECURITY_CATEGORIES,
    AuditCategory,
    AuditResult,
    categorize,
    is_security_event,
)
from .redaction import project_metadata, redacted_key_count
from .repository import AuditQuery, AuditRepository
from .schemas import (
    AuditActor,
    AuditCatalog,
    AuditCorrelationTrace,
    AuditEventDetail,
    AuditEventPage,
    AuditEventSummary,
    AuditFilterLimits,
    AuditResource,
)

DEFAULT_WINDOW = timedelta(days=30)
MAX_WINDOW = timedelta(days=366)
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_TRACE_EVENTS = 200
CURSOR_VERSION = 1
SOURCE_FINGERPRINT_LENGTH = 16


def _result(value: str | None) -> AuditResult:
    try:
        return AuditResult(value or AuditResult.success.value)
    except ValueError:
        return AuditResult.failure


def to_summary(row: AuditLog) -> AuditEventSummary:
    result = _result(row.result)
    return AuditEventSummary(
        id=row.id,
        occurred_at=row.created_at,
        category=categorize(row.action),
        action=row.action,
        result=result,
        actor=AuditActor(id=row.actor_id, type=row.actor_type),
        resource=AuditResource(type=row.resource_type, id=row.resource_id),
        vendor_id=row.vendor_id,
        request_id=row.request_id,
        correlation_id=row.correlation_id,
        security_relevant=is_security_event(row.action, result.value),
    )


def to_detail(row: AuditLog) -> AuditEventDetail:
    return AuditEventDetail(
        **to_summary(row).model_dump(),
        metadata=project_metadata(row.metadata_json),
        metadata_withheld_keys=redacted_key_count(row.metadata_json),
        source_fingerprint=(
            row.source_ip_hash[:SOURCE_FINGERPRINT_LENGTH] if row.source_ip_hash else None
        ),
    )


def resolve_window(
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    for value in (occurred_from, occurred_to):
        if value is not None and value.utcoffset() is None:
            raise DomainError(
                "AUDIT_FILTER_INVALID",
                "occurred_from and occurred_to must include a timezone offset.",
                422,
            )
    upper = occurred_to or now or datetime.now(UTC)
    lower = occurred_from or upper - DEFAULT_WINDOW
    if lower >= upper:
        raise DomainError(
            "AUDIT_FILTER_INVALID", "occurred_from must be earlier than occurred_to.", 422
        )
    if upper - lower > MAX_WINDOW:
        raise DomainError(
            "AUDIT_FILTER_INVALID",
            f"The search window may not exceed {MAX_WINDOW.days} days.",
            422,
            fields={"max_window_days": MAX_WINDOW.days},
        )
    return lower, upper


def _fingerprint(query: AuditQuery) -> str:
    # The window is carried by the cursor itself, so a defaulted ("last 30 days")
    # window does not drift between pages.
    material = {
        key: (str(value) if value is not None else None)
        for key, value in sorted(asdict(query).items())
        if key not in {"occurred_from", "occurred_to"}
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:16]


def _aware(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.utcoffset() is None:
        raise ValueError("naive cursor timestamp")
    return parsed


def encode_cursor(row: AuditLog, query: AuditQuery) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "t": row.created_at.isoformat(),
        "i": str(row.id),
        "lo": query.occurred_from.isoformat(),
        "hi": query.occurred_to.isoformat(),
        "f": _fingerprint(query),
    }
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_cursor(
    cursor: str, query: AuditQuery
) -> tuple[AuditQuery, tuple[datetime, uuid.UUID]]:
    """Return the query pinned to the cursor's window, plus the keyset position."""
    invalid = DomainError(
        "AUDIT_CURSOR_INVALID",
        "The pagination cursor is invalid or belongs to a different search.",
        400,
    )
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        if payload.get("v") != CURSOR_VERSION or payload.get("f") != _fingerprint(query):
            raise invalid
        pinned = replace(query, occurred_from=_aware(payload["lo"]), occurred_to=_aware(payload["hi"]))
        if not pinned.occurred_from < pinned.occurred_to:
            raise invalid
        if pinned.occurred_to - pinned.occurred_from > MAX_WINDOW:
            raise invalid
        return pinned, (_aware(payload["t"]), uuid.UUID(payload["i"]))
    except DomainError:
        raise
    except (binascii.Error, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise invalid from exc


class AuditReadService:
    def __init__(self, session: AsyncSession):
        self.repo = AuditRepository(session)

    async def search(
        self,
        query: AuditQuery,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> AuditEventPage:
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise DomainError(
                "AUDIT_FILTER_INVALID", f"limit must be between 1 and {MAX_PAGE_SIZE}.", 422
            )
        if query.action is not None and query.action_prefix is not None:
            raise DomainError(
                "AUDIT_FILTER_INVALID", "Use either action or action_prefix, not both.", 422
            )
        after: tuple[datetime, uuid.UUID] | None = None
        if cursor:
            query, after = decode_cursor(cursor, query)
        rows = await self.repo.page(query, limit=limit, after=after)
        has_more = len(rows) > limit
        rows = rows[:limit]
        return AuditEventPage(
            items=[to_summary(row) for row in rows],
            next_cursor=encode_cursor(rows[-1], query) if has_more and rows else None,
            limit=limit,
            occurred_from=query.occurred_from,
            occurred_to=query.occurred_to,
        )

    async def security_activity(
        self,
        query: AuditQuery,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> AuditEventPage:
        return await self.search(replace(query, security_only=True), limit=limit, cursor=cursor)

    async def detail(self, event_id: uuid.UUID) -> AuditEventDetail:
        row = await self.repo.get(event_id)
        if row is None:
            raise DomainError("AUDIT_EVENT_NOT_FOUND", "Audit event not found.", 404)
        return to_detail(row)

    async def trace(self, correlation_id: str) -> AuditCorrelationTrace:
        rows = await self.repo.trace(correlation_id, limit=MAX_TRACE_EVENTS)
        return AuditCorrelationTrace(
            correlation_id=correlation_id,
            items=[to_detail(row) for row in rows[:MAX_TRACE_EVENTS]],
            truncated=len(rows) > MAX_TRACE_EVENTS,
        )

    @staticmethod
    def catalog() -> AuditCatalog:
        return AuditCatalog(
            categories=list(AuditCategory),
            security_categories=sorted(SECURITY_CATEGORIES),
            security_actions=sorted(SECURITY_ACTIONS),
            results=list(AuditResult),
            limits=AuditFilterLimits(
                default_window_days=DEFAULT_WINDOW.days,
                max_window_days=MAX_WINDOW.days,
                default_page_size=DEFAULT_PAGE_SIZE,
                max_page_size=MAX_PAGE_SIZE,
                max_trace_events=MAX_TRACE_EVENTS,
            ),
            retention=dict(RETENTION_POLICY),
        )
