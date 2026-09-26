import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.provider_http import optional_if_match, require_if_match
from app.core.errors import DomainError
from app.domains.auth.models import User, UserRole
from app.domains.provider_availability import service as availability_service_module
from app.domains.provider_availability.expansion import (
    Blackout,
    RuleWindow,
    expand,
    windows_overlap,
)
from app.domains.provider_availability.models import ProviderAvailabilityRule
from app.domains.provider_availability.schemas import (
    AvailabilityRuleCreate,
    AvailabilityRuleUpdate,
    BlackoutPeriodCreate,
    BlackoutPeriodUpdate,
)
from app.domains.provider_availability.service import ProviderAvailabilityService
from app.domains.provider_qualifications import service as qualification_service_module
from app.domains.provider_qualifications.models import (
    ProviderQualification,
    QualificationReviewStatus,
    QualificationStatus,
    QualificationType,
)
from app.domains.provider_qualifications.schemas import (
    QualificationCreate,
    QualificationReviewDecision,
    QualificationUpdate,
)
from app.domains.provider_qualifications.service import ProviderQualificationService
from app.domains.provider_work import service as work_service_module
from app.domains.provider_work.schemas import ProviderOfferDecision
from app.domains.provider_work.service import ProviderWorkService
from app.domains.workforce.models import Vendor, VendorStatus
from app.domains.workforce.provider_scope import provider_vendor, provider_worker
from app.domains.workforce.schemas import ProviderWorkerCreate
from app.main import app

CHICAGO = "America/Chicago"


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        password_hash="disabled",
        full_name="Provider Owner",
        role=UserRole.vendor_admin,
        is_active=True,
        email_verified=True,
    )


def make_vendor(status: VendorStatus = VendorStatus.PENDING) -> Vendor:
    return Vendor(id=uuid.uuid4(), owner_user_id=uuid.uuid4(), status=status)


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class _Rows:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return list(self._rows)


class FakeSession:
    """Queue-backed async session double; records writes, never touches a database."""

    def __init__(self, *, scalar: list | None = None, scalars: list | None = None) -> None:
        self._scalar = list(scalar or [])
        self._scalars = list(scalars or [])
        self.added: list = []
        self.commits = 0
        self.flushes = 0

    async def scalar(self, _query):
        return self._scalar.pop(0) if self._scalar else None

    async def scalars(self, _query):
        return _Rows(self._scalars.pop(0) if self._scalars else [])

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushes += 1
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj) -> None:
        now = datetime.now(UTC)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        obj.updated_at = now

    async def get(self, _model, _id):
        return None


def patch_scope(monkeypatch, module, vendor: Vendor) -> list[dict]:
    calls: list[dict] = []

    async def fake_provider_vendor(_session, _user, *, lock=False, write=False):
        calls.append({"lock": lock, "write": write})
        return vendor

    monkeypatch.setattr(module, "provider_vendor", fake_provider_vendor)
    return calls


# --- Route registration and deny-by-default ---------------------------------------


def test_provider_portal_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/provider/workers": {"get", "post"},
        "/api/v1/provider/availability": {"get"},
        "/api/v1/provider/availability/preview": {"get"},
        "/api/v1/provider/availability/rules": {"post"},
        "/api/v1/provider/availability/rules/{rule_id}": {"patch", "delete"},
        "/api/v1/provider/availability/blackouts": {"post"},
        "/api/v1/provider/availability/blackouts/{blackout_id}": {"patch", "delete"},
        "/api/v1/provider/qualifications": {"get", "post"},
        "/api/v1/provider/qualifications/{qualification_id}": {"get", "patch", "delete"},
        "/api/v1/provider/qualifications/{qualification_id}/submit": {"post"},
        "/api/v1/provider/qualifications/{qualification_id}/evidence": {"post"},
        "/api/v1/admin/provider-qualifications/{qualification_id}/review": {"post"},
        "/api/v1/provider/jobs": {"get"},
        "/api/v1/provider/offers": {"get"},
        "/api/v1/provider/offers/{offer_id}/decision": {"post"},
        "/api/v1/provider/onboarding/checklist": {"get"},
        "/api/v1/provider/skill-catalog": {"get"},
    }
    for path, methods in expected.items():
        assert methods <= set(paths[path]), path


