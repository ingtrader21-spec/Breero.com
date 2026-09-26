import asyncio
import os
import uuid
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.core.errors import DomainError
from app.db.session import SessionLocal
from app.domains.auth.models import (
    AccessAssignment,
    AccessProfile,
    AccessRole,
    Department,
    RolePermission,
    TenantScope,
    User,
    UserRole,
)
from app.domains.common.outbox import AuditLog
from app.domains.dispatch.models import DispatchOffer, OfferStatus
from app.domains.jobs.models import Job, JobStatus
from app.domains.provider_availability.schemas import (
    AvailabilityRuleCreate,
    AvailabilityRuleUpdate,
    BlackoutPeriodCreate,
)
from app.domains.provider_availability.service import ProviderAvailabilityService
from app.domains.provider_qualifications.models import (
    QualificationReviewStatus,
    QualificationStatus,
    QualificationType,
)
from app.domains.provider_qualifications.schemas import (
    QualificationCreate,
    QualificationReviewDecision,
)
from app.domains.provider_qualifications.service import ProviderQualificationService
from app.domains.provider_work.schemas import ProviderOfferDecision
from app.domains.provider_work.service import ProviderWorkService
from app.domains.workforce.models import (
    ProviderApplication,
    ProviderApplicationStatus,
    Vendor,
    VendorStatus,
    Worker,
    WorkerStatus,
)
from app.domains.workforce.onboarding_service import ProviderOnboardingService
from app.domains.workforce.provider_team import ProviderTeamService
from app.domains.workforce.schemas import ProviderWorkerCreate

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="provider portal integration requires PostgreSQL",
)

CHICAGO = "America/Chicago"


