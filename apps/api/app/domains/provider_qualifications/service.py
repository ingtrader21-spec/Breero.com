import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.auth.models import User
from app.domains.common.clock import Clock, SystemClock
from app.domains.common.outbox import AuditLog
from app.domains.workforce.models import Vendor
from app.domains.workforce.provider_scope import provider_vendor, provider_worker

from .models import (
    ProviderQualification,
    QualificationReviewStatus,
    QualificationStatus,
)
from .schemas import (
    EXPIRY_REQUIRED_TYPES,
    EvidenceStorageRead,
    QualificationCreate,
    QualificationList,
    QualificationRead,
    QualificationReviewDecision,
    QualificationUpdate,
)

MAX_ACTIVE_QUALIFICATIONS = 200
EVIDENCE_STORAGE = EvidenceStorageRead(
    upload_enabled=False,
    reason=(
        "Governed document storage is not configured. Record metadata and an opaque "
        "evidence reference only; binary uploads are refused."
    ),
)
EDITABLE_REVIEW_STATES = frozenset(
    {
        QualificationReviewStatus.NOT_SUBMITTED,
        QualificationReviewStatus.REJECTED,
        QualificationReviewStatus.INFORMATION_REQUESTED,
    }
)


def to_read(record: ProviderQualification, today: date) -> QualificationRead:
    result = QualificationRead.model_validate(record)
    result.is_expired = bool(record.expires_on and record.expires_on < today)
    return result