def test_provider_scoped_routes_never_take_a_vendor_identifier() -> None:
    paths = app.openapi()["paths"]
    for path, operations in paths.items():
        if not path.startswith("/api/v1/provider/"):
            continue
        assert "vendor_id" not in path
        for operation in operations.values():
            names = {item.get("name") for item in operation.get("parameters", [])}
            assert "vendor_id" not in names, path


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/provider/workers"),
        ("post", "/api/v1/provider/workers"),
        ("get", "/api/v1/provider/availability"),
        ("post", "/api/v1/provider/availability/rules"),
        ("get", "/api/v1/provider/qualifications"),
        ("post", "/api/v1/provider/qualifications"),
        ("get", "/api/v1/provider/jobs"),
        ("get", "/api/v1/provider/offers"),
        ("get", "/api/v1/provider/onboarding/checklist"),
        ("get", "/api/v1/provider/skill-catalog"),
        ("post", f"/api/v1/provider/qualifications/{uuid.uuid4()}/evidence"),
        ("post", f"/api/v1/admin/provider-qualifications/{uuid.uuid4()}/review"),
    ],
)
def test_provider_portal_is_deny_by_default(method: str, path: str) -> None:
    client = TestClient(app)
    assert client.request(method, path, json={}).status_code == 401


# --- If-Match -----------------------------------------------------------------------


def test_if_match_parsing() -> None:
    assert require_if_match('"3"') == 3
    assert require_if_match('W/"7"') == 7
    assert optional_if_match(None) is None
    with pytest.raises(DomainError) as missing:
        require_if_match(None)
    assert missing.value.status_code == 428
    for invalid in ("*", '"0"', "abc", '"-1"'):
        with pytest.raises(DomainError):
            require_if_match(invalid)


# --- Mass-assignment and input contracts --------------------------------------------


@pytest.mark.parametrize("field", ["vendor_id", "status", "user_id", "available"])
def test_worker_create_rejects_privileged_fields(field: str) -> None:
    payload = {
        "first_name": "Ana",
        "last_name": "Diaz",
        "email": "ana@example.com",
        "phone": "+17135550100",
        field: str(uuid.uuid4()),
    }
    with pytest.raises(ValidationError):
        ProviderWorkerCreate.model_validate(payload)


def test_offer_decision_rejects_vendor_substitution() -> None:
    with pytest.raises(ValidationError):
        ProviderOfferDecision.model_validate({"accept": True, "vendor_id": str(uuid.uuid4())})


