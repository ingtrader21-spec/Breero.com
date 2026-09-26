import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import DomainError
from app.domains.auth.models import (
    AccessAssignment,
    AccessProfile,
    AccessRole,
    Department,
    EmailVerificationToken,
    TenantScope,
    User,
    UserRole,
)
from app.domains.auth.repository import UserRepository
from app.domains.auth.security import hash_password, hash_token, new_opaque_token
from app.domains.auth.service import AuthService
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.provider_availability.models import ProviderAvailabilityRule
from app.domains.provider_catalog.models import (
    ApprovalStatus,
    ProviderService,
    ProviderSkill,
)
from app.domains.provider_qualifications.models import (
    ProviderQualification,
    QualificationReviewStatus,
    QualificationStatus,
    QualificationType,
)
from app.domains.workforce.models import (
    ProviderApplication,
    ProviderApplicationStatus,
    Vendor,
    VendorStatus,
    Worker,
    WorkerStatus,
)
from app.domains.workforce.schemas import (
    ProviderApplicationDecision,
    ProviderApplicationList,
    ProviderApplicationRead,
    ProviderOnboardingChecklist,
    ProviderOnboardingUpdate,
    ProviderProfileUpdate,
    ProviderRegisterRequest,
    ProviderRegistrationResponse,
    VendorRead,
)

EDITABLE_APPLICATION_STATUSES = frozenset(
    {
        ProviderApplicationStatus.DRAFT,
        ProviderApplicationStatus.INFORMATION_REQUESTED,
    }
)
EVIDENCED_REVIEW_STATUSES = (
    QualificationReviewStatus.PENDING_REVIEW,
    QualificationReviewStatus.APPROVED,
)

REQUIRED_APPLICATION_FIELDS = (
    "identity",
    "business",
    "contact_details",
    "services",
    "skills",
    "service_areas",
    "postal_codes",
    "availability",
    "capacity",
    "licenses",
    "insurance",
    "compliance_documents",
)


class ProviderRegistrationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    async def register(
        self,
        data: ProviderRegisterRequest,
        *,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> ProviderRegistrationResponse:
        email = str(data.email).strip().lower()
        if await self.users.by_email(email):
            raise HTTPException(409, "Email already registered")

        try:
            user = await self.users.add(
                User(
                    email=email,
                    full_name=data.full_name.strip(),
                    password_hash=await hash_password(data.password),
                    role=UserRole.vendor_admin,
                    is_active=True,
                    email_verified=False,
                )
            )
            vendor = Vendor(
                legal_name=data.legal_name.strip(),
                display_name=data.display_name.strip(),
                email=email,
                phone=data.phone.strip(),
                owner_user_id=user.id,
                status=VendorStatus.PENDING,
                capabilities=[],
                service_radius_meters=40000,
            )
            self.session.add(vendor)
            await self.session.flush()

            parts = data.full_name.strip().split(maxsplit=1)
            self.session.add(
                Worker(
                    vendor_id=vendor.id,
                    user_id=user.id,
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else "",
                    email=email,
                    phone=data.phone.strip(),
                    status=WorkerStatus.INVITED,
                    skills=[],
                    available=False,
                )
            )
            self.session.add(AccessProfile(user_id=user.id, brand_key="breero"))
            self.session.add(
                AccessAssignment(
                    user_id=user.id,
                    brand_key="breero",
                    role_key=AccessRole.vendor_admin.value,
                    department=Department.provider.value,
                    tenant_scope=TenantScope.vendor.value,
                    vendor_id=vendor.id,
                    active=True,
                    is_primary=True,
                )
            )
            application = ProviderApplication(
                vendor_id=vendor.id,
                status=ProviderApplicationStatus.DRAFT,
                identity={"full_name": data.full_name.strip()},
                business={
                    "legal_name": data.legal_name.strip(),
                    "display_name": data.display_name.strip(),
                },
                contact_details={"email": email, "phone": data.phone.strip()},
            )
            self.session.add(application)

            verification_token = new_opaque_token()
            self.session.add(
                EmailVerificationToken(
                    user_id=user.id,
                    token_hash=hash_token(verification_token),
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
            )
            deliverable = (
                settings.email_enabled
                and settings.live_email_delivery
                and settings.transactional_email_mode != "disabled"
            )
            self.session.add(
                IntegrationEvent(
                    aggregate_type="user",
                    aggregate_id=user.id,
                    event_type="email_verification_requested",
                    idempotency_key=f"provider-email-verification:{user.id}",
                    payload={
                        "user_id": str(user.id),
                        "email": email,
                        "token": verification_token,
                    },
                    status=(
                        EventStatus.PENDING
                        if deliverable
                        else EventStatus.PENDING_CONFIGURATION
                    ),
                    attempts=0,
                    available_at=datetime.now(UTC),
                )
            )
            token_response = await AuthService(self.session)._tokens(
                user,
                user_agent,
                ip,
            )
            self.session.add(
                AuditLog(
                    actor_id=user.id,
                    actor_type="self",
                    action="provider.register",
                    resource_type="vendor",
                    resource_id=vendor.id,
                    metadata_json={
                        "application_status": ProviderApplicationStatus.DRAFT.value
                    },
                    created_at=datetime.now(UTC),
                )
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Provider account already exists") from exc

        await self.session.refresh(vendor)
        await self.session.refresh(application)
        return ProviderRegistrationResponse(
            user_id=user.id,
            vendor=VendorRead.model_validate(vendor),
            application=ProviderApplicationRead.model_validate(application),
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            expires_in=token_response.expires_in,
            refresh_expires_in=token_response.refresh_expires_in,
        )


class ProviderOnboardingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _owned_vendor(self, user: User, *, lock: bool = False) -> Vendor:
        query = select(Vendor).where(Vendor.owner_user_id == user.id)
        if lock:
            query = query.with_for_update()
        vendor = await self.session.scalar(query)
        if not vendor:
            raise HTTPException(
                403,
                "Account does not administer a provider organization",
            )
        return vendor

    async def _application_for_vendor(
        self,
        vendor_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> ProviderApplication:
        query = select(ProviderApplication).where(
            ProviderApplication.vendor_id == vendor_id
        )
        if lock:
            query = query.with_for_update()
        application = await self.session.scalar(query)
        if not application:
            raise HTTPException(404, "Provider application not found")
        return application

    async def profile(self, user: User) -> Vendor:
        return await self._owned_vendor(user)

    async def update_profile(
        self,
        user: User,
        data: ProviderProfileUpdate,
    ) -> Vendor:
        vendor = await self._owned_vendor(user, lock=True)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(vendor, field, value)
        self._audit(user.id, "provider.profile.update", "vendor", vendor.id, {})
        await self.session.commit()
        await self.session.refresh(vendor)
        return vendor

    async def onboarding(self, user: User) -> ProviderApplication:
        vendor = await self._owned_vendor(user)
        return await self._application_for_vendor(vendor.id)

    async def checklist(self, user: User) -> ProviderOnboardingChecklist:
        """Read-only submission readiness, including provider-owned domain records."""

        vendor = await self._owned_vendor(user)
        application = await self._application_for_vendor(vendor.id)
        derived = await self._derived_selections(vendor.id)
        missing = [
            field
            for field in REQUIRED_APPLICATION_FIELDS
            if not (derived[field] if field in derived else getattr(application, field))
        ]
        editable = application.status in EDITABLE_APPLICATION_STATUSES
        return ProviderOnboardingChecklist(
            application_id=application.id,
            status=application.status,
            version=application.version,
            editable=editable,
            submittable=editable and not missing,
            missing=missing,
            requested_information=application.requested_information,
            decision_reason=application.decision_reason,
            submitted_at=application.submitted_at,
            decided_at=application.decided_at,
        )

    async def update_onboarding(
        self,
        user: User,
        data: ProviderOnboardingUpdate,
        *,
        expected_version: int | None = None,
    ) -> ProviderApplication:
        vendor = await self._owned_vendor(user, lock=True)
        application = await self._application_for_vendor(vendor.id, lock=True)
        self._require_version(application, expected_version)
        if application.status not in EDITABLE_APPLICATION_STATUSES:
            raise HTTPException(409, "Submitted applications cannot be edited")
        values = data.model_dump(exclude_unset=True, mode="json")
        if {"services", "skills"}.intersection(values):
            raise HTTPException(
                422,
                "Use the provider services and skills APIs for catalog selections",
            )
        for field, value in values.items():
            setattr(application, field, value)
        application.version += 1
        self._audit(
            user.id,
            "provider.onboarding.update",
            "provider_application",
            application.id,
            {"version": application.version},
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    @classmethod
    def missing_submission_fields(
        cls,
        application: ProviderApplication,
    ) -> list[str]:
        return [
            field
            for field in REQUIRED_APPLICATION_FIELDS
            if not getattr(application, field)
        ]

    async def submit(
        self,
        user: User,
        *,
        expected_version: int | None = None,
    ) -> ProviderApplication:
        vendor = await self._owned_vendor(user, lock=True)
        application = await self._application_for_vendor(vendor.id, lock=True)
        self._require_version(application, expected_version)
        if application.status not in EDITABLE_APPLICATION_STATUSES:
            raise HTTPException(
                409,
                "Application cannot be submitted in its current state",
            )
        for field, value in (await self._derived_selections(vendor.id)).items():
            setattr(application, field, value)
        missing = self.missing_submission_fields(application)
        if missing:
            raise HTTPException(
                422,
                detail={
                    "code": "ONBOARDING_INCOMPLETE",
                    "missing": missing,
                },
            )
        application.status = ProviderApplicationStatus.PENDING
        application.submitted_at = datetime.now(UTC)
        application.decided_at = None
        application.reviewed_by = None
        application.decision_reason = None
        application.requested_information = None
        application.version += 1
        self._audit(
            user.id,
            "provider.onboarding.submit",
            "provider_application",
            application.id,
            {"status": ProviderApplicationStatus.PENDING.value},
        )
        self._event(
            application,
            "provider_application_submitted",
            {"vendor_id": str(vendor.id)},
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def list_applications(
        self,
        *,
        status: ProviderApplicationStatus | None,
        limit: int,
        offset: int,
    ) -> ProviderApplicationList:
        filters = []
        if status:
            filters.append(ProviderApplication.status == status)
        query = (
            select(ProviderApplication)
            .where(*filters)
            .order_by(ProviderApplication.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_query = (
            select(func.count())
            .select_from(ProviderApplication)
            .where(*filters)
        )
        items = list((await self.session.scalars(query)).all())
        total = int(await self.session.scalar(count_query) or 0)
        return ProviderApplicationList(
            items=[
                ProviderApplicationRead.model_validate(item) for item in items
            ],
            total=total,
        )

    async def application(
        self,
        application_id: uuid.UUID,
    ) -> ProviderApplication:
        application = await self.session.get(
            ProviderApplication,
            application_id,
        )
        if not application:
            raise HTTPException(404, "Provider application not found")
        return application

    async def approve(
        self,
        application_id: uuid.UUID,
        actor: User,
        data: ProviderApplicationDecision,
    ) -> ProviderApplication:
        return await self._decide(
            application_id,
            actor,
            ProviderApplicationStatus.APPROVED,
            data.reason,
        )

    async def reject(
        self,
        application_id: uuid.UUID,
        actor: User,
        data: ProviderApplicationDecision,
    ) -> ProviderApplication:
        return await self._decide(
            application_id,
            actor,
            ProviderApplicationStatus.REJECTED,
            data.reason,
        )

    async def request_information(
        self,
        application_id: uuid.UUID,
        actor: User,
        data: ProviderApplicationDecision,
    ) -> ProviderApplication:
        return await self._decide(
            application_id,
            actor,
            ProviderApplicationStatus.INFORMATION_REQUESTED,
            data.reason,
        )

    async def _decide(
        self,
        application_id: uuid.UUID,
        actor: User,
        target: ProviderApplicationStatus,
        reason: str,
    ) -> ProviderApplication:
        application = await self.session.scalar(
            select(ProviderApplication)
            .where(ProviderApplication.id == application_id)
            .with_for_update()
        )
        if not application:
            raise HTTPException(404, "Provider application not found")
        if application.status != ProviderApplicationStatus.PENDING:
            raise HTTPException(409, "Only pending applications can be reviewed")
        vendor = await self.session.scalar(
            select(Vendor)
            .where(Vendor.id == application.vendor_id)
            .with_for_update()
        )
        if not vendor:
            raise HTTPException(404, "Provider organization not found")

        now = datetime.now(UTC)
        application.status = target
        application.reviewed_by = actor.id
        application.decided_at = now
        application.version += 1
        if target == ProviderApplicationStatus.INFORMATION_REQUESTED:
            application.requested_information = reason
            application.decision_reason = None
            vendor.status = VendorStatus.PENDING
        elif target == ProviderApplicationStatus.APPROVED:
            application.decision_reason = reason
            application.requested_information = None
            vendor.status = VendorStatus.ACTIVE
            await self.session.execute(
                update(Worker)
                .where(Worker.vendor_id == vendor.id)
                .values(status=WorkerStatus.ACTIVE, available=True)
            )
            await self.session.execute(
                update(ProviderService)
                .where(
                    ProviderService.vendor_id == vendor.id,
                    ProviderService.active.is_(True),
                    ProviderService.status == ApprovalStatus.PENDING,
                )
                .values(
                    status=ApprovalStatus.APPROVED,
                    reviewed_by=actor.id,
                    reviewed_at=now,
                    rejection_reason=None,
                    version=ProviderService.version + 1,
                )
            )
            await self.session.execute(
                update(ProviderSkill)
                .where(
                    ProviderSkill.vendor_id == vendor.id,
                    ProviderSkill.active.is_(True),
                    ProviderSkill.status == ApprovalStatus.PENDING,
                )
                .values(
                    status=ApprovalStatus.APPROVED,
                    reviewed_by=actor.id,
                    reviewed_at=now,
                    rejection_reason=None,
                    version=ProviderSkill.version + 1,
                )
            )
        else:
            application.decision_reason = reason
            application.requested_information = None
            vendor.status = VendorStatus.REJECTED
            await self.session.execute(
                update(Worker)
                .where(Worker.vendor_id == vendor.id)
                .values(status=WorkerStatus.INACTIVE, available=False)
            )

        action = {
            ProviderApplicationStatus.APPROVED: "provider.onboarding.approve",
            ProviderApplicationStatus.REJECTED: "provider.onboarding.reject",
            ProviderApplicationStatus.INFORMATION_REQUESTED: (
                "provider.onboarding.request_information"
            ),
        }[target]
        self._audit(
            actor.id,
            action,
            "provider_application",
            application.id,
            {"status": target.value, "reason": reason},
        )
        self._event(
            application,
            "provider_application_decided",
            {
                "vendor_id": str(vendor.id),
                "status": target.value,
                "reason": reason,
            },
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    @staticmethod
    def _require_version(
        application: ProviderApplication,
        expected_version: int | None,
    ) -> None:
        if expected_version is not None and application.version != expected_version:
            raise DomainError(
                "VERSION_CONFLICT",
                "Provider application changed since it was loaded.",
                409,
                fields={"current_version": application.version},
            )

    async def _derived_selections(self, vendor_id: uuid.UUID) -> dict[str, object]:
        """Application fields owned by dedicated provider domains.

        Services and skills always come from the catalog selection tables. Availability
        and license/insurance/document evidence are overlaid only when the provider has
        recorded them through the dedicated APIs, so older JSON drafts keep working.
        """

        services = list(
            (
                await self.session.scalars(
                    select(ProviderService).where(
                        ProviderService.vendor_id == vendor_id,
                        ProviderService.active.is_(True),
                    )
                )
            ).all()
        )
        skills = list(
            (
                await self.session.scalars(
                    select(ProviderSkill).where(
                        ProviderSkill.vendor_id == vendor_id,
                        ProviderSkill.active.is_(True),
                    )
                )
            ).all()
        )
        derived: dict[str, object] = {
            "services": [str(item.service_id) for item in services],
            "skills": [str(item.skill_id) for item in skills],
        }
        rules = list(
            (
                await self.session.scalars(
                    select(ProviderAvailabilityRule)
                    .where(
                        ProviderAvailabilityRule.vendor_id == vendor_id,
                        ProviderAvailabilityRule.active.is_(True),
                    )
                    .order_by(
                        ProviderAvailabilityRule.weekday,
                        ProviderAvailabilityRule.start_time,
                    )
                )
            ).all()
        )
        if rules:
            derived["availability"] = {
                "source": "provider_availability_rules",
                "rules": [
                    {
                        "rule_id": str(rule.id),
                        "worker_id": str(rule.worker_id) if rule.worker_id else None,
                        "weekday": rule.weekday,
                        "start_time": rule.start_time.strftime("%H:%M"),
                        "end_time": rule.end_time.strftime("%H:%M"),
                        "timezone": rule.timezone,
                        "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
                        "valid_until": (
                            rule.valid_until.isoformat() if rule.valid_until else None
                        ),
                    }
                    for rule in rules
                ],
            }
        qualifications = list(
            (
                await self.session.scalars(
                    select(ProviderQualification)
                    .where(
                        ProviderQualification.vendor_id == vendor_id,
                        ProviderQualification.status == QualificationStatus.SUBMITTED,
                        ProviderQualification.review_status.in_(EVIDENCED_REVIEW_STATUSES),
                    )
                    .order_by(ProviderQualification.created_at, ProviderQualification.id)
                )
            ).all()
        )
        if qualifications:
            derived["compliance_documents"] = [str(item.id) for item in qualifications]
        for field, qualification_type in (
            ("licenses", QualificationType.LICENSE),
            ("insurance", QualificationType.INSURANCE),
        ):
            matching = [
                {
                    "qualification_id": str(item.id),
                    "title": item.title,
                    "jurisdiction": item.jurisdiction,
                    "expires_on": item.expires_on.isoformat() if item.expires_on else None,
                    "review_status": item.review_status.value,
                }
                for item in qualifications
                if item.qualification_type == qualification_type
            ]
            if matching:
                derived[field] = matching
        return derived

    def _audit(
        self,
        actor_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        metadata: dict,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                actor_type="user",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_json=metadata,
                created_at=datetime.now(UTC),
            )
        )

    def _event(
        self,
        application: ProviderApplication,
        event_type: str,
        payload: dict,
    ) -> None:
        self.session.add(
            IntegrationEvent(
                aggregate_type="provider_application",
                aggregate_id=application.id,
                aggregate_version=application.version,
                event_type=event_type,
                idempotency_key=(
                    f"{event_type}:{application.id}:{application.version}"
                ),
                payload={"application_id": str(application.id), **payload},
                # PENDING, not PENDING_CONFIGURATION: these events have no external-adapter
                # dependency (not a "breero."-prefixed CRM event, not an email notification),
                # so there's nothing to gate on. PENDING_CONFIGURATION is only ever promoted
                # by OutboxService.activate_pending_configuration(aggregate_type="public_submission")
                # (see workers/tasks.py), which never matches aggregate_type="provider_application" —
                # using that status here would leave these events permanently unprocessed.
                status=EventStatus.PENDING,
                attempts=0,
                available_at=datetime.now(UTC),
            )
        )
