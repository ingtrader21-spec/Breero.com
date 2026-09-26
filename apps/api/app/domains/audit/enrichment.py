"""Insert-time enrichment for every ``AuditLog`` row, whichever domain wrote it."""

import uuid
from typing import Any

from sqlalchemy import event

from app.domains.common.outbox import AuditLog

from .catalog import AuditResult
from .context import current_request_context
from .redaction import scrub_for_storage


def _vendor_context(target: AuditLog) -> uuid.UUID | None:
    if target.resource_type == "vendor":
        return target.resource_id
    raw = (target.metadata_json or {}).get("vendor_id")
    if isinstance(raw, uuid.UUID):
        return raw
    if isinstance(raw, str):
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
    return None


def enrich(target: AuditLog) -> None:
    """Fill trace/tenant context and scrub secrets; explicit values always win."""
    if target.result is None:
        target.result = AuditResult.success.value
    context = current_request_context()
    if context is not None:
        if target.request_id is None:
            target.request_id = context.request_id
        if target.correlation_id is None:
            target.correlation_id = context.correlation_id
        if target.source_ip_hash is None:
            target.source_ip_hash = context.source_ip_hash
    if target.vendor_id is None:
        target.vendor_id = _vendor_context(target)
    target.metadata_json = scrub_for_storage(target.metadata_json or {})


@event.listens_for(AuditLog, "before_insert")
def _before_insert(_mapper: Any, _connection: Any, target: AuditLog) -> None:
    enrich(target)