def test_availability_rule_contract() -> None:
    rule = AvailabilityRuleCreate(
        weekday=0, start_time=time(8), end_time=time(17), timezone=CHICAGO
    )
    assert rule.timezone == CHICAGO
    invalid_payloads = [
        {"weekday": 7, "start_time": "08:00", "end_time": "17:00", "timezone": CHICAGO},
        {"weekday": 1, "start_time": "22:00", "end_time": "02:00", "timezone": CHICAGO},
        {"weekday": 1, "start_time": "08:00", "end_time": "17:00", "timezone": "Mars/Base"},
        {"weekday": 1, "start_time": "08:00", "end_time": "17:00", "timezone": "../etc/passwd"},
        {"weekday": 1, "start_time": "08:00:30", "end_time": "17:00", "timezone": CHICAGO},
        {
            "weekday": 1,
            "start_time": "08:00",
            "end_time": "17:00",
            "timezone": CHICAGO,
            "valid_from": "2026-12-01",
            "valid_until": "2026-11-01",
        },
        {
            "weekday": 1,
            "start_time": "08:00",
            "end_time": "17:00",
            "timezone": CHICAGO,
            "vendor_id": str(uuid.uuid4()),
        },
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            AvailabilityRuleCreate.model_validate(payload)
    with pytest.raises(ValidationError):
        AvailabilityRuleUpdate()
    with pytest.raises(ValidationError):
        AvailabilityRuleUpdate.model_validate({"timezone": None})


def test_blackout_requires_offsets_and_is_stored_in_utc() -> None:
    blackout = BlackoutPeriodCreate.model_validate(
        {
            "starts_at": "2026-11-26T00:00:00-06:00",
            "ends_at": "2026-11-27T00:00:00-06:00",
            "timezone": CHICAGO,
            "reason": "  Holiday  ",
        }
    )
    assert blackout.starts_at == datetime(2026, 11, 26, 6, tzinfo=UTC)
    assert blackout.starts_at.utcoffset() == timedelta(0)
    assert blackout.reason == "Holiday"
    with pytest.raises(ValidationError):
        BlackoutPeriodCreate.model_validate(
            {
                "starts_at": "2026-11-26T00:00:00",
                "ends_at": "2026-11-27T00:00:00",
                "timezone": CHICAGO,
            }
        )
    with pytest.raises(ValidationError):
        BlackoutPeriodCreate.model_validate(
            {
                "starts_at": "2026-11-27T00:00:00Z",
                "ends_at": "2026-11-26T00:00:00Z",
                "timezone": CHICAGO,
            }
        )
    with pytest.raises(ValidationError):
        BlackoutPeriodCreate.model_validate(
            {
                "starts_at": "2026-01-01T00:00:00Z",
                "ends_at": "2027-06-01T00:00:00Z",
                "timezone": CHICAGO,
            }
        )
    with pytest.raises(ValidationError):
        BlackoutPeriodUpdate()


def test_qualification_contract_blocks_review_fields_and_urls() -> None:
    record = QualificationCreate(
        qualification_type=QualificationType.LICENSE,
        title="  Master plumber  ",
        jurisdiction="TX",
        reference_last4="1234",
        expires_on=date(2027, 1, 1),
        evidence_reference="odoo-doc:4411",
    )
    assert record.title == "Master plumber"
    for field in ("status", "review_status", "reviewed_by", "vendor_id", "submitted_at"):
        with pytest.raises(ValidationError):
            QualificationCreate.model_validate(
                {"qualification_type": "LICENSE", "title": "License", field: "APPROVED"}
            )
    for reference in (
        "https://evil.example/doc.pdf",
        "javascript:alert(1)//",
        "../../secret",
        "s3://bucket/key",
    ):
        with pytest.raises(ValidationError):
            QualificationCreate.model_validate(
                {
                    "qualification_type": "LICENSE",
                    "title": "License",
                    "evidence_reference": reference,
                }
            )
    with pytest.raises(ValidationError):
        QualificationCreate.model_validate(
            {"qualification_type": "LICENSE", "title": "License", "reference_last4": "123456"}
        )
    with pytest.raises(ValidationError):
        QualificationUpdate()
    with pytest.raises(ValidationError):
        QualificationUpdate.model_validate({"title": "   "})
    with pytest.raises(ValidationError):
        QualificationReviewDecision.model_validate({"decision": "APPROVED", "reason": ""})


# --- Timezone-safe expansion ---------------------------------------------------------


def test_weekly_window_keeps_local_time_across_dst() -> None:
    # 2026-03-08 is the US spring-forward Sunday; 2026-11-01 is fall-back Sunday.
    rule = RuleWindow(
        worker_id=None, weekday=6, start_time=time(9), end_time=time(17), timezone=CHICAGO
    )
    intervals = expand(
        [rule],
        [],
        datetime(2026, 3, 1, tzinfo=UTC),
        datetime(2026, 3, 9, tzinfo=UTC),
    )
    assert [(item.starts_at, item.ends_at) for item in intervals] == [
        (datetime(2026, 3, 1, 15, tzinfo=UTC), datetime(2026, 3, 1, 23, tzinfo=UTC)),
        (datetime(2026, 3, 8, 14, tzinfo=UTC), datetime(2026, 3, 8, 22, tzinfo=UTC)),
    ]
    november = expand(
        [rule],
        [],
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 11, 2, tzinfo=UTC),
    )
    assert [(item.starts_at, item.ends_at) for item in november] == [
        (datetime(2026, 11, 1, 15, tzinfo=UTC), datetime(2026, 11, 1, 23, tzinfo=UTC)),
    ]