async def _provider(session, marker: str, suffix: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user = User(
        email=f"portal-{suffix}-{marker}@example.test",
        password_hash="disabled",
        full_name=f"Portal {suffix}",
        role=UserRole.vendor_admin,
        is_active=True,
        email_verified=True,
    )
    session.add(user)
    await session.flush()
    vendor = Vendor(
        legal_name=f"Portal {suffix} LLC",
        display_name=f"Portal {suffix}",
        email=user.email,
        phone="+17135550100",
        owner_user_id=user.id,
        status=VendorStatus.PENDING,
        capabilities=[],
        service_radius_meters=40000,
    )
    session.add(vendor)
    await session.flush()
    worker = Worker(
        vendor_id=vendor.id,
        user_id=user.id,
        first_name="Portal",
        last_name=suffix,
        email=user.email,
        phone="+17135550100",
        status=WorkerStatus.INVITED,
        skills=[],
        available=False,
    )
    session.add(worker)
    session.add(AccessProfile(user_id=user.id, brand_key="breero"))
    session.add(
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
    session.add(
        ProviderApplication(
            vendor_id=vendor.id,
            status=ProviderApplicationStatus.DRAFT,
            identity={"full_name": user.full_name},
            business={"legal_name": vendor.legal_name},
            contact_details={"email": user.email, "phone": vendor.phone},
            service_areas=[{"type": "ZIP", "value": "77001"}],
            postal_codes=["77001"],
            capacity={"daily_jobs": 4},
            version=1,
        )
    )
    await session.flush()
    return user.id, vendor.id, worker.id


async def _two_providers(marker: str):
    async with SessionLocal() as session:
        a = await _provider(session, marker, "a")
        b = await _provider(session, marker, "b")
        await session.commit()
    return a, b


async def _user(session, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    assert user is not None
    return user


@pytest.mark.asyncio
async def test_availability_is_scoped_versioned_and_readable() -> None:
    marker = uuid.uuid4().hex
    (owner_a, vendor_a, worker_a), (owner_b, _vendor_b, worker_b) = await _two_providers(marker)

    async with SessionLocal() as session:
        service = ProviderAvailabilityService(session)
        user_a = await _user(session, owner_a)
        rule = await service.create_rule(
            user_a,
            AvailabilityRuleCreate(
                weekday=0, start_time=time(8), end_time=time(12), timezone=CHICAGO
            ),
        )
        assert rule.vendor_id == vendor_a
        worker_rule = await service.create_rule(
            await _user(session, owner_a),
            AvailabilityRuleCreate(
                worker_id=worker_a,
                weekday=0,
                start_time=time(8),
                end_time=time(12),
                timezone=CHICAGO,
            ),
        )
        assert worker_rule.worker_id == worker_a

    async with SessionLocal() as session:
        with pytest.raises(DomainError) as overlap:
            await ProviderAvailabilityService(session).create_rule(
                await _user(session, owner_a),
                AvailabilityRuleCreate(
                    weekday=0, start_time=time(11), end_time=time(14), timezone=CHICAGO
                ),
            )
        assert overlap.value.code == "AVAILABILITY_OVERLAP"

    # Cross-provider substitution: B may not target A's rule or A's worker.
    async with SessionLocal() as session:
        with pytest.raises(DomainError) as hidden:
            await ProviderAvailabilityService(session).update_rule(
                rule.id,
                await _user(session, owner_b),
                AvailabilityRuleUpdate(end_time=time(13)),
                expected_version=rule.version,
            )
        assert hidden.value.code == "AVAILABILITY_RULE_NOT_FOUND"
    async with SessionLocal() as session:
        with pytest.raises(DomainError) as foreign_worker:
            await ProviderAvailabilityService(session).create_rule(
                await _user(session, owner_b),
                AvailabilityRuleCreate(
                    worker_id=worker_a,
                    weekday=2,
                    start_time=time(8),
                    end_time=time(12),
                    timezone=CHICAGO,
                ),
            )
        assert foreign_worker.value.code == "WORKER_NOT_FOUND"
    async with SessionLocal() as session:
        snapshot_b = await ProviderAvailabilityService(session).snapshot(
            await _user(session, owner_b)
        )
        assert snapshot_b.rules == []
        assert worker_b not in {item.worker_id for item in snapshot_b.rules}

    async with SessionLocal() as session:
        service = ProviderAvailabilityService(session)
        updated = await service.update_rule(
            rule.id,
            await _user(session, owner_a),
            AvailabilityRuleUpdate(end_time=time(13)),
            expected_version=rule.version,
        )
        assert updated.end_time == time(13)
        assert updated.version == rule.version + 1
    async with SessionLocal() as session:
        with pytest.raises(DomainError) as stale:
            await ProviderAvailabilityService(session).update_rule(
                rule.id,
                await _user(session, owner_a),
                AvailabilityRuleUpdate(end_time=time(14)),
                expected_version=rule.version,
            )
        assert stale.value.code == "VERSION_CONFLICT"

    async with SessionLocal() as session:
        blackout = await ProviderAvailabilityService(session).create_blackout(
            await _user(session, owner_a),
            BlackoutPeriodCreate(
                starts_at=datetime(2026, 10, 5, 14, tzinfo=UTC),
                ends_at=datetime(2026, 10, 5, 15, tzinfo=UTC),
                timezone=CHICAGO,
                reason="Supplier pickup",
            ),
        )
        assert blackout.starts_at == datetime(2026, 10, 5, 14, tzinfo=UTC)
    async with SessionLocal() as session:
        preview = await ProviderAvailabilityService(session).preview(
            await _user(session, owner_a),
            starts_at=datetime(2026, 10, 5, tzinfo=UTC),
            ends_at=datetime(2026, 10, 6, tzinfo=UTC),
        )
        company = [
            (item.starts_at, item.ends_at) for item in preview.intervals if item.worker_id is None
        ]
        # Monday 2026-10-05 08:00-13:00 CDT == 13:00-18:00Z minus the 14:00-15:00Z blackout.
        assert company == [
            (datetime(2026, 10, 5, 13, tzinfo=UTC), datetime(2026, 10, 5, 14, tzinfo=UTC)),
            (datetime(2026, 10, 5, 15, tzinfo=UTC), datetime(2026, 10, 5, 18, tzinfo=UTC)),
        ]

    async with SessionLocal() as session:
        await ProviderAvailabilityService(session).delete_rule(
            rule.id, await _user(session, owner_a), expected_version=updated.version
        )
    async with SessionLocal() as session:
        snapshot_a = await ProviderAvailabilityService(session).snapshot(
            await _user(session, owner_a)
        )
        assert rule.id not in {item.id for item in snapshot_a.rules}
        assert worker_rule.id in {item.id for item in snapshot_a.rules}
        actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.actor_id == owner_a)
                )
            ).all()
        )
        assert {
            "provider.availability.rule.create",
            "provider.availability.rule.update",
            "provider.availability.rule.delete",
            "provider.availability.blackout.create",
        } <= actions


