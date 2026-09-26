import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    false,
    literal,
    not_,
    or_,
    select,
    true,
    tuple_,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.common.outbox import AuditLog

from .catalog import (
    CATEGORY_RULES,
    SECURITY_ACTIONS,
    SECURITY_CATEGORIES,
    AuditCategory,
    AuditResult,
    CategoryRule,
)


@dataclass(frozen=True, slots=True)
class AuditQuery:
    occurred_from: datetime
    occurred_to: datetime
    actor_id: uuid.UUID | None = None
    actor_type: str | None = None
    action: str | None = None
    action_prefix: str | None = None
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    result: AuditResult | None = None
    category: AuditCategory | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    vendor_id: uuid.UUID | None = None
    security_only: bool = False


def _rule_clause(rule: CategoryRule) -> ColumnElement[bool]:
    clauses: list[ColumnElement[bool]] = []
    if rule.actions:
        clauses.append(AuditLog.action.in_(sorted(rule.actions)))
    clauses.extend(AuditLog.action.startswith(prefix, autoescape=True) for prefix in rule.prefixes)
    return or_(*clauses) if clauses else false()


def category_clause(category: AuditCategory) -> ColumnElement[bool]:
    """SQL equivalent of ``catalog.categorize(action) == category`` (first match wins)."""
    earlier: list[ColumnElement[bool]] = []
    for candidate, rule in CATEGORY_RULES.items():
        if candidate == category:
            return and_(_rule_clause(rule), not_(or_(*earlier))) if earlier else _rule_clause(rule)
        earlier.append(_rule_clause(rule))
    # Residual ``domain`` category: no explicit rule matches.
    return not_(or_(*earlier)) if earlier else true()


def security_clause() -> ColumnElement[bool]:
    return or_(
        AuditLog.result != AuditResult.success.value,
        AuditLog.action.in_(sorted(SECURITY_ACTIONS)),
        *(category_clause(category) for category in sorted(SECURITY_CATEGORIES)),
    )


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def build(query: AuditQuery) -> Select[Any]:
        stmt = select(AuditLog).where(
            AuditLog.created_at >= query.occurred_from,
            AuditLog.created_at < query.occurred_to,
        )
        if query.actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == query.actor_id)
        if query.actor_type is not None:
            stmt = stmt.where(AuditLog.actor_type == query.actor_type)
        if query.action is not None:
            stmt = stmt.where(AuditLog.action == query.action)
        if query.action_prefix is not None:
            stmt = stmt.where(AuditLog.action.startswith(query.action_prefix, autoescape=True))
        if query.resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == query.resource_type)
        if query.resource_id is not None:
            stmt = stmt.where(AuditLog.resource_id == query.resource_id)
        if query.result is not None:
            stmt = stmt.where(AuditLog.result == query.result.value)
        if query.category is not None:
            stmt = stmt.where(category_clause(query.category))
        if query.correlation_id is not None:
            stmt = stmt.where(AuditLog.correlation_id == query.correlation_id)
        if query.request_id is not None:
            stmt = stmt.where(AuditLog.request_id == query.request_id)
        if query.vendor_id is not None:
            stmt = stmt.where(AuditLog.vendor_id == query.vendor_id)
        if query.security_only:
            stmt = stmt.where(security_clause())
        return stmt

    async def page(
        self,
        query: AuditQuery,
        *,
        limit: int,
        after: tuple[datetime, uuid.UUID] | None,
    ) -> list[AuditLog]:
        stmt = self.build(query)
        if after is not None:
            created_at, event_id = after
            stmt = stmt.where(
                tuple_(AuditLog.created_at, AuditLog.id)
                < tuple_(literal(created_at, AuditLog.created_at.type), literal(event_id, AuditLog.id.type))
            )
        stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1)
        return list((await self.session.scalars(stmt)).all())

    async def get(self, event_id: uuid.UUID) -> AuditLog | None:
        return await self.session.scalar(select(AuditLog).where(AuditLog.id == event_id))

    async def trace(self, correlation_id: str, *, limit: int) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.correlation_id == correlation_id)
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
            .limit(limit + 1)
        )
        return list((await self.session.scalars(stmt)).all())
