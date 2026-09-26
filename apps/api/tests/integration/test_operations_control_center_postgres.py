"""Operations Control Center journey against PostgreSQL/PostGIS.

Match -> manual assign -> candidate pre-screen -> reassign -> stale reassign ->
readback through every read model. No external effects: no booking is attached,
so no provider, payment, notification, or outbox delivery is triggered.
"""

import os
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.db.session import SessionLocal
from app.domains.auth import models as _auth_models  # noqa: F401
from app.domains.booking.models import (
    Address,
    LegalEntity,
    ProviderServiceCoverage,
    ProviderWorkingHours,
    ServiceArea,
)
from app.domains.catalog.models import Service
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.dispatch.control_center import OperationsControlCenterService, QueueFilters
from app.domains.dispatch.models import Assignment, AssignmentStatus, DispatchOffer, OfferStatus
from app.domains.dispatch.risk import RiskCode, RiskSeverity
from app.domains.dispatch.service import DispatchService
from app.domains.geography.models import ServiceZonePostalCode
from app.domains.jobs.models import Job, JobStatus
from app.domains.professional_leads import models as _professional_models  # noqa: F401
from app.domains.workforce.models import Vendor, VendorStatus, Worker, WorkerStatus

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="operations control center projections require PostgreSQL/PostGIS",
)