@pytest.mark.asyncio
async def test_concurrent_overlapping_rules_admit_exactly_one() -> None:
    marker = uuid.uuid4().hex
    (owner_a, _vendor_a, _worker_a), _ = await _two_providers(marker)

    async def attempt(start_hour: int) -> str:
        async with SessionLocal() as session:
            try:
                await ProviderAvailabilityService(session).create_rule(
                    await _user(session, owner_a),
                    AvailabilityRuleCreate(
                        weekday=4,
                        start_time=time(start_hour),
                        end_time=time(start_hour + 3),
                        timezone=CHICAGO,
                    ),
                )
                return "created"
            except DomainError as exc:
                await session.rollback()
                return exc.code

    results = await asyncio.gather(attempt(9), attempt(10))
    assert sorted(results) == ["AVAILABILITY_OVERLAP", "created"]


@pytest.mark.asyncio
async def test_qualification_lifecycle_feeds_onboarding_checklist() -> None:
    marker = uuid.uuid4().hex
    (owner_a, vendor_a, _), (owner_b, _, _) = await _two_providers(marker)
    today = datetime.now(UTC).date()

    async with SessionLocal() as session:
        checklist = await ProviderOnboardingService(session).checklist(
            await _user(session, owner_a)
        )
        assert checklist.status == ProviderApplicationStatus.DRAFT
        assert checklist.editable is True
        assert checklist.submittable is False
        assert {"licenses", "insurance", "compliance_documents", "availability"} <= set(
            checklist.missing
        )

    created = {}
    for qualification_type in (QualificationType.LICENSE, QualificationType.INSURANCE):
        async with SessionLocal() as session:
            created[qualification_type] = await ProviderQualificationService(session).create(
                await _user(session, owner_a),
                QualificationCreate(
                    qualification_type=qualification_type,
                    title=f"{qualification_type.value.title()} {marker[:6]}",
                    jurisdiction="TX",
                    reference_last4="9876",
                    expires_on=today + timedelta(days=365),
                    evidence_reference=f"ref-{marker[:8]}",
                ),
            )
    license_record = created[QualificationType.LICENSE]
    assert license_record.status == QualificationStatus.DRAFT
    assert license_record.review_status == QualificationReviewStatus.NOT_SUBMITTED

    async with SessionLocal() as session:
        with pytest.raises(DomainError) as hidden:
            await ProviderQualificationService(session).submit(
                license_record.id,
                await _user(session, owner_b),
                expected_version=license_record.version,
            )
        assert hidden.value.code == "QUALIFICATION_NOT_FOUND"

    submitted = {}
    for qualification_type, record in created.items():
        async with SessionLocal() as session:
            submitted[qualification_type] = await ProviderQualificationService(session).submit(
                record.id, await _user(session, owner_a), expected_version=record.version
            )
    assert submitted[QualificationType.LICENSE].review_status == (
        QualificationReviewStatus.PENDING_REVIEW
    )

    async with SessionLocal() as session:
        await ProviderAvailabilityService(session).create_rule(
            await _user(session, owner_a),
            AvailabilityRuleCreate(
                weekday=1, start_time=time(8), end_time=time(17), timezone=CHICAGO
            ),
        )

    async with SessionLocal() as session:
        checklist = await ProviderOnboardingService(session).checklist(
            await _user(session, owner_a)
        )
        # Services and skills still come from the catalog APIs and are outstanding.
        assert set(checklist.missing) == {"services", "skills"}
        application = await session.scalar(
            select(ProviderApplication).where(ProviderApplication.vendor_id == vendor_a)
        )
        assert application is not None
        # The checklist is read-only.
        assert application.licenses == []

    async with SessionLocal() as session:
        reviewer = User(
            email=f"trust-{marker}@example.test",
            password_hash="disabled",
            full_name="Trust Reviewer",
            role=UserRole.admin,
            is_active=True,
            email_verified=True,
        )
        session.add(reviewer)
        await session.commit()
        await session.refresh(reviewer)
        reviewed = await ProviderQualificationService(session).review(
            license_record.id,
            reviewer,
            QualificationReviewDecision(decision="INFORMATION_REQUESTED", reason="Add issuer"),
        )
        assert reviewed.review_status == QualificationReviewStatus.INFORMATION_REQUESTED
        assert reviewed.review_reason == "Add issuer"

    async with SessionLocal() as session:
        await ProviderQualificationService(session).withdraw(
            license_record.id,
            await _user(session, owner_a),
            expected_version=reviewed.version,
        )
        listing = await ProviderQualificationService(session).list_qualifications(
            await _user(session, owner_a)
        )
        assert license_record.id not in {item.id for item in listing.items}
        assert listing.evidence_storage.upload_enabled is False
    async with SessionLocal() as session:
        foreign = await ProviderQualificationService(session).list_qualifications(
            await _user(session, owner_b)
        )
        assert foreign.items == []