def test_blackouts_subtract_by_scope_and_validity_is_respected() -> None:
    worker_a, worker_b = uuid.uuid4(), uuid.uuid4()
    rules = [
        RuleWindow(worker_a, 0, time(8), time(12), "UTC"),
        RuleWindow(worker_b, 0, time(8), time(12), "UTC"),
        RuleWindow(None, 1, time(8), time(12), "UTC", valid_from=date(2026, 10, 13)),
    ]
    blackouts = [
        Blackout(worker_a, datetime(2026, 10, 5, 9, tzinfo=UTC), datetime(2026, 10, 5, 10, tzinfo=UTC)),
    ]
    intervals = expand(
        rules,
        blackouts,
        datetime(2026, 10, 5, tzinfo=UTC),
        datetime(2026, 10, 7, tzinfo=UTC),
    )
    a = [(i.starts_at.hour, i.ends_at.hour) for i in intervals if i.worker_id == worker_a]
    b = [(i.starts_at.hour, i.ends_at.hour) for i in intervals if i.worker_id == worker_b]
    assert a == [(8, 9), (10, 12)]
    assert b == [(8, 12)]
    # Tuesday 2026-10-06 precedes the org-wide rule's valid_from.
    assert not [i for i in intervals if i.worker_id is None]

    company_blackout = [
        Blackout(None, datetime(2026, 10, 5, tzinfo=UTC), datetime(2026, 10, 6, tzinfo=UTC))
    ]
    assert expand(
        rules[:2],
        company_blackout,
        datetime(2026, 10, 5, tzinfo=UTC),
        datetime(2026, 10, 6, tzinfo=UTC),
    ) == []


def test_window_overlap_detection() -> None:
    base = RuleWindow(None, 2, time(9), time(12), CHICAGO)
    assert windows_overlap(base, RuleWindow(None, 2, time(11), time(13), CHICAGO))
    assert not windows_overlap(base, RuleWindow(None, 2, time(12), time(13), CHICAGO))
    assert not windows_overlap(base, RuleWindow(None, 3, time(9), time(12), CHICAGO))
    bounded = RuleWindow(None, 2, time(9), time(12), CHICAGO, valid_until=date(2026, 1, 31))
    later = RuleWindow(None, 2, time(9), time(12), CHICAGO, valid_from=date(2026, 2, 1))
    assert not windows_overlap(bounded, later)


# --- Principal-derived scope and cross-provider substitution -------------------------


@pytest.mark.asyncio
async def test_scope_requires_a_linked_provider(monkeypatch) -> None:
    async def no_vendor(self, user, *, lock=False):
        return None

    monkeypatch.setattr(
        "app.domains.workforce.provider_scope.ProviderCatalogRepository.vendor_for_user",
        no_vendor,
    )
    with pytest.raises(DomainError) as denied:
        await provider_vendor(FakeSession(), make_user())  # type: ignore[arg-type]
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_locked_provider_cannot_write(monkeypatch) -> None:
    vendor = make_vendor(VendorStatus.SUSPENDED)

    async def found(self, user, *, lock=False):
        return vendor

    monkeypatch.setattr(
        "app.domains.workforce.provider_scope.ProviderCatalogRepository.vendor_for_user",
        found,
    )
    assert await provider_vendor(FakeSession(), make_user()) is vendor  # type: ignore[arg-type]
    with pytest.raises(DomainError) as locked:
        await provider_vendor(FakeSession(), make_user(), write=True)  # type: ignore[arg-type]
    assert locked.value.code == "PROVIDER_NOT_EDITABLE"


@pytest.mark.asyncio
async def test_foreign_worker_is_not_found() -> None:
    with pytest.raises(DomainError) as hidden:
        await provider_worker(FakeSession(scalar=[None]), make_vendor(), uuid.uuid4())  # type: ignore[arg-type]
    assert hidden.value.status_code == 404


