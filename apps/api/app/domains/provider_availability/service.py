import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.auth.models import User
from app.domains.common.clock import Clock, SystemClock
from app.domains.common.outbox import AuditLog
from app.domains.workforce.models import Vendor
from app.domains.workforce.provider_scope import provider_vendor, provider_worker

from .expansion import Blackout, RuleWindow, expand, windows_overlap
from .models import ProviderAvailabilityRule, ProviderBlackoutPeriod
from .schemas import (
    MAX_PREVIEW_LENGTH,
    AvailabilityInterval,
    AvailabilityPreviewRead,
    AvailabilityRuleCreate,
    AvailabilityRuleRead,
    AvailabilityRuleUpdate,
    BlackoutPeriodCreate,
    BlackoutPeriodRead,
    BlackoutPeriodUpdate,
    ProviderAvailabilityRead,
    validate_blackout_values,
    validate_rule_values,
)

MAX_ACTIVE_RULES = 200
MAX_ACTIVE_BLACKOUTS = 500


def _rule_window(record: ProviderAvailabilityRule) -> RuleWindow:
    return RuleWindow(
        worker_id=record.worker_id,
        weekday=record.weekday,
        start_time=record.start_time,
        end_time=record.end_time,
        timezone=record.timezone,
        valid_from=record.valid_from,
        valid_until=record.valid_until,
    )