@pytest.mark.asyncio
async def test_operations_control_center_dispatch_journey() -> None:
    marker = uuid.uuid4().hex[:10]
    now = datetime.now(UTC)
    actor_id = uuid.uuid4()
    # Run-specific ZIP so coverage rows from other suites never join this zone.
    postal_code = f"{int(marker[:6], 16) % 90000 + 10000:05d}"

    async with SessionLocal() as session:
        entity = LegalEntity(code=f"OCC-{marker[:8]}", name="Ops Control Center", currency="USD")
        session.add(entity)
        await session.flush()
        area = ServiceArea(
            legal_entity_id=entity.id,
            name=f"Ops Zone {marker}",
            country_code="US",
            state_code="TX",
            city="Austin",
            active=True,
        )
        catalog_service = Service(
            slug=f"ops-cc-{marker}",
            name="Ops Control Repair",
            description="Operations control center journey",
            base_price=Decimal("100.00"),
            duration_minutes=120,
            is_active=True,
            is_bookable=True,
        )
        vendor = Vendor(
            legal_name=f"Ops Vendor {marker} LLC",
            display_name=f"Ops Vendor {marker}",
            email=f"ops-vendor-{marker}@example.com",
            phone="+15125550100",
            status=VendorStatus.ACTIVE,
            capabilities=[],
        )
        session.add_all([area, catalog_service, vendor])
        await session.flush()
        first = Worker(
            vendor_id=vendor.id,
            first_name="First",
            last_name=f"Tech {marker}",
            email=f"first-{marker}@example.com",
            phone="+15125550101",
            status=WorkerStatus.ACTIVE,
            available=True,
            skills=[],
        )
        second = Worker(
            vendor_id=vendor.id,
            first_name="Second",
            last_name=f"Tech {marker}",
            email=f"second-{marker}@example.com",
            phone="+15125550102",
            status=WorkerStatus.ACTIVE,
            available=True,
            skills=[],
        )
        inactive = Worker(
            vendor_id=vendor.id,
            first_name="Inactive",
            last_name=f"Tech {marker}",
            email=f"inactive-{marker}@example.com",
            phone="+15125550103",
            status=WorkerStatus.INACTIVE,
            available=False,
            skills=[],
        )
        session.add_all([first, second, inactive])
        await session.flush()
        session.add_all(
            [
                ServiceZonePostalCode(
                    service_area_id=area.id,
                    postal_code=postal_code,
                    city="Austin",
                    state_code="TX",
                ),
                ProviderServiceCoverage(
                    worker_id=second.id, service_id=catalog_service.id, postal_code=postal_code
                ),
                ProviderWorkingHours(
                    worker_id=second.id,
                    weekday=now.date().weekday(),
                    start_time=time(0, 0),
                    end_time=time(23, 59),
                    capacity=1,
                ),
            ]
        )
        address = Address(
            formatted_address="1 Private Street, Austin, TX 78701",
            line1="1 Private Street",
            city="Austin",
            state_code="TX",
            postal_code=postal_code,
            country_code="US",
            location=WKTElement("POINT(-97.7431 30.2672)", srid=4326),
            service_area_id=area.id,
            timezone_name="America/Chicago",
            geocoding_provider="fake",
        )
        session.add(address)
        await session.flush()

        def new_job(start: datetime, status: JobStatus = JobStatus.CREATED) -> Job:
            return Job(
                booking_id=uuid.uuid4(),
                service_id=catalog_service.id,
                address_id=address.id,
                status=status,
                scheduled_start=start,
                scheduled_end=start + timedelta(hours=2),
                version=1,
            )

        urgent = new_job(now + timedelta(hours=1))
        late = new_job(now - timedelta(minutes=30))
        later_today = new_job(now + timedelta(minutes=5))
        future = new_job(now + timedelta(days=3))
        session.add_all([urgent, late, later_today, future])
        await session.flush()
        failure = IntegrationEvent(
            aggregate_type="job",
            aggregate_id=urgent.id,
            event_type="job.ops_cc_test",
            payload={"secret": "never-exposed"},
            status=EventStatus.FAILED_TERMINAL,
            attempts=5,
            available_at=now,
            last_error="provider said customer@example.com is invalid",
            last_error_code="OPS_CC_TEST",
        )
        session.add(failure)
        await session.commit()

        # --- exception queue flags the right jobs with server-side policy
        control = OperationsControlCenterService(session)
        exceptions = await control.exceptions()
        flagged = {item.job_id: item for item in exceptions.items}
        assert flagged[late.id].highest_severity == RiskSeverity.CRITICAL
        assert RiskCode.UNASSIGNED_NEAR_START in {r.code for r in flagged[urgent.id].risks}
        assert future.id not in flagged
        assert exceptions.policy.unassigned_lead_time_minutes == 240
        critical_only = await control.exceptions(RiskSeverity.CRITICAL)
        assert late.id in {item.job_id for item in critical_only.items}
        assert urgent.id not in {item.job_id for item in critical_only.items}

        # --- dispatch queue filters and privacy-safe location
        area_queue = await control.queue(
            QueueFilters(service_area_id=area.id), limit=50, offset=0
        )
        assert {item.job_id for item in area_queue.items} == {
            urgent.id, late.id, later_today.id, future.id
        }
        assert area_queue.total == 4
        assert [item.job_id for item in area_queue.items][0] == late.id
        assert area_queue.items[0].location.service_area_name == area.name
        paged = await control.queue(QueueFilters(service_area_id=area.id), limit=2, offset=2)
        assert paged.total == 4 and len(paged.items) == 2
        risky = await control.queue(
            QueueFilters(service_area_id=area.id, at_risk_only=True), limit=50, offset=0
        )
        assert future.id not in {item.job_id for item in risky.items}
        assert risky.items[0].job_id == late.id

        # --- match, then manual assignment through the existing dispatch service
        offers = await DispatchService(session).match(urgent.id, actor_id)
        assert offers
        assignment = await DispatchService(session).manual_assign(
            urgent.id, vendor.id, first.id, actor_id, "Nearest technician"
        )
        assert assignment.status == AssignmentStatus.ACTIVE
        withdrawn = (
            await session.scalars(
                select(DispatchOffer.status).where(DispatchOffer.job_id == urgent.id)
            )
        ).all()
        assert withdrawn and set(withdrawn) == {OfferStatus.WITHDRAWN}

        # --- candidate pre-screen for reassignment
        await session.refresh(urgent)
        candidates = await OperationsControlCenterService(session).assignment_candidates(urgent.id)
        assert candidates.mode == "reassign" and candidates.job_status == JobStatus.ASSIGNED
        by_worker = {candidate.worker_id: candidate for candidate in candidates.candidates}
        assert inactive.id not in by_worker
        assert by_worker[first.id].currently_assigned
        assert by_worker[first.id].blocking_reasons == ["CURRENTLY_ASSIGNED"]
        assert by_worker[second.id].eligible and by_worker[second.id].covers_job_postal_code

        # --- reassign with optimistic version, then reject stale version
        reviewed_version = candidates.job_version
        replacement, released, job = await DispatchService(session).reassign(
            urgent.id, vendor.id, second.id, actor_id, "Rebalance workload", reviewed_version
        )
        assert job.worker_id == second.id and job.version == reviewed_version + 1
        assert released.status == AssignmentStatus.RELEASED
        with pytest.raises(HTTPException) as stale:
            await DispatchService(session).reassign(
                urgent.id, vendor.id, first.id, actor_id, "Stale view", reviewed_version
            )
        assert stale.value.status_code == 409
        active_rows = (
            await session.scalars(
                select(Assignment).where(
                    Assignment.job_id == urgent.id,
                    Assignment.status == AssignmentStatus.ACTIVE,
                )
            )
        ).all()
        assert [row.id for row in active_rows] == [replacement.id]

        # --- job detail readback: history, timeline, safe integration view, actions
        detail = await OperationsControlCenterService(session).job_detail(urgent.id)
        assert detail.job.worker is not None and detail.job.worker.id == second.id
        assert detail.job.live_offer_count == 0
        assert [a.status for a in detail.assignments] == [
            AssignmentStatus.RELEASED,
            AssignmentStatus.ACTIVE,
        ]
        actions = [entry.action for entry in detail.timeline]
        assert "reassigned" in actions and "assignment.reassign" in actions
        assert "assignment.create" in actions
        statuses = [e.to_status for e in detail.timeline if e.kind == "status"]
        # MATCHING and OFFERED share one transaction timestamp, so only their set is stable.
        assert set(statuses[:2]) == {JobStatus.MATCHING, JobStatus.OFFERED}
        assert statuses[2:] == [JobStatus.ASSIGNED, JobStatus.ASSIGNED]
        assert detail.actions.can_reassign and not detail.actions.can_assign
        assert detail.actions.allowed_transitions == [JobStatus.EN_ROUTE, JobStatus.CANCELLED]
        assert detail.actions.technician_commands == ["en-route"]
        assert detail.booking is None
        [event] = detail.integration_events
        assert event.last_error_code == "OPS_CC_TEST"
        dumped = detail.model_dump_json()
        assert "1 Private Street" not in dumped
        assert "never-exposed" not in dumped and "customer@example.com" not in dumped
        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.resource_id == urgent.id, AuditLog.action == "assignment.reassign"
            )
        )
        assert audit is not None and audit.actor_id == actor_id

        # --- capacity reflects the reassignment for today's window
        board = await OperationsControlCenterService(session).capacity(
            now.date(), vendor_id=vendor.id
        )
        rows = {worker.worker_id: worker for worker in board.workers}
        assert inactive.id not in rows
        assert rows[second.id].daily_capacity == 1
        assert rows[second.id].active_jobs == 1
        assert rows[first.id].active_jobs == 0 and rows[first.id].shift_start is None
        assert rows[second.id].covered_postal_codes == 1
        with_inactive = await OperationsControlCenterService(session).capacity(
            now.date(), vendor_id=vendor.id, include_inactive=True
        )
        assert inactive.id in {worker.worker_id for worker in with_inactive.workers}

        # --- service-area projection: aggregate only
        projection = await OperationsControlCenterService(session).service_areas()
        [zone] = [a for a in projection.areas if a.service_area_id == area.id]
        assert zone.postal_code_count == 1
        assert zone.active_jobs == 4 and zone.unassigned_jobs == 3
        assert zone.covering_dispatchable_workers == 1
        assert "Private Street" not in projection.model_dump_json()

        # --- dashboard and integration failures read the same truth
        dashboard = await OperationsControlCenterService(session).dashboard()
        by_status = {entry.status: entry.count for entry in dashboard.jobs_by_status}
        assert set(by_status) == set(JobStatus)
        assert by_status[JobStatus.ASSIGNED] >= 1 and dashboard.at_risk_jobs >= 2
        assert dashboard.integrations.failed >= 1
        failures = await OperationsControlCenterService(session).integration_failures(
            limit=200, retry_permitted=False
        )
        assert failure.id in {item.id for item in failures.items}
        assert "never-exposed" not in failures.model_dump_json()