@pytest.mark.asyncio
async def test_foreign_offer_decision_is_not_found_and_not_delegated(monkeypatch) -> None:
    patch_scope(monkeypatch, work_service_module, make_vendor(VendorStatus.ACTIVE))

    class ExplodingDispatch:
        def __init__(self, _session) -> None:
            raise AssertionError("dispatch authority must not be reached")

    monkeypatch.setattr(work_service_module, "DispatchService", ExplodingDispatch)
    session = FakeSession(scalar=[None])
    with pytest.raises(DomainError) as hidden:
        await ProviderWorkService(session).decide_offer(  # type: ignore[arg-type]
            uuid.uuid4(), make_user(), ProviderOfferDecision(accept=True)
        )
    assert hidden.value.code == "OFFER_NOT_FOUND"
    assert session.commits == 0


@pytest.mark.asyncio
async def test_foreign_qualification_is_not_found(monkeypatch) -> None:
    patch_scope(monkeypatch, qualification_service_module, make_vendor())
    session = FakeSession(scalar=[None])
    with pytest.raises(DomainError) as hidden:
        await ProviderQualificationService(session).update(  # type: ignore[arg-type]
            uuid.uuid4(),
            make_user(),
            QualificationUpdate(title="Changed"),
            expected_version=1,
        )
    assert hidden.value.status_code == 404
    assert session.commits == 0


@pytest.mark.asyncio
async def test_foreign_availability_rule_is_not_found(monkeypatch) -> None:
    patch_scope(monkeypatch, availability_service_module, make_vendor())
    session = FakeSession(scalar=[None])
    with pytest.raises(DomainError) as hidden:
        await ProviderAvailabilityService(session).delete_rule(  # type: ignore[arg-type]
            uuid.uuid4(), make_user(), expected_version=1
        )
    assert hidden.value.code == "AVAILABILITY_RULE_NOT_FOUND"


# --- Availability service rules -------------------------------------------------------


def _rule(vendor: Vendor, **overrides) -> ProviderAvailabilityRule:
    values = {
        "id": uuid.uuid4(),
        "vendor_id": vendor.id,
        "worker_id": None,
        "weekday": 0,
        "start_time": time(8),
        "end_time": time(12),
        "timezone": CHICAGO,
        "valid_from": None,
        "valid_until": None,
        "active": True,
        "version": 1,
    }
    values.update(overrides)
    return ProviderAvailabilityRule(**values)


@pytest.mark.asyncio
async def test_overlapping_rule_is_rejected(monkeypatch) -> None:
    vendor = make_vendor()
    calls = patch_scope(monkeypatch, availability_service_module, vendor)
    existing = _rule(vendor)
    session = FakeSession(scalar=[0], scalars=[[existing]])
    with pytest.raises(DomainError) as conflict:
        await ProviderAvailabilityService(session).create_rule(  # type: ignore[arg-type]
            make_user(),
            AvailabilityRuleCreate(
                weekday=0, start_time=time(11), end_time=time(15), timezone=CHICAGO
            ),
        )
    assert conflict.value.code == "AVAILABILITY_OVERLAP"
    assert calls == [{"lock": True, "write": True}]
    assert session.commits == 0


@pytest.mark.asyncio
async def test_mixed_timezones_in_one_scope_are_rejected(monkeypatch) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, availability_service_module, vendor)
    session = FakeSession(scalar=[0], scalars=[[_rule(vendor)]])
    with pytest.raises(DomainError) as conflict:
        await ProviderAvailabilityService(session).create_rule(  # type: ignore[arg-type]
            make_user(),
            AvailabilityRuleCreate(
                weekday=3, start_time=time(8), end_time=time(12), timezone="America/New_York"
            ),
        )
    assert conflict.value.code == "AVAILABILITY_TIMEZONE_CONFLICT"


