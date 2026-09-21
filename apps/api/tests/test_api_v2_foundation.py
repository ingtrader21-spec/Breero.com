import json
import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from app.core.errors import DomainError
from app.main import app

EXPECTED_CAPABILITIES = {
    "request_intake": True,
    "instant_booking": False,
    "online_payments": False,
    "automatic_assignment": False,
    "provider_self_service": False,
    "marketplace_matching": False,
    "messaging": False,
    "reviews": False,
}


class ErrorContext(BaseModel):
    resource_id: uuid.UUID
    observed_at: datetime


@contextmanager
def _temporary_route(
    path: str,
    endpoint: Callable[..., Any],
    *,
    methods: list[str],
) -> Iterator[None]:
    existing_ids = {id(route) for route in app.router.routes}
    app.add_api_route(path, endpoint, methods=methods, include_in_schema=False)
    route = next(route for route in app.router.routes if id(route) not in existing_ids)
    app.openapi_schema = None
    try:
        yield
    finally:
        app.router.routes.remove(route)
        app.openapi_schema = None


@contextmanager
def _approved_breero_origin() -> Iterator[str]:
    client = TestClient(app, raise_server_exceptions=False)
    client.get("/health/live")  # Build the middleware stack before inspection.
    middleware = app.middleware_stack
    while middleware is not None and not isinstance(middleware, CORSMiddleware):
        middleware = getattr(middleware, "app", None)
    assert isinstance(middleware, CORSMiddleware)
    origin = "https://breero.com"
    original = list(middleware.allow_origins)
    middleware.allow_origins = [*original, origin]
    try:
        yield origin
    finally:
        middleware.allow_origins = original


def test_v2_capabilities_reuse_the_v1_authority() -> None:
    client = TestClient(app)

    v1 = client.get("/api/v1/public/capabilities")
    v2 = client.get("/api/v2/capabilities")

    assert v1.status_code == 200
    assert v2.status_code == 200
    assert v1.json() == EXPECTED_CAPABILITIES
    assert v2.json() == v1.json()


def test_v2_missing_routes_use_the_stable_error_contract() -> None:
    correlation_id = "marketplace-v2-test"
    response = TestClient(app).get(
        "/api/v2/not-implemented",
        headers={"X-Correlation-ID": correlation_id},
    )

    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "Not Found",
        "correlation_id": correlation_id,
        "fields": None,
    }
    assert response.headers["x-correlation-id"] == correlation_id
    assert response.headers["x-request-id"]


def test_v2_method_errors_preserve_the_allow_header() -> None:
    response = TestClient(app).post("/api/v2/capabilities")

    assert response.status_code == 405
    assert response.json()["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in response.headers["allow"]
    assert response.headers["x-request-id"]
    assert response.headers["x-correlation-id"]


def test_v2_http_exceptions_preserve_required_headers() -> None:
    async def throttled() -> None:
        raise HTTPException(
            status_code=429,
            detail="Slow down",
            headers={"Retry-After": "30", "WWW-Authenticate": "Bearer"},
        )

    correlation_id = "v2-http-header-test"
    with _temporary_route("/api/v2/_test/http-error", throttled, methods=["GET"]):
        response = TestClient(app).get(
            "/api/v2/_test/http-error",
            headers={"X-Correlation-ID": correlation_id},
        )

    assert response.status_code == 429
    assert response.json() == {
        "code": "TOO_MANY_REQUESTS",
        "message": "Slow down",
        "correlation_id": correlation_id,
        "fields": None,
    }
    assert response.headers["retry-after"] == "30"
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["x-correlation-id"] == correlation_id


def test_v2_domain_error_fields_are_json_encoded_losslessly() -> None:
    resource_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 26, 12, 30, tzinfo=UTC)
    amount = Decimal("9007199254740993.000000000000000001")
    context = ErrorContext(resource_id=resource_id, observed_at=observed_at)

    async def structured_failure() -> None:
        raise DomainError(
            "RESOURCE_CONFLICT",
            "The resource cannot be changed.",
            409,
            fields={
                "resource_id": resource_id,
                "amount": amount,
                "observed_at": observed_at,
                "context": context,
            },
        )

    with _temporary_route(
        "/api/v2/_test/domain-error",
        structured_failure,
        methods=["GET"],
    ):
        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/v2/_test/domain-error",
            headers={"X-Correlation-ID": "structured-domain-error"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "RESOURCE_CONFLICT"
    assert body["correlation_id"] == "structured-domain-error"
    assert body["fields"] == {
        "resource_id": str(resource_id),
        "amount": str(amount),
        "observed_at": observed_at.isoformat(),
        "context": {
            "resource_id": str(resource_id),
            "observed_at": observed_at.isoformat(),
        },
    }


def test_v2_unhandled_exceptions_use_the_stable_error_contract() -> None:
    async def unexpected_failure() -> None:
        raise RuntimeError("sensitive implementation detail")

    request_id = "v2-unhandled-request"
    correlation_id = "v2-unhandled-correlation"
    with _temporary_route(
        "/api/v2/_test/unhandled",
        unexpected_failure,
        methods=["GET"],
    ):
        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/v2/_test/unhandled",
            headers={
                "X-Request-ID": request_id,
                "X-Correlation-ID": correlation_id,
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "An unexpected error occurred.",
        "correlation_id": correlation_id,
        "fields": None,
    }
    assert "sensitive implementation detail" not in response.text
    assert response.headers["x-request-id"] == request_id
    assert response.headers["x-correlation-id"] == correlation_id
    assert response.headers["x-content-type-options"] == "nosniff"


def test_v2_unhandled_error_preserves_the_approved_breero_cors_policy() -> None:
    async def unexpected_failure() -> None:
        raise RuntimeError("must not be disclosed")

    with _temporary_route(
        "/api/v2/_test/cors-unhandled",
        unexpected_failure,
        methods=["GET"],
    ), _approved_breero_origin() as origin:
        client = TestClient(app, raise_server_exceptions=False)
        allowed = client.get(
            "/api/v2/_test/cors-unhandled",
            headers={"Origin": origin, "X-Correlation-ID": "cors-allowed"},
        )
        denied = client.get(
            "/api/v2/_test/cors-unhandled",
            headers={"Origin": "https://attacker.example"},
        )
        preflight = client.options(
            "/api/v2/capabilities",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Correlation-ID",
            },
        )

    assert allowed.status_code == 500
    assert allowed.headers["access-control-allow-origin"] == origin
    assert allowed.headers["x-correlation-id"] == "cors-allowed"
    exposed = {
        header.strip().lower()
        for header in allowed.headers["access-control-expose-headers"].split(",")
    }
    assert {"x-request-id", "x-correlation-id"} <= exposed
    assert allowed.json()["code"] == "INTERNAL_SERVER_ERROR"
    assert "must not be disclosed" not in allowed.text
    assert "access-control-allow-origin" not in denied.headers
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin


def test_v2_cors_exposes_trace_headers_on_success() -> None:
    with _approved_breero_origin() as origin:
        response = TestClient(app).get(
            "/api/v2/capabilities",
            headers={"Origin": origin},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    exposed = {
        header.strip().lower()
        for header in response.headers["access-control-expose-headers"].split(",")
    }
    assert {"x-request-id", "x-correlation-id"} <= exposed
    assert response.headers["x-request-id"]
    assert response.headers["x-correlation-id"]


def test_v1_missing_routes_keep_the_existing_fastapi_contract() -> None:
    response = TestClient(app).get("/api/v1/not-implemented")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_unsafe_trace_headers_are_not_reflected() -> None:
    response = TestClient(app).get(
        "/api/v2/capabilities",
        headers={
            "X-Request-ID": "contains spaces",
            "X-Correlation-ID": "also contains spaces",
        },
    )

    request_id = response.headers["x-request-id"]
    correlation_id = response.headers["x-correlation-id"]
    assert request_id == correlation_id
    assert re.fullmatch(r"[0-9a-f-]{36}", request_id)
    uuid.UUID(request_id)


def test_openapi_exposes_only_the_real_v2_foundation_route() -> None:
    schema = app.openapi()

    assert schema["paths"]["/api/v2/capabilities"]["get"]["operationId"] == (
        "get_v2_capabilities"
    )
    assert "ApiError" in schema["components"]["schemas"]
    assert "/api/v2/project-requests" not in schema["paths"]


def _stable_operation_contract(operation: dict[str, Any]) -> dict[str, Any]:
    """Exclude additive vendor extensions owned by later contract layers."""

    return {key: value for key, value in operation.items() if not key.startswith("x-")}


def test_checked_in_openapi_matches_the_runtime_v2_contract() -> None:
    api_root = Path(__file__).resolve().parents[1]
    checked_in = json.loads((api_root / "openapi.json").read_text(encoding="utf-8"))
    runtime = app.openapi()

    assert checked_in["info"] == runtime["info"]
    checked_operation = checked_in["paths"]["/api/v2/capabilities"]["get"]
    runtime_operation = runtime["paths"]["/api/v2/capabilities"]["get"]
    assert _stable_operation_contract(checked_operation) == _stable_operation_contract(
        runtime_operation
    )
    for schema_name in ("ApiError", "PublicCapabilities"):
        assert checked_in["components"]["schemas"][schema_name] == (
            runtime["components"]["schemas"][schema_name]
        )
