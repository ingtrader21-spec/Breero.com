"""Read-only, deterministic source inventory; no database or provider calls.

Run with the API's Python environment. Runtime imports run in a separate process
with a clean environment and an empty working directory, so .env files and live
credentials cannot affect the inventory. This records evidence, not authorization.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/architecture/SOURCE_INVENTORY.json"
METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
PROFILES = {
    "default": {},
    # The checked-in OpenAPI is the canonical contract surface. It inventories
    # release-gated public booking routes without enabling them in production.
    "canonical_contract": {
        "GEOCODING_ENABLED": "true",
        "SCHEDULING_ENABLED": "true",
        "PUBLIC_BOOKING_API_ENABLED": "true",
    },
    "implemented_routes": {
        "GEOCODING_ENABLED": "true",
        "PAYMENTS_ENABLED": "true",
        "STRIPE_ENABLED": "true",
        "PAYOUT_ENABLED": "true",
        "PAID_LEADS_ENABLED": "true",
    },
}
UNREGISTERED = (
    "owner",
    "audience",
    "permission",
    "tenant_scope",
    "record_policy",
    "capability",
    "rate_limit_class",
    "idempotency_requirement",
    "request_hash_policy",
    "optimistic_version_policy",
    "PII_classification",
    "event_effect",
    "deprecation_state",
    "replacement_endpoint",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(node: ast.AST | None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return "DYNAMIC"


def assignments(nodes):
    values = {}
    for node in nodes:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = literal(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            values[node.target.id] = literal(node.value)
    return values


def source(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}


def runtime_inventory():
    # Do not start application lifespan, request handlers, workers or exporters.
    sys.path.insert(0, str(ROOT / "apps/api"))
    from app.main import app
    from fastapi.routing import APIRoute

    schema = app.openapi()
    operations = []
    routes = []
    for mounted in app.routes:
        if isinstance(mounted, APIRoute):
            routes.append(mounted)
        elif hasattr(mounted, "effective_route_contexts"):
            # FastAPI 0.13x preserves the original route *and* an effective
            # context. Inventory the effective context so nested router prefixes
            # match the real mounted/OpenAPI path.
            routes.extend(
                context
                for context in mounted.effective_route_contexts()
                if isinstance(context.original_route, APIRoute)
            )
    for route in routes:
        dependencies = []

        def visit(dep, dependencies):
            call = dep.call
            if call is not None:
                entry = {
                    "callable": f"{getattr(call, '__module__', type(call).__module__)}.{getattr(call, '__qualname__', type(call).__name__)}"
                }
                if inspect.isfunction(call):
                    closed = inspect.getclosurevars(call).nonlocals
                    for key in ("allowed_roles", "required"):
                        if key in closed:
                            entry[key] = sorted(
                                str(getattr(v, "value", v)) for v in closed[key]
                            )
                if entry not in dependencies:
                    dependencies.append(entry)
            for child in dep.dependencies:
                visit(child, dependencies)

        for dependency in route.dependant.dependencies:
            visit(dependency, dependencies)
        for method in sorted(route.methods):
            operation = (
                schema.get("paths", {}).get(route.path, {}).get(method.lower(), {})
            )
            endpoint_file = Path(inspect.getsourcefile(route.endpoint)).resolve()
            operations.append(
                {
                    "method": method,
                    "path": route.path,
                    "version": "v2"
                    if route.path.startswith("/api/v2/")
                    else "v1"
                    if route.path.startswith("/api/v1/")
                    else "internal"
                    if route.path.startswith("/internal/")
                    else "platform",
                    "domain": route.endpoint.__module__,
                    "source": endpoint_file.relative_to(ROOT).as_posix(),
                    "handler": route.endpoint.__name__,
                    "runtime_operation_id": getattr(route, "unique_id", None),
                    "included_in_openapi": route.include_in_schema,
                    "operation_id": operation.get("operationId"),
                    "authentication": {
                        "openapi_security": operation.get("security", []),
                        "dependencies": dependencies,
                    },
                    "request_schema": operation.get("requestBody", {}),
                    "parameters": operation.get("parameters", []),
                    "response_schema": operation.get("responses", {}),
                    "error_contract": {
                        k: v
                        for k, v in operation.get("responses", {}).items()
                        if k.startswith(("4", "5"))
                    },
                    **{key: "UNREGISTERED" for key in UNREGISTERED},
                }
            )
    expected = {
        (method.upper(), path)
        for path, item in schema["paths"].items()
        for method in item
        if method in METHODS
    }
    grouped = {}
    for row in operations:
        grouped.setdefault((row["method"], row["path"]), []).append(row)
    observed = {
        key
        for key, rows in grouped.items()
        if any(row["included_in_openapi"] for row in rows)
    }
    if observed != expected:
        raise RuntimeError(
            "Runtime enumeration differs from OpenAPI; inventory is incomplete"
        )
    duplicate_route_registrations = []
    logical_operations = []
    for (method, path), rows in sorted(grouped.items()):
        if len(rows) > 1:
            duplicate_route_registrations.append(
                {
                    "method": method,
                    "path": path,
                    "registrations": [
                        {
                            "source": row["source"],
                            "handler": row["handler"],
                            "runtime_operation_id": row["runtime_operation_id"],
                        }
                        for row in rows
                    ],
                }
            )
        # Dispatch ordering is significant; preserve the first effective
        # registration while recording every alternate registration above.
        selected = dict(rows[0])
        selected["duplicate_registration_count"] = len(rows)
        logical_operations.append(selected)
    saved = json.loads((ROOT / "apps/api/openapi.json").read_text(encoding="utf-8"))
    return {
        "framework_routes": [
            {"path": route.path, "methods": sorted(route.methods or [])}
            for route in app.routes
            if not isinstance(route, APIRoute)
            and hasattr(route, "path")
            and hasattr(route, "methods")
        ],
        "paths": len(schema["paths"]),
        "openapi_operations": sum(
            method in METHODS for item in schema["paths"].values() for method in item
        ),
        "openapi_matches_artifact": schema == saved,
        "contract_sha256": hashlib.sha256(
            (json.dumps(schema, indent=2, sort_keys=True) + "\n").encode()
        ).hexdigest(),
        "duplicate_route_registrations": duplicate_route_registrations,
        "operations": logical_operations,
    }


def collect(baseline: str):
    modules = []
    revisions = []
    flags = []
    tasks = []
    route_declarations = []
    for path in sorted((ROOT / "apps/api/app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                values = assignments(node.body)
                bases = [ast.unparse(base) for base in node.bases]
                classes.append(
                    {
                        "name": node.name,
                        "bases": bases,
                        "table": values.get("__tablename__"),
                        "enum_values": values
                        if any("Enum" in base for base in bases)
                        else {},
                    }
                )
                if node.name in {"Settings", "ObservabilitySettings"}:
                    for field in node.body:
                        if isinstance(field, ast.AnnAssign) and isinstance(
                            field.target, ast.Name
                        ):
                            name = field.target.id
                            if ast.unparse(field.annotation) == "bool" or name.endswith(
                                "_mode"
                            ):
                                flags.append(
                                    {
                                        "setting": name.upper(),
                                        "default": literal(field.value),
                                        "source": path.relative_to(ROOT).as_posix(),
                                    }
                                )
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call) or not isinstance(
                        decorator.func, ast.Attribute
                    ):
                        continue
                    if decorator.func.attr in METHODS:
                        route_declarations.append(
                            {
                                "source": path.relative_to(ROOT).as_posix(),
                                "handler": node.name,
                                "method": decorator.func.attr.upper(),
                                "local_path": literal(decorator.args[0])
                                if decorator.args
                                else "",
                                "router": ast.unparse(decorator.func.value),
                            }
                        )
                    if decorator.func.attr == "task":
                        tasks.append(
                            {
                                "source": path.relative_to(ROOT).as_posix(),
                                "function": node.name,
                                "configuration": {
                                    kw.arg: literal(kw.value)
                                    for kw in decorator.keywords
                                },
                            }
                        )
        modules.append({**source(path), "classes": classes})
    for path in sorted((ROOT / "apps/api/migrations/versions").glob("*.py")):
        values = assignments(ast.parse(path.read_text(encoding="utf-8-sig")).body)
        revisions.append(
            {
                **source(path),
                "revision": values["revision"],
                "down_revision": values["down_revision"],
            }
        )
    parents = {
        parent
        for row in revisions
        for parent in (
            row["down_revision"]
            if isinstance(row["down_revision"], (list, tuple))
            else [row["down_revision"]]
        )
        if parent
    }
    frontend = []
    for app in ("web", "partner", "ops", "admin"):
        app_root = ROOT / f"apps/{app}/app"
        for path in sorted(app_root.rglob("*")):
            if path.name not in {
                "page.tsx",
                "page.ts",
                "route.ts",
                "route.tsx",
                "page.jsx",
                "route.js",
            }:
                continue
            parts = [
                part
                for part in path.parent.relative_to(app_root).parts
                if not part.startswith(("(", "@"))
            ]
            frontend.append(
                {
                    **source(path),
                    "app": app,
                    "route": "/" + "/".join(parts),
                    "kind": "handler" if path.stem == "route" else "page",
                }
            )
    deployment = sorted(
        {
            *ROOT.glob("docker-compose*.yml"),
            *(ROOT / "deploy").rglob("*.yml"),
            *(ROOT / "deploy").rglob("*.yaml"),
        }
    )
    profiles = {}
    with tempfile.TemporaryDirectory(prefix="breero-inventory-") as empty:
        for name, overrides in PROFILES.items():
            env = {
                "PATH": os.defpath,
                "APP_ENV": "test",
                "OTEL_ENABLED": "false",
                "PYTHONDONTWRITEBYTECODE": "1",
                **overrides,
            }
            if os.name == "nt":
                # A Windows child process needs core OS variables even when the
                # application environment is intentionally scrubbed. Preserve
                # only non-credential system plumbing; the empty cwd still
                # prevents repository .env discovery.
                for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP"):
                    value = os.environ.get(key)
                    if value:
                        env[key] = value
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--runtime-profile",
                    name,
                ],
                cwd=empty,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            profiles[name] = json.loads(result.stdout)
    indexed = {}
    operation_profile = {}
    profile_contract_variants = []
    for profile_name in ("canonical_contract", "implemented_routes", "default"):
        for row in profiles[profile_name]["operations"]:
            key = (row["method"], row["path"])
            previous = indexed.get(key)
            if previous is None:
                indexed[key] = row
                operation_profile[key] = profile_name
                continue
            comparable = {
                k: v
                for k, v in row.items()
                if k not in {"duplicate_registration_count"}
            }
            previous_comparable = {
                k: v
                for k, v in previous.items()
                if k not in {"duplicate_registration_count"}
            }
            if comparable != previous_comparable:
                profile_contract_variants.append(
                    {
                        "method": row["method"],
                        "path": row["path"],
                        "authoritative_profile": operation_profile[key],
                        "variant_profile": profile_name,
                        "authoritative": previous,
                        "variant": row,
                    }
                )
                # The canonical contract profile is traversed first and remains
                # authoritative for shared method/path pairs. Alternate profile
                # contracts are evidence for M02 rather than silently replacing it.
                continue
            previous["duplicate_registration_count"] = max(
                previous.get("duplicate_registration_count", 1),
                row.get("duplicate_registration_count", 1),
            )
    all_operations = sorted(
        indexed.values(), key=lambda row: (row["path"], row["method"])
    )
    for profile in profiles.values():
        profile["operations"] = [
            f"{row['method']} {row['path']}" for row in profile["operations"]
        ]
    return {
        "api_operations": all_operations,
        "profile_contract_variants": profile_contract_variants,
        "schema_version": 1,
        "baseline_main_sha": baseline,
        "scope": "Source evidence only. Test-profile imports; no deployed configuration or runtime certification.",
        "required_directories": {
            name: (ROOT / name).is_dir()
            for name in (
                "apps/api",
                "apps/web",
                "apps/partner",
                "apps/ops",
                "apps/admin",
                "packages/ui",
                "packages/types",
                "packages/api-client",
                "deploy",
                "infrastructure",
                "docs",
                "odoo-addons",
            )
        },
        "backend_modules": modules,
        "backend_domains": sorted(
            p.name
            for p in (ROOT / "apps/api/app/domains").iterdir()
            if p.is_dir() and (p / "__init__.py").exists()
        ),
        "alembic_revisions": revisions,
        "alembic_heads": sorted(
            row["revision"] for row in revisions if row["revision"] not in parents
        ),
        "openapi_artifact": source(ROOT / "apps/api/openapi.json"),
        "runtime_profiles": profiles,
        "route_declarations": route_declarations,
        "frontend_routes": frontend,
        "feature_defaults": sorted(flags, key=lambda row: row["setting"]),
        "workers": tasks,
        "deployment_files": [source(path) for path in deployment],
        "contract_sources": [
            source(path)
            for path in sorted(
                [
                    *(ROOT / "packages/types/src").glob("*.ts"),
                    *(ROOT / "packages/api-client/src").glob("*.ts"),
                    ROOT / "packages/portal/src/index.tsx",
                    ROOT / "scripts/check-frontend-openapi.mjs",
                ]
            )
        ],
        "odoo_addon_sources": [
            source(path)
            for path in sorted((ROOT / "odoo-addons").rglob("*"))
            if path.is_file() and path.suffix in {".py", ".xml", ".csv"}
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--runtime-profile", choices=PROFILES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.runtime_profile:
        print(json.dumps(runtime_inventory(), sort_keys=True))
        return
    baseline = args.source_sha or json.loads(OUTPUT.read_text(encoding="utf-8"))["baseline_main_sha"]
    if len(baseline) != 40 or any(char not in "0123456789abcdef" for char in baseline):
        parser.error("source SHA must be a full lowercase Git SHA")
    result = json.dumps(collect(baseline), indent=2, sort_keys=True) + "\n"
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != result:
            raise SystemExit(
                "Source inventory drift: review and regenerate the architecture baseline"
            )
        print(
            "PASS: source inventory matches executable source and runtime route profiles"
        )
    else:
        OUTPUT.write_text(result, encoding="utf-8")
        print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