class ProviderAvailabilityService:
    """Provider-owned availability declarations, scoped to the principal's vendor."""

    def __init__(self, session: AsyncSession, *, clock: Clock | None = None) -> None:
        self.session = session
        self.clock = clock or SystemClock()

    async def snapshot(
        self,
        user: User,
        *,
        worker_id: uuid.UUID | None = None,
    ) -> ProviderAvailabilityRead:
        vendor = await provider_vendor(self.session, user)
        if worker_id:
            await provider_worker(self.session, vendor, worker_id)
        rules = await self._active_rules(vendor.id, worker_id=worker_id)
        blackouts = await self._active_blackouts(vendor.id, worker_id=worker_id)
        return ProviderAvailabilityRead(
            rules=[AvailabilityRuleRead.model_validate(item) for item in rules],
            blackouts=[BlackoutPeriodRead.model_validate(item) for item in blackouts],
        )

    async def create_rule(
        self,
        user: User,
        command: AvailabilityRuleCreate,
        *,
        correlation_id: str | None = None,
    ) -> AvailabilityRuleRead:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        if command.worker_id:
            await provider_worker(self.session, vendor, command.worker_id)
        await self._require_capacity(ProviderAvailabilityRule, vendor.id, MAX_ACTIVE_RULES)
        candidate = RuleWindow(
            worker_id=command.worker_id,
            weekday=command.weekday,
            start_time=command.start_time,
            end_time=command.end_time,
            timezone=command.timezone,
            valid_from=command.valid_from,
            valid_until=command.valid_until,
        )
        await self._require_no_conflict(vendor, candidate, exclude_id=None)
        record = ProviderAvailabilityRule(
            vendor_id=vendor.id,
            worker_id=command.worker_id,
            weekday=command.weekday,
            start_time=command.start_time,
            end_time=command.end_time,
            timezone=command.timezone,
            valid_from=command.valid_from,
            valid_until=command.valid_until,
            active=True,
            version=1,
            created_by=user.id,
        )
        self.session.add(record)
        await self.session.flush()
        self._audit(user, "provider.availability.rule.create", "provider_availability_rule",
                    record.id, vendor, correlation_id, {"weekday": record.weekday})
        await self.session.commit()
        await self.session.refresh(record)
        return AvailabilityRuleRead.model_validate(record)

    async def update_rule(
        self,
        rule_id: uuid.UUID,
        user: User,
        command: AvailabilityRuleUpdate,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> AvailabilityRuleRead:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        record = await self._rule(vendor.id, rule_id)
        self._require_version(record.version, expected_version, "availability rule")
        changes = command.model_dump(exclude_unset=True)
        merged = {
            field: changes.get(field, getattr(record, field))
            for field in (
                "weekday",
                "start_time",
                "end_time",
                "timezone",
                "valid_from",
                "valid_until",
            )
        }
        try:
            validate_rule_values(
                start_time=merged["start_time"],
                end_time=merged["end_time"],
                valid_from=merged["valid_from"],
                valid_until=merged["valid_until"],
            )
        except ValueError as exc:
            raise DomainError("INVALID_AVAILABILITY", str(exc), 422) from exc
        candidate = RuleWindow(worker_id=record.worker_id, **merged)
        await self._require_no_conflict(vendor, candidate, exclude_id=record.id)
        for field, value in merged.items():
            setattr(record, field, value)
        record.version += 1
        self._audit(user, "provider.availability.rule.update", "provider_availability_rule",
                    record.id, vendor, correlation_id, {"version": record.version})
        await self.session.commit()
        await self.session.refresh(record)
        return AvailabilityRuleRead.model_validate(record)

    async def delete_rule(
        self,
        rule_id: uuid.UUID,
        user: User,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> None:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        record = await self._rule(vendor.id, rule_id)
        self._require_version(record.version, expected_version, "availability rule")
        record.active = False
        record.version += 1
        self._audit(user, "provider.availability.rule.delete", "provider_availability_rule",
                    record.id, vendor, correlation_id, {"version": record.version})
        await self.session.commit()

    async def create_blackout(
        self,
        user: User,
        command: BlackoutPeriodCreate,
        *,
        correlation_id: str | None = None,
    ) -> BlackoutPeriodRead:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        if command.worker_id:
            await provider_worker(self.session, vendor, command.worker_id)
        await self._require_capacity(ProviderBlackoutPeriod, vendor.id, MAX_ACTIVE_BLACKOUTS)
        record = ProviderBlackoutPeriod(
            vendor_id=vendor.id,
            worker_id=command.worker_id,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            timezone=command.timezone,
            reason=command.reason,
            active=True,
            version=1,
            created_by=user.id,
        )
        self.session.add(record)
        await self.session.flush()
        self._audit(user, "provider.availability.blackout.create", "provider_blackout_period",
                    record.id, vendor, correlation_id, {})
        await self.session.commit()
        await self.session.refresh(record)
        return BlackoutPeriodRead.model_validate(record)

    async def update_blackout(
        self,
        blackout_id: uuid.UUID,
        user: User,
        command: BlackoutPeriodUpdate,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> BlackoutPeriodRead:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        record = await self._blackout(vendor.id, blackout_id)
        self._require_version(record.version, expected_version, "blackout period")
        changes = command.model_dump(exclude_unset=True)
        starts_at = changes.get("starts_at", record.starts_at)
        ends_at = changes.get("ends_at", record.ends_at)
        try:
            validate_blackout_values(starts_at, ends_at)
        except ValueError as exc:
            raise DomainError("INVALID_BLACKOUT", str(exc), 422) from exc
        for field, value in changes.items():
            setattr(record, field, value)
        record.version += 1
        self._audit(user, "provider.availability.blackout.update", "provider_blackout_period",
                    record.id, vendor, correlation_id, {"version": record.version})
        await self.session.commit()
        await self.session.refresh(record)
        return BlackoutPeriodRead.model_validate(record)

    async def delete_blackout(
        self,
        blackout_id: uuid.UUID,
        user: User,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> None:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        record = await self._blackout(vendor.id, blackout_id)
        self._require_version(record.version, expected_version, "blackout period")
        record.active = False
        record.version += 1
        self._audit(user, "provider.availability.blackout.delete", "provider_blackout_period",
                    record.id, vendor, correlation_id, {"version": record.version})
        await self.session.commit()

    async def preview(
        self,
        user: User,
        *,
        starts_at: datetime,
        ends_at: datetime,
        worker_id: uuid.UUID | None = None,
    ) -> AvailabilityPreviewRead:
        if starts_at.tzinfo is None or ends_at.tzinfo is None:
            raise DomainError(
                "INVALID_PREVIEW_WINDOW", "Preview bounds must include a UTC offset.", 422
            )
        if starts_at >= ends_at or ends_at - starts_at > MAX_PREVIEW_LENGTH:
            raise DomainError(
                "INVALID_PREVIEW_WINDOW",
                "Preview window must be positive and at most 31 days.",
                422,
            )
        vendor = await provider_vendor(self.session, user)
        if worker_id:
            await provider_worker(self.session, vendor, worker_id)
        rules = await self._active_rules(vendor.id, worker_id=worker_id)
        blackouts = await self._active_blackouts(vendor.id, worker_id=worker_id)
        intervals = expand(
            [_rule_window(item) for item in rules],
            [
                Blackout(worker_id=item.worker_id, starts_at=item.starts_at, ends_at=item.ends_at)
                for item in blackouts
            ],
            starts_at,
            ends_at,
        )
        return AvailabilityPreviewRead(
            window_start=starts_at,
            window_end=ends_at,
            intervals=[
                AvailabilityInterval(
                    worker_id=item.worker_id,
                    starts_at=item.starts_at,
                    ends_at=item.ends_at,
                    timezone=item.timezone,
                )
                for item in intervals
            ],
        )

    async def _active_rules(
        self, vendor_id: uuid.UUID, *, worker_id: uuid.UUID | None
    ) -> list[ProviderAvailabilityRule]:
        query = select(ProviderAvailabilityRule).where(
            ProviderAvailabilityRule.vendor_id == vendor_id,
            ProviderAvailabilityRule.active.is_(True),
        )
        if worker_id:
            query = query.where(
                (ProviderAvailabilityRule.worker_id == worker_id)
                | ProviderAvailabilityRule.worker_id.is_(None)
            )
        query = query.order_by(
            ProviderAvailabilityRule.weekday,
            ProviderAvailabilityRule.start_time,
            ProviderAvailabilityRule.id,
        )
        return list((await self.session.scalars(query)).all())

    async def _active_blackouts(
        self, vendor_id: uuid.UUID, *, worker_id: uuid.UUID | None
    ) -> list[ProviderBlackoutPeriod]:
        query = select(ProviderBlackoutPeriod).where(
            ProviderBlackoutPeriod.vendor_id == vendor_id,
            ProviderBlackoutPeriod.active.is_(True),
        )
        if worker_id:
            query = query.where(
                (ProviderBlackoutPeriod.worker_id == worker_id)
                | ProviderBlackoutPeriod.worker_id.is_(None)
            )
        query = query.order_by(ProviderBlackoutPeriod.starts_at, ProviderBlackoutPeriod.id)
        return list((await self.session.scalars(query)).all())

    async def _rule(self, vendor_id: uuid.UUID, rule_id: uuid.UUID) -> ProviderAvailabilityRule:
        record = await self.session.scalar(
            select(ProviderAvailabilityRule)
            .where(
                ProviderAvailabilityRule.id == rule_id,
                ProviderAvailabilityRule.vendor_id == vendor_id,
                ProviderAvailabilityRule.active.is_(True),
            )
            .with_for_update()
        )
        if not record:
            raise DomainError(
                "AVAILABILITY_RULE_NOT_FOUND", "Availability rule not found.", 404
            )
        return record

    async def _blackout(
        self, vendor_id: uuid.UUID, blackout_id: uuid.UUID
    ) -> ProviderBlackoutPeriod:
        record = await self.session.scalar(
            select(ProviderBlackoutPeriod)
            .where(
                ProviderBlackoutPeriod.id == blackout_id,
                ProviderBlackoutPeriod.vendor_id == vendor_id,
                ProviderBlackoutPeriod.active.is_(True),
            )
            .with_for_update()
        )
        if not record:
            raise DomainError("BLACKOUT_NOT_FOUND", "Blackout period not found.", 404)
        return record

    async def _require_capacity(
        self,
        model: type[ProviderAvailabilityRule] | type[ProviderBlackoutPeriod],
        vendor_id: uuid.UUID,
        limit: int,
    ) -> None:
        count = await self.session.scalar(
            select(func.count())
            .select_from(model)
            .where(model.vendor_id == vendor_id, model.active.is_(True))
        )
        if int(count or 0) >= limit:
            raise DomainError(
                "AVAILABILITY_LIMIT_REACHED",
                f"A provider may keep at most {limit} active entries of this kind.",
                409,
            )

    async def _require_no_conflict(
        self,
        vendor: Vendor,
        candidate: RuleWindow,
        *,
        exclude_id: uuid.UUID | None,
    ) -> None:
        query = select(ProviderAvailabilityRule).where(
            ProviderAvailabilityRule.vendor_id == vendor.id,
            ProviderAvailabilityRule.active.is_(True),
        )
        if candidate.worker_id is None:
            query = query.where(ProviderAvailabilityRule.worker_id.is_(None))
        else:
            query = query.where(ProviderAvailabilityRule.worker_id == candidate.worker_id)
        if exclude_id:
            query = query.where(ProviderAvailabilityRule.id != exclude_id)
        existing = list((await self.session.scalars(query)).all())
        for item in existing:
            if item.timezone != candidate.timezone:
                raise DomainError(
                    "AVAILABILITY_TIMEZONE_CONFLICT",
                    "All weekly windows for the same provider or professional must use "
                    "one timezone.",
                    409,
                    fields={"timezone": item.timezone},
                )
            if windows_overlap(_rule_window(item), candidate):
                raise DomainError(
                    "AVAILABILITY_OVERLAP",
                    "This window overlaps an existing weekly window.",
                    409,
                    fields={"conflicting_rule_id": str(item.id)},
                )

    @staticmethod
    def _require_version(current: int, expected: int, resource_name: str) -> None:
        if current != expected:
            raise DomainError(
                "VERSION_CONFLICT",
                f"{resource_name.capitalize()} changed since it was loaded.",
                409,
                fields={"current_version": current},
            )

    def _audit(
        self,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        vendor: Vendor,
        correlation_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor.id,
                actor_type="provider",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_json={
                    "vendor_id": str(vendor.id),
                    "correlation_id": correlation_id,
                    **metadata,
                },
                created_at=self.clock.now(),
            )
        )