@pytest.mark.asyncio
async def test_rule_create_persists_and_audits(monkeypatch) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, availability_service_module, vendor)
    session = FakeSession(scalar=[0], scalars=[[_rule(vendor)]])
    user = make_user()
    result = await ProviderAvailabilityService(session).create_rule(  # type: ignore[arg-type]
        user,
        AvailabilityRuleCreate(
            weekday=0, start_time=time(12), end_time=time(17), timezone=CHICAGO
        ),
        correlation_id="corr-1",
    )
    assert result.vendor_id == vendor.id
    assert result.version == 1
    assert session.commits == 1
    audit = [item for item in session.added if item.__class__.__name__ == "AuditLog"]
    assert audit and audit[0].action == "provider.availability.rule.create"
    assert audit[0].metadata_json["correlation_id"] == "corr-1"


@pytest.mark.asyncio
async def test_stale_rule_version_is_rejected(monkeypatch) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, availability_service_module, vendor)
    session = FakeSession(scalar=[_rule(vendor, version=4)])
    with pytest.raises(DomainError) as stale:
        await ProviderAvailabilityService(session).update_rule(  # type: ignore[arg-type]
            uuid.uuid4(),
            make_user(),
            AvailabilityRuleUpdate(end_time=time(13)),
            expected_version=3,
        )
    assert stale.value.code == "VERSION_CONFLICT"
    assert stale.value.fields == {"current_version": 4}


@pytest.mark.asyncio
async def test_rule_patch_is_revalidated_against_stored_values(monkeypatch) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, availability_service_module, vendor)
    session = FakeSession(scalar=[_rule(vendor)])
    with pytest.raises(DomainError) as invalid:
        await ProviderAvailabilityService(session).update_rule(  # type: ignore[arg-type]
            uuid.uuid4(),
            make_user(),
            AvailabilityRuleUpdate(start_time=time(13)),
            expected_version=1,
        )
    assert invalid.value.code == "INVALID_AVAILABILITY"


@pytest.mark.asyncio
async def test_preview_window_is_bounded() -> None:
    service = ProviderAvailabilityService(FakeSession())  # type: ignore[arg-type]
    start = datetime(2026, 10, 1, tzinfo=UTC)
    with pytest.raises(DomainError):
        await service.preview(make_user(), starts_at=start, ends_at=start + timedelta(days=40))
    with pytest.raises(DomainError):
        await service.preview(
            make_user(), starts_at=datetime(2026, 10, 1), ends_at=datetime(2026, 10, 2)
        )


# --- Qualification lifecycle -----------------------------------------------------------


def _qualification(vendor: Vendor, **overrides) -> ProviderQualification:
    now = datetime(2026, 9, 25, tzinfo=UTC)
    values = {
        "id": uuid.uuid4(),
        "vendor_id": vendor.id,
        "worker_id": None,
        "qualification_type": QualificationType.LICENSE,
        "title": "Master plumber",
        "issuer": "TSBPE",
        "jurisdiction": "TX",
        "reference_last4": "1234",
        "issued_on": date(2024, 1, 1),
        "expires_on": date(2027, 1, 1),
        "evidence_reference": None,
        "status": QualificationStatus.DRAFT,
        "review_status": QualificationReviewStatus.NOT_SUBMITTED,
        "review_reason": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "submitted_at": None,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return ProviderQualification(**values)


CLOCK = FixedClock(datetime(2026, 9, 25, 12, tzinfo=UTC))


@pytest.mark.asyncio
async def test_submit_moves_draft_to_pending_review(monkeypatch) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, qualification_service_module, vendor)
    record = _qualification(vendor)
    session = FakeSession(scalar=[record])
    result = await ProviderQualificationService(session, clock=CLOCK).submit(  # type: ignore[arg-type]
        record.id, make_user(), expected_version=1
    )
    assert result.status == QualificationStatus.SUBMITTED
    assert result.review_status == QualificationReviewStatus.PENDING_REVIEW
    assert result.submitted_at == CLOCK.now()
    assert result.version == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"expires_on": date(2026, 1, 1)}, "QUALIFICATION_EXPIRED"),
        ({"expires_on": None}, "QUALIFICATION_EXPIRY_REQUIRED"),
        ({"status": QualificationStatus.SUBMITTED}, "QUALIFICATION_NOT_SUBMITTABLE"),
    ],
)
async def test_submit_guards(monkeypatch, overrides: dict, code: str) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, qualification_service_module, vendor)
    record = _qualification(vendor, **overrides)
    session = FakeSession(scalar=[record])
    with pytest.raises(DomainError) as refused:
        await ProviderQualificationService(session, clock=CLOCK).submit(  # type: ignore[arg-type]
            record.id, make_user(), expected_version=1
        )
    assert refused.value.code == code
    assert session.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "review_status",
    [QualificationReviewStatus.PENDING_REVIEW, QualificationReviewStatus.APPROVED],
)
async def test_pending_or_approved_qualifications_are_locked(monkeypatch, review_status) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, qualification_service_module, vendor)
    record = _qualification(
        vendor, status=QualificationStatus.SUBMITTED, review_status=review_status
    )
    with pytest.raises(DomainError) as locked:
        await ProviderQualificationService(FakeSession(scalar=[record]), clock=CLOCK).update(  # type: ignore[arg-type]
            record.id, make_user(), QualificationUpdate(title="Changed"), expected_version=1
        )
    assert locked.value.code == "QUALIFICATION_LOCKED"


