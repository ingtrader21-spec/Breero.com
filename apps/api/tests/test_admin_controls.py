import pytest
from pydantic import ValidationError

from app.domains.administration.schemas import AdminUserCreate, OperatingHourWrite
from app.domains.auth.models import UserRole
from app.main import app


def test_admin_provisioning_rejects_public_roles() -> None:
    with pytest.raises(ValidationError):
        AdminUserCreate(
            email="client@example.test",
            full_name="Not An Admin",
            role=UserRole.CLIENT,
        )


def test_sunday_operating_hours_are_emergency_only() -> None:
    with pytest.raises(ValidationError):
        OperatingHourWrite(
            day_of_week=1,
            start_local_time="07:00",
            end_local_time="19:00",
            emergency_only=True,
        )


def test_required_admin_and_auth_operations_are_in_openapi() -> None:
    paths = app.openapi()["paths"]
    required = {
        "/api/v1/admin/users",
        "/api/v1/admin/feature-flags",
        "/api/v1/admin/feature-flags/{flag}",
        "/api/v1/admin/operating-hours",
        "/api/v1/admin/audit-events",
        "/api/v1/auth/email/resend",
        "/api/v1/auth/phone/verify",
    }
    assert required <= paths.keys()
