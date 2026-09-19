from pathlib import Path

from app.api.v1 import jobs
from app.api.v1.jobs.dependencies import worker_for_user
from app.api.v1.jobs.router import router
from app.main import app


def test_jobs_package_is_the_compatibility_facade() -> None:
    assert jobs.router is router
    assert jobs.worker_for_user is worker_for_user


def test_job_routes_remain_registered_after_module_split() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/jobs": {"get"},
        "/api/v1/jobs/{job_id}": {"get"},
        "/api/v1/jobs/{job_id}/transition": {"post"},
        "/api/v1/jobs/{job_id}/technician/{command}": {"post"},
        "/api/v1/jobs/{job_id}/diagnostic": {"post"},
        "/api/v1/jobs/{job_id}/completion": {"post"},
        "/api/v1/jobs/{job_id}/work-requests": {"get", "post"},
        "/api/v1/jobs/work-requests/{request_id}/decision": {"post"},
        "/api/v1/jobs/work-requests/{request_id}/review": {"post"},
    }
    for path, methods in expected.items():
        assert methods <= set(paths[path])


def test_same_named_jobs_monolith_is_removed() -> None:
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "jobs.py"
    assert not path.exists()


def test_jobs_resource_modules_do_not_use_lazy_fastapi_imports() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "jobs"
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "    from fastapi import HTTPException" not in source
