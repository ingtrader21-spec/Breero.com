import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.api.policy_registry import (
    DOCUMENTATION_PATHS,
    OPENAPI_METHODS,
    POLICY_RULES,
    build_endpoint_policies,
    get_endpoint_registry,
    iter_api_route_contexts,
)
from app.main import app

REQUIRED_POLICY_FIELDS = {
    "method",
    "path",
    "operation_id",
    "policy_rule",
    "resource_owner",
    "audience",
    "authentication",
    "permission",
    "tenant_scope",
    "record_policy",
    "capability_gate",
    "idempotency_key_policy",
    "request_hash_policy",
    "if_match_version_policy",
    "request_schema",
    "response_schema",
    "emitted_effect",
    "deprecation_status",
    "rate_limit_class",
    "pii_classification",
}


def _runtime_operations() -> set[tuple[str, str]]:
    operations: set[tuple[str, str]] = set()
    for route in iter_api_route_contexts(app):
        if route.path in DOCUMENTATION_PATHS:
            continue
        for method in (route.methods or set()) & OPENAPI_METHODS:
            operations.add((method, route.path))
    return operations


def test_every_runtime_operation_has_one_complete_policy() -> None:
    document = get_endpoint_registry(app)
    endpoints = document["endpoints"]
    assert isinstance(endpoints, list)
    registered = {(entry["method"], entry["path"]) for entry in endpoints}

    assert registered == _runtime_operations()
    assert len(registered) == len(endpoints)
    assert len(registered) >= 60
    assert str(document["digest"]).startswith("sha256:")
    assert ("GET", "/api/v1/public/capabilities") in registered
    assert ("POST", "/api/v1/service-requests") in registered
    assert ("GET", "/api/v2/capabilities") in registered
    assert ("GET", "/health/ready") in registered
    assert ("GET", "/ready") in registered

    for entry in endpoints:
        assert REQUIRED_POLICY_FIELDS == set(entry)
        for field in REQUIRED_POLICY_FIELDS - {"request_schema", "response_schema"}:
            assert str(entry[field]).strip(), f"{entry['method']} {entry['path']} has empty {field}"


def test_policy_rule_names_are_unique_and_explicit() -> None:
    names = [rule.name for rule in POLICY_RULES]
    assert len(names) == len(set(names))
    for rule in POLICY_RULES:
        assert rule.path_pattern.startswith("/")
        assert rule.resource_owner
        assert rule.permission
        assert rule.capability_gate
        assert rule.record_policy


def test_openapi_operations_embed_the_registry_policy() -> None:
    document = get_endpoint_registry(app)
    schema = app.openapi()
    assert schema["x-breero-endpoint-registry-digest"] == document["digest"]

    for entry in document["endpoints"]:
        if entry["path"] == "/metrics":
            assert entry["path"] not in schema["paths"]
            continue
        operation = schema["paths"][entry["path"]][entry["method"].lower()]
        method_policies = operation["x-breero-policy"]
        assert set(method_policies) == {entry["method"]}
        embedded = method_policies[entry["method"]]
        assert embedded["policy_rule"] == entry["policy_rule"]
        assert embedded["resource_owner"] == entry["resource_owner"]
        assert embedded["permission"] == entry["permission"]
        assert embedded["capability_gate"] == entry["capability_gate"]


def test_high_risk_route_families_are_never_registered_as_always_enabled() -> None:
    endpoints = get_endpoint_registry(app)["endpoints"]
    high_risk_prefixes = (
        "/api/v1/payments",
        "/api/v1/finance",
        "/api/v1/provider/leads",
    )
    for entry in endpoints:
        if entry["path"].startswith(high_risk_prefixes):
            assert entry["capability_gate"] != "always"


@pytest.mark.parametrize("path", ["/api/v1/unregistered-resource", "/ready/details"])
def test_unowned_route_still_fails_closed(path: str) -> None:
    isolated = FastAPI()

    @isolated.get(path)
    def unregistered():
        return {}

    with pytest.raises(RuntimeError, match=f"unmatched=GET {path}"):
        build_endpoint_policies(isolated)


def test_readiness_alias_uses_the_same_policy_as_the_health_endpoint() -> None:
    endpoints = get_endpoint_registry(app)["endpoints"]
    ready = next(entry for entry in endpoints if entry["path"] == "/ready")
    health = next(entry for entry in endpoints if entry["path"] == "/health/ready")
    identity_fields = {"path", "operation_id"}
    assert {key: value for key, value in ready.items() if key not in identity_fields} == {
        key: value for key, value in health.items() if key not in identity_fields
    }


def test_committed_contract_artifacts_match_the_runtime_registry() -> None:
    api_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "scripts/generate_openapi.py", "--check"],
        cwd=api_root,
        env={**os.environ, "OPENAPI_PATH": str(api_root / "openapi.json"),
             "ENDPOINT_REGISTRY_PATH": str(api_root / "endpoint-registry.json")},
        check=True,
        capture_output=True,
        text=True,
    )
