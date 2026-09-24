"""PostgreSQL accuracy, freshness, and tenant-scope tests for analytics projections."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domains.analytics.repository import AnalyticsRepository
from app.domains.analytics.schemas import AnalyticsScopeKind, MetricGroupStatus
from app.domains.analytics.scope import AnalyticsScope
from app.domains.analytics.service import MarketplaceMetricsService
from app.domains.auth import security
from app.domains.auth.models import (
    AccessAssignment,
    AccessProfile,
    AccessRole,
    Department,
    TenantScope,
    User,
    UserPermission,
    UserRole,
)
from app.domains.booking.capacity_models import ServiceZone
from app.domains.booking.models import (
    Address,
    Booking,
    BookingStatus,
    Customer,
    LegalEntity,
    ServiceArea,
)
from app.domains.booking_intents.models import BookingIntent, BookingIntentStatus
from app.domains.catalog.models import Service
from app.domains.dispatch.models import DispatchOffer, OfferStatus
from app.domains.jobs.models import Job, JobStatus, WorkRequest, WorkRequestStatus
from app.domains.workforce.models import Vendor, VendorStatus
from app.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="analytics projection integration requires PostgreSQL",
)


def _values(group) -> dict[str, float | int | None]:
    return {item.key: item.value for item in group.values}


def _groups(read) -> dict:
    return {group.key.value: group for group in read.groups}


async def _seed(marker: str, window_start: datetime) -> dict:
    """Seed one isolated marketplace slice with two providers inside one day."""

    t = window_start + timedelta(hours=1)
    before = window_start - timedelta(hours=1)
    async with SessionLocal() as session:
        assert ServiceZone.__table__.name == "service_zones"
        entity = LegalEntity(code=f"AN-{marker[:8]}", name="Analytics Test", currency="USD")
        service = Service(
            slug=f"analytics-{marker}",
            name="Analytics test",
            category="home-services",
            pricing_model="quote_required",
            is_active=True,
            is_bookable=True,
        )
        customer = Customer(
            first_name="Analytics",
            last_name="Customer",
            email=f"analytics-{marker}@example.com",
            phone="+12815550111",
        )
        session.add_all([entity, service, customer])
        await session.flush()
        area = ServiceArea(
            legal_entity_id=entity.id,
            name="Analytics area",
            country_code="US",
            state_code="TX",
            city="Cypress",
            postal_codes=["77433"],
            active=True,
        )
        session.add(area)
        await session.flush()
        address = Address(
            formatted_address="1 Analytics Way, Cypress, TX 77433",
            line1="1 Analytics Way",
            city="Cypress",
            state_code="TX",
            postal_code="77433",
            country_code="US",
            location=WKTElement("POINT(-95.7 29.9)", srid=4326),
            service_area_id=area.id,
            geocoding_provider="analytics-test",
            timezone_name="America/Chicago",
            customer_id=customer.id,
        )
        session.add(address)

        users: dict[str, User] = {}
        for key, role in (
            ("owner_a", UserRole.vendor_admin),
            ("owner_b", UserRole.vendor_admin),
            ("ops_manager", UserRole.operations),
            ("operations", UserRole.operations),
            ("admin", UserRole.admin),
            ("customer", UserRole.customer),
            ("escalating_provider", UserRole.vendor_admin),
        ):
            users[key] = User(
                email=f"analytics-{key}-{marker}@example.com",
                password_hash="disabled",
                full_name=f"Analytics {key}",
                role=role,
                is_active=True,
                email_verified=True,
            )
        session.add_all(users.values())
        await session.flush()

        vendors = {}
        for key in ("a", "b"):
            vendors[key] = Vendor(
                legal_name=f"Analytics {key} LLC",
                display_name=f"Analytics {key}",
                email=f"analytics-vendor-{key}-{marker}@example.com",
                phone="+17135550100",
                owner_user_id=users[f"owner_{key}"].id,
                status=VendorStatus.ACTIVE,
                capabilities=[],
                service_radius_meters=40000,
            )
        session.add_all(vendors.values())
        await session.flush()

        def assignment(user: User, role: AccessRole, department: Department, scope: TenantScope, vendor=None):
            return AccessAssignment(
                user_id=user.id,
                brand_key="breero",
                role_key=role.value,
                department=department.value,
                tenant_scope=scope.value,
                vendor_id=vendor.id if vendor else None,
                active=True,
                is_primary=True,
            )

        for key in ("owner_a", "ops_manager", "escalating_provider"):
            session.add(AccessProfile(user_id=users[key].id, brand_key="breero"))
        session.add_all(
            [
                assignment(users["owner_a"], AccessRole.vendor_admin, Department.provider, TenantScope.vendor, vendors["a"]),
                assignment(users["ops_manager"], AccessRole.ops_manager, Department.dispatch, TenantScope.brand),
                assignment(
                    users["escalating_provider"],
                    AccessRole.vendor_admin,
                    Department.provider,
                    TenantScope.vendor,
                    vendors["b"],
                ),
                UserPermission(
                    user_id=users["escalating_provider"].id,
                    brand_key="breero",
                    permission="analytics.marketplace.read",
                    allow=True,
                ),
            ]
        )

        def intent(status: BookingIntentStatus, created: datetime, suffix: str) -> BookingIntent:
            return BookingIntent(
                public_reference=f"AI{marker[:10]}{suffix}",
                anonymous_session_id=uuid.uuid4(),
                service_id=service.id,
                status=status,
                expires_at=created + timedelta(hours=2),
                created_at=created,
                updated_at=created,
            )

        session.add_all(
            [
                intent(BookingIntentStatus.SUBMITTED, t, "1"),
                intent(BookingIntentStatus.COVERAGE_CONFIRMED, t, "2"),
                intent(BookingIntentStatus.ADDRESS_VALIDATED, t, "3"),
                intent(BookingIntentStatus.EXPIRED, t + timedelta(minutes=30), "4"),
                intent(BookingIntentStatus.SUBMITTED, before, "5"),
            ]
        )

        def booking(status: BookingStatus, created: datetime, suffix: str) -> Booking:
            return Booking(
                reference=f"AN-{marker[:8]}-{suffix}",
                idempotency_key=f"analytics-{marker}-{suffix}",
                idempotency_request_hash=(marker + suffix).ljust(64, "0")[:64],
                customer_id=customer.id,
                address_id=address.id,
                legal_entity_id=entity.id,
                service_id=service.id,
                window_start=created + timedelta(days=2),
                window_end=created + timedelta(days=2, hours=1),
                status=status,
                pricing_snapshot={"analytics_test": True},
                total_amount=Decimal("0.00"),
                currency="USD",
                expires_at=created + timedelta(days=1),
                guest_confirmation_token_hash=(marker + suffix).ljust(64, "1")[:64],
                guest_confirmation_expires_at=created + timedelta(days=3),
                created_at=created,
                updated_at=created,
            )

        bookings = {
            "a_confirmed": booking(BookingStatus.CONFIRMED, t, "ac"),
            "a_cancelled": booking(BookingStatus.CANCELLED, t, "ax"),
            "b_completed": booking(BookingStatus.COMPLETED, t + timedelta(minutes=45), "bc"),
            "unassigned": booking(BookingStatus.NO_COVERAGE, t, "nc"),
            "a_before": booking(BookingStatus.CONFIRMED, before, "ab"),
        }
        session.add_all(bookings.values())
        await session.flush()

        def job(status: JobStatus, created: datetime, booking_id: uuid.UUID, vendor=None) -> Job:
            return Job(
                booking_id=booking_id,
                service_id=service.id,
                address_id=address.id,
                status=status,
                scheduled_start=created + timedelta(days=2),
                scheduled_end=created + timedelta(days=2, hours=1),
                vendor_id=vendor.id if vendor else None,
                created_at=created,
                updated_at=created,
            )

        jobs = {
            "a_assigned": job(JobStatus.ASSIGNED, t, bookings["a_confirmed"].id, vendors["a"]),
            "a_cancelled": job(JobStatus.CANCELLED, t, bookings["a_cancelled"].id, vendors["a"]),
            "b_completed": job(JobStatus.COMPLETED, t, bookings["b_completed"].id, vendors["b"]),
            "matching": job(JobStatus.MATCHING, t, uuid.uuid4()),
            "a_before": job(JobStatus.COMPLETED, before, bookings["a_before"].id, vendors["a"]),
        }
        session.add_all(jobs.values())
        await session.flush()

        def offer(job_key: str, vendor, status: OfferStatus, created: datetime, answer_seconds=None):
            return DispatchOffer(
                job_id=jobs[job_key].id,
                vendor_id=vendor.id,
                status=status,
                score=50,
                score_detail={},
                expires_at=created + timedelta(minutes=15),
                responded_at=created + timedelta(seconds=answer_seconds) if answer_seconds else None,
                created_at=created,
            )

        session.add_all(
            [
                offer("a_assigned", vendors["a"], OfferStatus.ACCEPTED, t, 60),
                offer("b_completed", vendors["b"], OfferStatus.DECLINED, t, 300),
                offer("matching", vendors["a"], OfferStatus.EXPIRED, t),
                offer("matching", vendors["b"], OfferStatus.PENDING, t),
                offer("a_before", vendors["a"], OfferStatus.ACCEPTED, before, 10),
            ]
        )

        def quote(job_key: str, status: WorkRequestStatus) -> WorkRequest:
            return WorkRequest(
                job_id=jobs[job_key].id,
                status=status,
                description="Analytics quote",
                line_items=[],
                subtotal_minor=1000,
                tax_minor=0,
                total_minor=1000,
                currency="USD",
                created_by=users["owner_a"].id,
                created_at=t,
                updated_at=t + timedelta(minutes=5),
            )

        session.add_all(
            [
                quote("a_assigned", WorkRequestStatus.APPROVED),
                quote("a_assigned", WorkRequestStatus.DECLINED),
                quote("b_completed", WorkRequestStatus.PENDING_CUSTOMER),
                quote("b_completed", WorkRequestStatus.DRAFT),
            ]
        )
        await session.commit()
        return {"users": users, "vendors": vendors, "t": t}


def _isolated_window(marker: str) -> tuple[datetime, datetime]:
    # A unique far-future day keeps shared-database rows from other tests out of the window.
    start = datetime(2040, 1, 1, tzinfo=UTC) + timedelta(days=int(marker[:6], 16) % 20000)
    return start, start + timedelta(days=1)


@pytest.mark.asyncio
async def test_marketplace_projection_matches_seeded_source_of_record() -> None:
    marker = uuid.uuid4().hex
    start, end = _isolated_window(marker)
    seeded = await _seed(marker, start)

    read = await MarketplaceMetricsService(SessionLocal).metrics(
        AnalyticsScope(AnalyticsScopeKind.marketplace), start, end
    )
    groups = _groups(read)

    assert read.scope.kind == AnalyticsScopeKind.marketplace
    assert read.scope.vendor_id is None
    assert (read.window.start, read.window.end) == (start, end)
    assert list(groups) == [
        "request",
        "qualification",
        "matching",
        "opportunity",
        "quote",
        "booking",
        "utilization",
        "completion",
        "cancellation",
        "review",
        "response_time",
        "finance",
    ]
    assert _values(groups["request"]) == {
        "intents_created": 4,
        "intents_submitted": 1,
        "intents_expired": 1,
        "submission_rate": 0.25,
    }
    assert _values(groups["qualification"]) == {
        "address_validated": 1,
        "coverage_confirmed": 1,
        "availability_found": 0,
        "qualification_rate": 0.5,
    }
    assert _values(groups["matching"]) == {
        "jobs_created": 4,
        "jobs_awaiting_match": 1,
        "jobs_matched": 2,
        "match_rate": 0.5,
    }
    assert _values(groups["opportunity"]) == {
        "offers_sent": 4,
        "offers_pending": 1,
        "offers_accepted": 1,
        "offers_declined": 1,
        "offers_expired": 1,
        "acceptance_rate": 0.3333,
    }
    assert _values(groups["quote"]) == {
        "quotes_issued": 3,
        "quotes_pending": 1,
        "quotes_approved": 1,
        "quotes_declined": 1,
        "quote_approval_rate": 0.5,
    }
    assert _values(groups["booking"]) == {
        "bookings_created": 4,
        "bookings_confirmed": 2,
        "bookings_unfulfilled": 1,
        "confirmation_rate": 0.5,
    }
    assert _values(groups["completion"]) == {
        "jobs_completed": 1,
        "jobs_cancelled": 1,
        "completion_rate": 0.5,
    }
    assert _values(groups["cancellation"]) == {"bookings_cancelled": 1, "cancellation_rate": 0.25}
    assert _values(groups["response_time"]) == {
        "offers_responded": 2,
        "median_response_seconds": 180.0,
        "p90_response_seconds": 276.0,
    }

    # Freshness: watermarks are the latest in-scope source change, never "now".
    t = seeded["t"]
    assert groups["request"].source_watermark == t + timedelta(minutes=30)
    assert groups["booking"].source_watermark == t + timedelta(minutes=45)
    assert groups["opportunity"].source_watermark == t + timedelta(seconds=300)
    assert groups["quote"].source_watermark == t + timedelta(minutes=5)
    assert read.generated_at > datetime.now(UTC) - timedelta(minutes=1)
    assert read.projection.max_age_seconds == 300

    # Groups without a certified source of record are never fabricated.
    for key, blocker in (("utilization", None), ("review", "PAS-128"), ("finance", "PAS-129")):
        assert groups[key].status == MetricGroupStatus.unavailable
        assert groups[key].values == []
        assert groups[key].blocked_by == blocker


@pytest.mark.asyncio
async def test_provider_projection_is_limited_to_the_provider_organization() -> None:
    marker = uuid.uuid4().hex
    start, end = _isolated_window(marker)
    seeded = await _seed(marker, start)
    vendor_a = seeded["vendors"]["a"]

    read = await MarketplaceMetricsService(SessionLocal).metrics(
        AnalyticsScope(AnalyticsScopeKind.provider, vendor_a.id), start, end
    )
    groups = _groups(read)

    assert read.scope.vendor_id == vendor_a.id
    for key in ("request", "qualification", "matching"):
        assert groups[key].status == MetricGroupStatus.restricted
        assert groups[key].values == []
    assert _values(groups["opportunity"]) == {
        "offers_sent": 2,
        "offers_pending": 0,
        "offers_accepted": 1,
        "offers_declined": 0,
        "offers_expired": 1,
        "acceptance_rate": 0.5,
    }
    assert _values(groups["quote"])["quotes_issued"] == 2
    assert _values(groups["booking"]) == {
        "bookings_created": 2,
        "bookings_confirmed": 1,
        "bookings_unfulfilled": 0,
        "confirmation_rate": 0.5,
    }
    assert _values(groups["completion"]) == {
        "jobs_completed": 0,
        "jobs_cancelled": 1,
        "completion_rate": 0.0,
    }
    assert _values(groups["cancellation"]) == {"bookings_cancelled": 1, "cancellation_rate": 0.5}
    assert _values(groups["response_time"]) == {
        "offers_responded": 1,
        "median_response_seconds": 60.0,
        "p90_response_seconds": 60.0,
    }


@pytest.mark.asyncio
async def test_empty_window_returns_zero_counts_and_undefined_rates() -> None:
    start = datetime(2039, 1, 1, tzinfo=UTC)
    read = await MarketplaceMetricsService(SessionLocal).metrics(
        AnalyticsScope(AnalyticsScopeKind.marketplace), start, start + timedelta(minutes=1)
    )
    booking = _groups(read)["booking"]
    assert booking.status == MetricGroupStatus.available
    assert booking.source_watermark is None
    assert _values(booking)["bookings_created"] == 0
    assert _values(booking)["confirmation_rate"] is None


@pytest.mark.asyncio
async def test_projection_reads_from_a_read_only_repeatable_read_snapshot(monkeypatch) -> None:
    observed: dict[str, str] = {}
    original = AnalyticsRepository.snapshot_time

    async def spy(self: AnalyticsRepository) -> datetime:
        observed["read_only"] = str(await self.session.scalar(text("SHOW transaction_read_only")))
        observed["isolation"] = str(await self.session.scalar(text("SHOW transaction_isolation")))
        return await original(self)

    monkeypatch.setattr(AnalyticsRepository, "snapshot_time", spy)
    start = datetime(2039, 1, 2, tzinfo=UTC)
    await MarketplaceMetricsService(SessionLocal).metrics(
        AnalyticsScope(AnalyticsScopeKind.marketplace), start, start + timedelta(minutes=1)
    )
    assert observed == {"read_only": "on", "isolation": "repeatable read"}

    # Snapshot characteristics must not leak onto pooled connections used for writes.
    async with SessionLocal() as session:
        assert await session.scalar(text("SHOW transaction_read_only")) == "off"
        assert await session.scalar(text("SHOW transaction_isolation")) == "read committed"


@pytest.mark.asyncio
async def test_http_role_and_tenant_visibility(monkeypatch) -> None:
    if not security.settings.jwt_secret:
        monkeypatch.setattr(security.settings, "jwt_secret", "analytics-test-secret-" + "x" * 32)
    marker = uuid.uuid4().hex
    start, end = _isolated_window(marker)
    seeded = await _seed(marker, start)
    users = seeded["users"]
    params = {"start": start.isoformat(), "end": end.isoformat()}

    def headers(key: str) -> dict[str, str]:
        user = users[key]
        return {"Authorization": f"Bearer {security.create_access_token(user.id, user.role.value)}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        async def get(path: str, key: str | None) -> httpx.Response:
            return await client.get(
                f"/api/v1/analytics/{path}/metrics",
                params=params,
                headers=headers(key) if key else {},
            )

        assert (await get("marketplace", None)).status_code == 401
        assert (await get("provider", None)).status_code == 401

        for key in ("ops_manager", "admin"):
            response = await get("marketplace", key)
            assert response.status_code == 200, response.text
            assert response.json()["scope"] == {"kind": "marketplace", "vendor_id": None}

        for key, code in (
            ("operations", "ANALYTICS_FORBIDDEN"),
            ("customer", "ANALYTICS_FORBIDDEN"),
            ("owner_a", "ANALYTICS_FORBIDDEN"),
            ("escalating_provider", "ANALYTICS_SCOPE_DENIED"),
        ):
            response = await get("marketplace", key)
            assert response.status_code == 403, (key, response.text)
            assert response.json()["error"]["code"] == code

        provider = await get("provider", "owner_a")
        assert provider.status_code == 200, provider.text
        assert provider.json()["scope"] == {
            "kind": "provider",
            "vendor_id": str(seeded["vendors"]["a"].id),
        }
        # The owner-only fallback resolves vendor B for its owner without an explicit assignment.
        owner_b = await get("provider", "owner_b")
        assert owner_b.status_code == 200, owner_b.text
        assert owner_b.json()["scope"]["vendor_id"] == str(seeded["vendors"]["b"].id)

        for key in ("ops_manager", "customer"):
            response = await get("provider", key)
            assert response.status_code == 403, (key, response.text)

        invalid = await client.get(
            "/api/v1/analytics/marketplace/metrics",
            params={"start": end.isoformat(), "end": start.isoformat()},
            headers=headers("ops_manager"),
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "INVALID_ANALYTICS_WINDOW"