@pytest.mark.asyncio
async def test_editing_a_returned_qualification_makes_it_a_draft_again(monkeypatch) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, qualification_service_module, vendor)
    record = _qualification(
        vendor,
        status=QualificationStatus.SUBMITTED,
        review_status=QualificationReviewStatus.INFORMATION_REQUESTED,
        review_reason="Upload the current policy declarations page",
        version=3,
    )
    result = await ProviderQualificationService(FakeSession(scalar=[record]), clock=CLOCK).update(  # type: ignore[arg-type]
        record.id,
        make_user(),
        QualificationUpdate(evidence_reference="policy-2026:88"),
        expected_version=3,
    )
    assert result.status == QualificationStatus.DRAFT
    assert result.review_status == QualificationReviewStatus.NOT_SUBMITTED
    assert result.review_reason == "Upload the current policy declarations page"
    assert result.evidence_reference == "policy-2026:88"
    assert result.version == 4


@pytest.mark.asyncio
async def test_evidence_upload_fails_closed(monkeypatch) -> None:
    vendor = make_vendor()
    patch_scope(monkeypatch, qualification_service_module, vendor)
    record = _qualification(vendor)
    session = FakeSession(scalar=[record])
    with pytest.raises(DomainError) as refused:
        await ProviderQualificationService(session).reject_evidence_upload(  # type: ignore[arg-type]
            record.id, make_user()
        )
    assert refused.value.code == "EVIDENCE_STORAGE_NOT_CONFIGURED"
    assert refused.value.status_code == 503
    assert session.added == []
    assert session.commits == 0


@pytest.mark.asyncio
async def test_review_only_decides_pending_submissions() -> None:
    vendor = make_vendor()
    draft = _qualification(vendor)
    with pytest.raises(DomainError) as refused:
        await ProviderQualificationService(FakeSession(scalar=[draft]), clock=CLOCK).review(  # type: ignore[arg-type]
            draft.id,
            make_user(),
            QualificationReviewDecision(decision="APPROVED", reason="Looks good"),
        )
    assert refused.value.code == "QUALIFICATION_NOT_PENDING"

    pending = _qualification(
        vendor,
        status=QualificationStatus.SUBMITTED,
        review_status=QualificationReviewStatus.PENDING_REVIEW,
    )
    reviewer = make_user()
    result = await ProviderQualificationService(FakeSession(scalar=[pending]), clock=CLOCK).review(  # type: ignore[arg-type]
        pending.id,
        reviewer,
        QualificationReviewDecision(decision="REJECTED", reason="Policy lapsed"),
    )
    assert result.review_status == QualificationReviewStatus.REJECTED
    assert result.review_reason == "Policy lapsed"
    assert pending.reviewed_by == reviewer.id