class ProviderQualificationService:
    """Provider-owned qualification metadata with a reviewer decision boundary."""

    def __init__(self, session: AsyncSession, *, clock: Clock | None = None) -> None:
        self.session = session
        self.clock = clock or SystemClock()

    def _today(self) -> date:
        return self.clock.now().date()

    async def list_qualifications(
        self,
        user: User,
        *,
        worker_id: uuid.UUID | None = None,
        include_withdrawn: bool = False,
    ) -> QualificationList:
        vendor = await provider_vendor(self.session, user)
        if worker_id:
            await provider_worker(self.session, vendor, worker_id)
        query = select(ProviderQualification).where(ProviderQualification.vendor_id == vendor.id)
        if worker_id:
            query = query.where(ProviderQualification.worker_id == worker_id)
        if not include_withdrawn:
            query = query.where(ProviderQualification.status != QualificationStatus.WITHDRAWN)
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(
                        ProviderQualification.created_at.desc(), ProviderQualification.id
                    )
                )
            ).all()
        )
        today = self._today()
        return QualificationList(
            items=[to_read(item, today) for item in rows],
            total=len(rows),
            evidence_storage=EVIDENCE_STORAGE,
        )

    async def get(self, qualification_id: uuid.UUID, user: User) -> QualificationRead:
        vendor = await provider_vendor(self.session, user)
        record = await self._owned(vendor.id, qualification_id, lock=False)
        return to_read(record, self._today())

    async def create(
        self,
        user: User,
        command: QualificationCreate,
        *,
        correlation_id: str | None = None,
    ) -> QualificationRead:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        if command.worker_id:
            await provider_worker(self.session, vendor, command.worker_id)
        count = await self.session.scalar(
            select(func.count())
            .select_from(ProviderQualification)
            .where(
                ProviderQualification.vendor_id == vendor.id,
                ProviderQualification.status != QualificationStatus.WITHDRAWN,
            )
        )
        if int(count or 0) >= MAX_ACTIVE_QUALIFICATIONS:
            raise DomainError(
                "QUALIFICATION_LIMIT_REACHED",
                f"A provider may keep at most {MAX_ACTIVE_QUALIFICATIONS} qualifications.",
                409,
            )
        record = ProviderQualification(
            vendor_id=vendor.id,
            worker_id=command.worker_id,
            qualification_type=command.qualification_type,
            title=command.title,
            issuer=command.issuer,
            jurisdiction=command.jurisdiction,
            reference_last4=command.reference_last4,
            issued_on=command.issued_on,
            expires_on=command.expires_on,
            evidence_reference=command.evidence_reference,
            status=QualificationStatus.DRAFT,
            review_status=QualificationReviewStatus.NOT_SUBMITTED,
            version=1,
            created_by=user.id,
        )
        self.session.add(record)
        await self.session.flush()
        self._audit(user, "provider.qualification.create", record, vendor, correlation_id,
                    {"qualification_type": record.qualification_type.value})
        await self.session.commit()
        await self.session.refresh(record)
        return to_read(record, self._today())

    async def update(
        self,
        qualification_id: uuid.UUID,
        user: User,
        command: QualificationUpdate,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> QualificationRead:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        record = await self._owned(vendor.id, qualification_id, lock=True)
        self._require_version(record, expected_version)
        self._require_editable(record)
        changes = command.model_dump(exclude_unset=True)
        issued_on = changes.get("issued_on", record.issued_on)
        expires_on = changes.get("expires_on", record.expires_on)
        if issued_on and expires_on and issued_on > expires_on:
            raise DomainError(
                "INVALID_QUALIFICATION", "issued_on must not be after expires_on.", 422
            )
        for field, value in changes.items():
            setattr(record, field, value)
        # Editing a returned submission turns it back into a draft that must be
        # resubmitted; the previous reviewer note stays visible until then.
        record.status = QualificationStatus.DRAFT
        record.review_status = QualificationReviewStatus.NOT_SUBMITTED
        record.version += 1
        self._audit(user, "provider.qualification.update", record, vendor, correlation_id,
                    {"fields": sorted(changes)})
        await self.session.commit()
        await self.session.refresh(record)
        return to_read(record, self._today())

    async def submit(
        self,
        qualification_id: uuid.UUID,
        user: User,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> QualificationRead:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        record = await self._owned(vendor.id, qualification_id, lock=True)
        self._require_version(record, expected_version)
        if record.status != QualificationStatus.DRAFT:
            raise DomainError(
                "QUALIFICATION_NOT_SUBMITTABLE",
                "Only draft qualifications can be submitted for review.",
                409,
            )
        if record.qualification_type in EXPIRY_REQUIRED_TYPES and not record.expires_on:
            raise DomainError(
                "QUALIFICATION_EXPIRY_REQUIRED",
                "Licenses and insurance require an expiry date.",
                422,
            )
        if record.expires_on and record.expires_on < self._today():
            raise DomainError(
                "QUALIFICATION_EXPIRED",
                "Expired qualifications cannot be submitted.",
                422,
            )
        now = self.clock.now()
        record.status = QualificationStatus.SUBMITTED
        record.review_status = QualificationReviewStatus.PENDING_REVIEW
        record.submitted_at = now
        record.review_reason = None
        record.reviewed_by = None
        record.reviewed_at = None
        record.version += 1
        self._audit(user, "provider.qualification.submit", record, vendor, correlation_id, {})
        await self.session.commit()
        await self.session.refresh(record)
        return to_read(record, self._today())

    async def withdraw(
        self,
        qualification_id: uuid.UUID,
        user: User,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> None:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        record = await self._owned(vendor.id, qualification_id, lock=True)
        self._require_version(record, expected_version)
        if record.status == QualificationStatus.WITHDRAWN:
            return
        record.status = QualificationStatus.WITHDRAWN
        record.version += 1
        self._audit(user, "provider.qualification.withdraw", record, vendor, correlation_id, {})
        await self.session.commit()

    async def reject_evidence_upload(
        self, qualification_id: uuid.UUID, user: User
    ) -> None:
        """Fail closed: no governed binary store exists for provider documents."""

        vendor = await provider_vendor(self.session, user, write=True)
        await self._owned(vendor.id, qualification_id, lock=False)
        raise DomainError(
            "EVIDENCE_STORAGE_NOT_CONFIGURED",
            EVIDENCE_STORAGE.reason,
            503,
        )

    async def review(
        self,
        qualification_id: uuid.UUID,
        actor: User,
        decision: QualificationReviewDecision,
        *,
        correlation_id: str | None = None,
    ) -> QualificationRead:
        record = await self.session.scalar(
            select(ProviderQualification)
            .where(ProviderQualification.id == qualification_id)
            .with_for_update()
        )
        if not record:
            raise DomainError("QUALIFICATION_NOT_FOUND", "Qualification not found.", 404)
        if (
            record.status != QualificationStatus.SUBMITTED
            or record.review_status != QualificationReviewStatus.PENDING_REVIEW
        ):
            raise DomainError(
                "QUALIFICATION_NOT_PENDING",
                "Only qualifications pending review can be decided.",
                409,
            )
        record.review_status = QualificationReviewStatus(decision.decision)
        record.review_reason = decision.reason.strip()
        record.reviewed_by = actor.id
        record.reviewed_at = self.clock.now()
        record.version += 1
        self.session.add(
            AuditLog(
                actor_id=actor.id,
                actor_type="user",
                action="provider.qualification.review",
                resource_type="provider_qualification",
                resource_id=record.id,
                metadata_json={
                    "vendor_id": str(record.vendor_id),
                    "decision": decision.decision,
                    "reason": record.review_reason,
                    "correlation_id": correlation_id,
                },
                created_at=self.clock.now(),
            )
        )
        await self.session.commit()
        await self.session.refresh(record)
        return to_read(record, self._today())

    async def _owned(
        self, vendor_id: uuid.UUID, qualification_id: uuid.UUID, *, lock: bool
    ) -> ProviderQualification:
        query = select(ProviderQualification).where(
            ProviderQualification.id == qualification_id,
            ProviderQualification.vendor_id == vendor_id,
        )
        if lock:
            query = query.with_for_update()
        record = await self.session.scalar(query)
        if not record:
            raise DomainError("QUALIFICATION_NOT_FOUND", "Qualification not found.", 404)
        return record

    @staticmethod
    def _require_version(record: ProviderQualification, expected: int) -> None:
        if record.version != expected:
            raise DomainError(
                "VERSION_CONFLICT",
                "Qualification changed since it was loaded.",
                409,
                fields={"current_version": record.version},
            )

    @staticmethod
    def _require_editable(record: ProviderQualification) -> None:
        if record.status == QualificationStatus.WITHDRAWN or (
            record.review_status not in EDITABLE_REVIEW_STATES
        ):
            raise DomainError(
                "QUALIFICATION_LOCKED",
                "Qualifications pending review, approved, or withdrawn cannot be edited.",
                409,
            )

    def _audit(
        self,
        actor: User,
        action: str,
        record: ProviderQualification,
        vendor: Vendor,
        correlation_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor.id,
                actor_type="provider",
                action=action,
                resource_type="provider_qualification",
                resource_id=record.id,
                metadata_json={
                    "vendor_id": str(vendor.id),
                    "version": record.version,
                    "correlation_id": correlation_id,
                    **metadata,
                },
                created_at=self.clock.now(),
            )
        )
