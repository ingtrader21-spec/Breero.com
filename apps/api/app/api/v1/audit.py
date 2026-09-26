"""Admin-only audit read model. Read-only: no route here mutates or deletes audit rows."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.audit.catalog import AuditCategory, AuditResult
from app.domains.audit.repository import AuditQuery
from app.domains.audit.schemas import (
    AuditCatalog,
    AuditCorrelationTrace,
    AuditEventDetail,
    AuditEventPage,
)
from app.domains.audit.service import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    AuditReadService,
    resolve_window,
)
from app.domains.auth.dependencies import require_permissions
from app.domains.auth.models import User

router = APIRouter()
# Provider, worker, customer and non-admin staff roles never hold this permission.
can_read_audit = require_permissions("admin.audit.read")

TRACE_ID = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
TraceId = Annotated[str, Path(pattern=TRACE_ID, max_length=128)]
ERROR_RESPONSES: dict[int | str, dict] = {
    400: {"description": "Invalid pagination cursor (AUDIT_CURSOR_INVALID)."},
    401: {"description": "Authentication required."},
    403: {"description": "Missing admin.audit.read permission; the denial is audited."},
    422: {"description": "Invalid or unbounded filters (AUDIT_FILTER_INVALID)."},
}


def audit_query(
    occurred_from: Annotated[
        datetime | None,
        Query(description="Inclusive lower bound (timezone required). Defaults to occurred_to - 30 days."),
    ] = None,
    occurred_to: Annotated[
        datetime | None,
        Query(description="Exclusive upper bound (timezone required). Defaults to now."),
    ] = None,
    actor_id: uuid.UUID | None = None,
    actor_type: Annotated[str | None, Query(pattern=r"^[a-z_]{1,32}$")] = None,
    action: Annotated[str | None, Query(pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)*$", max_length=120)] = None,
    action_prefix: Annotated[
        str | None,
        Query(pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)*\.?$", max_length=120),
    ] = None,
    resource_type: Annotated[str | None, Query(pattern=r"^[a-z_]{1,80}$")] = None,
    resource_id: uuid.UUID | None = None,
    result: AuditResult | None = None,
    category: Annotated[AuditCategory | None, Query(description="Event type / category.")] = None,
    correlation_id: Annotated[str | None, Query(pattern=TRACE_ID, max_length=128)] = None,
    request_id: Annotated[str | None, Query(pattern=TRACE_ID, max_length=128)] = None,
    vendor_id: uuid.UUID | None = None,
) -> AuditQuery:
    lower, upper = resolve_window(occurred_from, occurred_to)
    return AuditQuery(
        occurred_from=lower,
        occurred_to=upper,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        action_prefix=action_prefix,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        category=category,
        correlation_id=correlation_id,
        request_id=request_id,
        vendor_id=vendor_id,
    )


PageLimit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Cursor = Annotated[str | None, Query(min_length=1, max_length=512)]


@router.get(
    "/events",
    response_model=AuditEventPage,
    responses=ERROR_RESPONSES,
)
async def list_audit_events(
    _: Annotated[User, Depends(can_read_audit)],
    session: Annotated[AsyncSession, Depends(get_db)],
    query: Annotated[AuditQuery, Depends(audit_query)],
    limit: PageLimit = DEFAULT_PAGE_SIZE,
    cursor: Cursor = None,
) -> AuditEventPage:
    return await AuditReadService(session).search(query, limit=limit, cursor=cursor)


@router.get(
    "/security-events",
    response_model=AuditEventPage,
    responses=ERROR_RESPONSES,
)
async def list_security_events(
    _: Annotated[User, Depends(can_read_audit)],
    session: Annotated[AsyncSession, Depends(get_db)],
    query: Annotated[AuditQuery, Depends(audit_query)],
    limit: PageLimit = DEFAULT_PAGE_SIZE,
    cursor: Cursor = None,
) -> AuditEventPage:
    return await AuditReadService(session).security_activity(query, limit=limit, cursor=cursor)


@router.get(
    "/events/{event_id}",
    response_model=AuditEventDetail,
    responses={**ERROR_RESPONSES, 404: {"description": "AUDIT_EVENT_NOT_FOUND"}},
)
async def get_audit_event(
    event_id: uuid.UUID,
    _: Annotated[User, Depends(can_read_audit)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditEventDetail:
    return await AuditReadService(session).detail(event_id)


@router.get(
    "/correlations/{correlation_id}",
    response_model=AuditCorrelationTrace,
    responses=ERROR_RESPONSES,
)
async def trace_correlation(
    correlation_id: TraceId,
    _: Annotated[User, Depends(can_read_audit)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditCorrelationTrace:
    return await AuditReadService(session).trace(correlation_id)


@router.get(
    "/catalog",
    response_model=AuditCatalog,
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)
async def audit_catalog(_: Annotated[User, Depends(can_read_audit)]) -> AuditCatalog:
    return AuditReadService.catalog()
