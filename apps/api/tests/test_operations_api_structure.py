from pathlib import Path

from app.api.v1 import operations
from app.api.v1.operations.dispatcher import (
    dispatcher_queue,
    update_dispatcher_queue_item,
)
from app.api.v1.operations.router import router
from app.main import app


def test_operations_package_is_the_compatibility_facade() -> None:
    assert operations.router is router
    assert operations.dispatcher_queue is dispatcher_queue
    assert operations.update_dispatcher_queue_item is update_dispatcher_queue_item


def test_operations_routes_remain_registered_after_module_split() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/operations/bookings/{booking_id}/confirm": {"post"},
        "/api/v1/operations/vendors/{vendor_id}/credentials/{credential_type}/{jurisdiction}": {
            "put"
        },
        "/api/v1/operations/dispatcher/queue": {"get"},
        "/api/v1/operations/dispatcher/queue/{request_id}": {"patch"},
        "/api/v1/operations/workers/{worker_id}/booking-coverage": {"put"},
        "/api/v1/operations/jobs/{job_id}/match": {"post"},
        "/api/v1/operations/jobs/{job_id}/assign": {"post"},
        "/api/v1/operations/vendors/{vendor_id}/status": {"patch"},
    }
    for path, methods in expected.items():
        assert methods <= set(paths[path])


def test_same_named_operations_monolith_is_removed() -> None:
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "operations.py"
    assert not path.exists()


def test_operations_resource_modules_do_not_use_lazy_fastapi_imports() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "operations"
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "    from fastapi import HTTPException" not in source
