"""Emission helpers for events that are not part of a committed domain mutation."""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.common.outbox import AuditLog

from .catalog import ACCESS_DENIED_ACTION, AuditResult

logger = structlog.get_logger()


async def record_access_denied(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    required: Iterable[str],
    reason_code: str,
    brand_key: str | None = None,
) -> None:
    """Persist a failed-authorization event without ever changing the 403 outcome.

    Called from authorization gates before any endpoint work, so the session holds no
    pending domain changes; the row is committed on its own. Failures are logged and
    swallowed because an audit outage must not turn a denial into a 500 or an allow.
    """
    try:
        session.add(
            AuditLog(
                actor_id=actor_id,
                actor_type="user",
                action=ACCESS_DENIED_ACTION,
                resource_type="user",
                resource_id=actor_id,
                result=AuditResult.denied.value,
                metadata_json={
                    "required": sorted(str(item) for item in required)[:20],
                    "reason_code": reason_code,
                    "brand_key": brand_key,
                },
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    except Exception as exc:
        logger.warning("audit_access_denied_not_recorded", error=type(exc).__name__)
        try:
            await session.rollback()
        except Exception:
            pass