@pytest.mark.asyncio
async def test_team_roster_is_scoped_and_new_workers_are_not_dispatchable() -> None:
    marker = uuid.uuid4().hex
    (owner_a, vendor_a, _), (owner_b, _, _) = await _two_providers(marker)
    email = f"tech-{marker}@example.test"

    async with SessionLocal() as session:
        created = await ProviderTeamService(session).add_worker(
            await _user(session, owner_a),
            ProviderWorkerCreate(
                first_name="Luis", last_name="Ramos", email=email, phone="+17135550111"
            ),
        )
        assert created.status == WorkerStatus.INVITED
        assert created.available is False
        assert created.has_account is False
    async with SessionLocal() as session:
        with pytest.raises(DomainError) as duplicate:
            await ProviderTeamService(session).add_worker(
                await _user(session, owner_a),
                ProviderWorkerCreate(
                    first_name="Luis", last_name="Ramos", email=email, phone="+17135550111"
                ),
            )
        assert duplicate.value.code == "WORKER_CONFLICT"
    async with SessionLocal() as session:
        roster_a = await ProviderTeamService(session).list_workers(await _user(session, owner_a))
        roster_b = await ProviderTeamService(session).list_workers(await _user(session, owner_b))
        assert created.id in {item.id for item in roster_a.items}
        assert created.id not in {item.id for item in roster_b.items}
        assert any(item.is_account_owner for item in roster_a.items)
        stored = await session.get(Worker, created.id)
        assert stored is not None and stored.vendor_id == vendor_a


@pytest.mark.asyncio
async def test_jobs_and_offers_are_visible_only_to_their_provider() -> None:
    marker = uuid.uuid4().hex
    (owner_a, vendor_a, worker_a), (owner_b, _, _) = await _two_providers(marker)
    start = datetime.now(UTC) + timedelta(days=3)

    async with SessionLocal() as session:
        job = Job(
            booking_id=uuid.uuid4(),
            service_id=uuid.uuid4(),
            address_id=uuid.uuid4(),
            status=JobStatus.OFFERED,
            scheduled_start=start,
            scheduled_end=start + timedelta(hours=2),
            vendor_id=vendor_a,
            version=1,
        )
        session.add(job)
        await session.flush()
        offer = DispatchOffer(
            job_id=job.id,
            vendor_id=vendor_a,
            worker_id=worker_a,
            status=OfferStatus.PENDING,
            round=1,
            score=10,
            score_detail={},
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(offer)
        await session.commit()
        job_id, offer_id = job.id, offer.id

    async with SessionLocal() as session:
        work = ProviderWorkService(session)
        jobs_a = await work.list_jobs(
            await _user(session, owner_a), status=None, limit=50, offset=0
        )
        offers_a = await work.list_offers(
            await _user(session, owner_a), status=OfferStatus.PENDING, limit=50, offset=0
        )
        jobs_b = await work.list_jobs(
            await _user(session, owner_b), status=None, limit=50, offset=0
        )
        offers_b = await work.list_offers(
            await _user(session, owner_b), status=None, limit=50, offset=0
        )
        assert [item.id for item in jobs_a.items] == [job_id]
        assert [item.id for item in offers_a.items] == [offer_id]
        assert offers_a.items[0].job_status == JobStatus.OFFERED
        assert jobs_b.items == [] and offers_b.items == []

    async with SessionLocal() as session:
        with pytest.raises(DomainError) as hidden:
            await ProviderWorkService(session).decide_offer(
                offer_id, await _user(session, owner_b), ProviderOfferDecision(accept=False)
            )
        assert hidden.value.code == "OFFER_NOT_FOUND"

    async with SessionLocal() as session:
        declined = await ProviderWorkService(session).decide_offer(
            offer_id, await _user(session, owner_a), ProviderOfferDecision(accept=False)
        )
        assert declined.status == OfferStatus.DECLINED


@pytest.mark.asyncio
async def test_provider_portal_permissions_are_seeded_by_migration() -> None:
    async with SessionLocal() as session:
        permissions = set(
            (
                await session.scalars(
                    select(RolePermission.permission).where(
                        RolePermission.role_key == AccessRole.vendor_admin.value
                    )
                )
            ).all()
        )
    assert {
        "provider.availability.read",
        "provider.qualifications.manage",
        "provider.offers.decide",
    } <= permissions
