"""Generate deterministic OpenAPI and endpoint-policy artifacts for CI review."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

# Canonical contract generation inventories release-gated booking routes without
# enabling them in production. Runtime mounting remains governed by Settings.
os.environ.setdefault("GEOCODING_ENABLED", "true")
os.environ.setdefault("SCHEDULING_ENABLED", "true")
os.environ.setdefault("PUBLIC_BOOKING_API_ENABLED", "true")

from app.api.policy_registry import get_endpoint_registry, iter_api_route_contexts  # noqa: E402
from app.main import app  # noqa: E402

OPENAPI_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
POLICY_IDENTITY_FIELDS = {"path", "method", "operation_id"}


def _policy_payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key not in POLICY_IDENTITY_FIELDS}


def _apply_registry_to_schema(
    schema: dict[str, Any],
    registry: dict[str, Any],
) -> None:
    """Apply the canonical registry to the generated schema deterministically.

    The runtime application already installs the same overlay for served OpenAPI.
    The release generator deliberately reapplies it so artifact generation never
    depends on FastAPI schema-cache timing or import order.
    """

    paths = schema.get("paths")
    if not isinstance(paths, dict):
        raise SystemExit("OpenAPI schema is missing its paths object")

    endpoints = registry.get("endpoints")
    if not isinstance(endpoints, list):
        raise SystemExit("Endpoint registry is missing its endpoints list")

    schema_operations = {(route.path, method) for route in iter_api_route_contexts(app) if route.include_in_schema for method in (route.methods or set())}
    for raw_entry in endpoints:
        if not isinstance(raw_entry, dict):
            raise SystemExit("Endpoint registry contains a non-object entry")
        entry = {str(key): value for key, value in raw_entry.items()}
        path = str(entry["path"])
        method = str(entry["method"]).upper()
        if (path, method) not in schema_operations:
            continue
        path_item = paths.get(path)
        if not isinstance(path_item, dict):
            raise SystemExit(f"OpenAPI is missing registered path {path}")
        operation = path_item.get(method.lower())
        if not isinstance(operation, dict):
            raise SystemExit(f"OpenAPI is missing registered operation {method} {path}")
        policy = operation.setdefault("x-breero-policy", {})
        if not isinstance(policy, dict):
            raise SystemExit(f"Invalid endpoint policy container for {method} {path}")
        policy[method] = _policy_payload(entry)


openapi_target = Path(os.getenv("OPENAPI_PATH", "openapi.json"))
registry_target = Path(os.getenv("ENDPOINT_REGISTRY_PATH", "endpoint-registry.json"))

registry = get_endpoint_registry(app)
schema = app.openapi()
_apply_registry_to_schema(schema, registry)
schema["x-breero-endpoint-registry-digest"] = registry["digest"]

operation_ids: dict[str, str] = {}
for path, operations in schema.get("paths", {}).items():
    if not isinstance(operations, dict):
        continue
    for method, operation in operations.items():
        if method not in OPENAPI_METHODS:
            continue
        if not isinstance(operation, dict):
            raise SystemExit(f"Invalid OpenAPI operation for {method.upper()} {path}")
        operation_id = operation.get("operationId")
        if not operation_id:
            raise SystemExit(f"Missing operationId for {method.upper()} {path}")
        if operation_id in operation_ids:
            raise SystemExit(
                f"Duplicate operationId {operation_id}: {operation_ids[operation_id]} and "
                f"{method.upper()} {path}"
            )
        policy = operation.get("x-breero-policy")
        if not isinstance(policy, dict) or method.upper() not in policy:
            raise SystemExit(f"Missing endpoint policy for {method.upper()} {path}")
        operation_ids[str(operation_id)] = f"{method.upper()} {path}"

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
for target, document in ((openapi_target, schema), (registry_target, registry)):
    content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not target.exists() or target.read_text() != content:
            raise SystemExit(f"Stale generated artifact: {target}")
    else:
        target.write_text(content)
print(
    f"validated {len(schema.get('paths', {}))} paths / {len(operation_ids)} operations / "
    f"{len(registry['endpoints'])} endpoint policies"
)
print(f"endpoint registry digest: {registry['digest']}")
print(openapi_target)
print(registry_target)
