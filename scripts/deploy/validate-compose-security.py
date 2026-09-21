#!/usr/bin/env python3
"""Validate BREERO deployment configuration without contacting a live host."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DIGEST_IMAGE = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")
PINNED_ACTION = re.compile(r"^[0-9a-f]{40}$")
PERMISSION_SCOPES = {
    "actions",
    "attestations",
    "checks",
    "contents",
    "deployments",
    "discussions",
    "id-token",
    "issues",
    "models",
    "packages",
    "pages",
    "pull-requests",
    "security-events",
    "statuses",
}
APP_SECRET_BINDINGS = {
    "DATABASE_URL_FILE": "/run/secrets/breero_database_url",
    "REDIS_URL_FILE": "/run/secrets/breero_redis_url",
    "JWT_SECRET_FILE": "/run/secrets/breero_jwt_access_secret",
    "JWT_REFRESH_SECRET_FILE": "/run/secrets/breero_jwt_refresh_secret",
}


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Unable to read Compose JSON {path}: {exc}") from exc
    require(isinstance(document, dict), f"Compose JSON must be an object: {path}")
    return document


def names(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(name) for name in value}
    if isinstance(value, list):
        return {str(item) for item in value if isinstance(item, str)}
    return set()


def _secret_target(source: str, target: Any = None) -> str:
    configured = source if target in {None, ""} else str(target)
    return configured if configured.startswith("/") else f"/run/secrets/{configured}"


def secret_mounts(value: Any) -> dict[str, str]:
    """Return rendered secret source -> effective in-container target path."""

    mounts: dict[str, str] = {}

    def add(source: Any, target: Any = None) -> None:
        require(isinstance(source, str) and bool(source), "Secret source must be a non-empty string")
        require(source not in mounts, f"Duplicate secret mount source: {source}")
        mounts[source] = _secret_target(source, target)

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                add(item.get("source"), item.get("target"))
            else:
                raise ValidationError("Secret mounts must use short or long Compose syntax")
    elif isinstance(value, dict):
        for source, definition in value.items():
            if definition is None:
                add(source)
            elif isinstance(definition, str):
                add(source, definition)
            elif isinstance(definition, dict):
                add(definition.get("source", source), definition.get("target"))
            else:
                raise ValidationError("Secret mount mapping contains an unsupported value")
    elif value is not None:
        raise ValidationError("Service secrets must be a list or mapping")
    return mounts


def environment_map(value: Any) -> dict[str, str | None]:
    if isinstance(value, dict):
        return {str(key): None if item is None else str(item) for key, item in value.items()}
    environment: dict[str, str | None] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                continue
            key, separator, configured = item.partition("=")
            environment[key] = configured if separator else None
    return environment


def assert_digest(image: Any, service: str) -> None:
    require(
        isinstance(image, str) and DIGEST_IMAGE.fullmatch(image) is not None,
        f"{service} must use an immutable image digest",
    )


def assert_no_dangerous_runtime(service_name: str, service: dict[str, Any]) -> None:
    require(not service.get("ports"), f"{service_name} must not publish host ports")
    require(service.get("privileged") is not True, f"{service_name} must not be privileged")
    require(service.get("network_mode") != "host", f"{service_name} must not use host networking")
    require(service.get("pid") != "host", f"{service_name} must not use host PID namespace")
    require(service.get("ipc") != "host", f"{service_name} must not use host IPC namespace")
    require(not service.get("devices"), f"{service_name} must not map host devices")
    for mount in service.get("volumes", []) or []:
        text = json.dumps(mount, sort_keys=True)
        require("/var/run/docker.sock" not in text, f"{service_name} must not mount Docker socket")


def assert_hardened_application(service_name: str, service: dict[str, Any]) -> None:
    require(service.get("read_only") is True, f"{service_name} must have a read-only root filesystem")
    require(service.get("init") is True, f"{service_name} must enable init")
    require("ALL" in set(service.get("cap_drop", []) or []), f"{service_name} must drop all capabilities")
    require(
        "no-new-privileges:true" in set(service.get("security_opt", []) or []),
        f"{service_name} must set no-new-privileges",
    )
    require(int(service.get("pids_limit", 0)) > 0, f"{service_name} must define a PID limit")
    require(service.get("mem_limit") is not None, f"{service_name} must define a memory limit")
    assert_digest(service.get("image"), service_name)


def require_secret_target(
    service_name: str,
    mounts: dict[str, str],
    source: str,
    expected_path: str,
) -> None:
    require(source in mounts, f"{service_name} must mount secret {source}")
    require(
        mounts[source] == expected_path,
        f"{service_name} must mount {source} at {expected_path}",
    )


def validate_backend(document: dict[str, Any]) -> list[str]:
    services = document.get("services") or {}
    require(isinstance(services, dict), "Backend Compose must define services")
    required = {"migrate", "api", "worker", "scheduler", "postgres", "redis"}
    require(set(services) <= required, "Backend Compose contains unapproved services")
    missing = sorted(required - set(services))
    require(not missing, f"Backend Compose is missing services: {', '.join(missing)}")

    for name, raw in services.items():
        require(isinstance(raw, dict), f"Backend service {name} must be an object")
        assert_no_dangerous_runtime(name, raw)

    for name in ("migrate", "api", "worker", "scheduler"):
        service = services[name]
        assert_hardened_application(name, service)
        mounts = secret_mounts(service.get("secrets"))
        environment = environment_map(service.get("environment"))
        for variable, expected_path in APP_SECRET_BINDINGS.items():
            source = expected_path.rsplit("/", 1)[-1]
            require_secret_target(name, mounts, source, expected_path)
            require(
                environment.get(variable) == expected_path,
                f"{name} must bind {variable} to {expected_path}",
            )

    require(bool(services["api"].get("healthcheck")), "api must define a healthcheck")
    require(
        {"breero_private", "caddy_shared"} <= names(services["api"].get("networks")),
        "api must join the private application plane and approved Caddy edge",
    )
    for name in ("worker", "scheduler", "migrate", "postgres", "redis"):
        require(
            "breero_private" in names(services[name].get("networks")),
            f"{name} must join the private network",
        )

    for name in ("postgres", "redis"):
        assert_digest(services[name].get("image"), name)
        require(services[name].get("read_only") is True, f"{name} must be read-only outside declared data paths")
        require("ALL" in set(services[name].get("cap_drop", []) or []), f"{name} must drop all capabilities")
        require(
            "no-new-privileges:true" in set(services[name].get("security_opt", []) or []),
            f"{name} must set no-new-privileges",
        )
        require(bool(services[name].get("healthcheck")), f"{name} must define a healthcheck")

    postgres_environment = environment_map(services["postgres"].get("environment"))
    require(
        postgres_environment.get("POSTGRES_PASSWORD_FILE") == "/run/secrets/breero_postgres_password",
        "postgres must consume its file-backed password through POSTGRES_PASSWORD_FILE",
    )
    require_secret_target(
        "postgres",
        secret_mounts(services["postgres"].get("secrets")),
        "breero_postgres_password",
        "/run/secrets/breero_postgres_password",
    )

    redis_command = json.dumps(services["redis"].get("command", []), sort_keys=True)
    require(
        "/run/secrets/breero_redis_acl" in redis_command,
        "redis must consume the mounted ACL file",
    )
    require_secret_target(
        "redis",
        secret_mounts(services["redis"].get("secrets")),
        "breero_redis_acl",
        "/run/secrets/breero_redis_acl",
    )

    networks = document.get("networks") or {}
    require(isinstance(networks, dict), "Backend Compose networks must be an object")
    require(
        isinstance(networks.get("breero_private"), dict)
        and networks["breero_private"].get("internal") is True,
        "breero_private must be internal",
    )
    require(
        isinstance(networks.get("caddy_shared"), dict)
        and networks["caddy_shared"].get("external") is True,
        "caddy_shared must be externally provisioned",
    )

    secrets = document.get("secrets") or {}
    require(isinstance(secrets, dict) and bool(secrets), "Backend Compose must use file-backed secrets")
    for name, definition in secrets.items():
        require(
            isinstance(definition, dict) and bool(definition.get("file")),
            f"Secret {name} must be file-backed",
        )

    warnings: list[str] = []
    if not services["worker"].get("healthcheck"):
        warnings.append("WORKER_HEALTHCHECK=UNVERIFIED")
    if not services["scheduler"].get("healthcheck"):
        warnings.append("SCHEDULER_HEALTHCHECK=UNVERIFIED")
    return warnings


def validate_frontend(document: dict[str, Any]) -> None:
    services = document.get("services") or {}
    require(isinstance(services, dict), "Frontend Compose services must be an object")
    require(set(services) == {"web"}, "Frontend Compose must contain only the web service")
    web = services["web"]
    require(isinstance(web, dict), "Frontend web service must be an object")
    assert_no_dangerous_runtime("web", web)
    assert_hardened_application("web", web)
    require(
        str(web.get("user", "")).split(":", 1)[0] not in {"", "0", "root"},
        "web must declare a non-root runtime user",
    )
    require(bool(web.get("healthcheck")), "web must define a healthcheck")
    require("frontend" in names(web.get("networks")), "web must join the frontend edge network")
    networks = document.get("networks") or {}
    require(
        isinstance(networks, dict)
        and isinstance(networks.get("frontend"), dict)
        and networks["frontend"].get("external") is True,
        "frontend network must be externally provisioned",
    )


def load_workflow(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - execution-environment guard
        raise ValidationError("PyYAML is required for fail-closed workflow validation") from exc

    class UniqueBaseLoader(yaml.BaseLoader):
        pass

    def construct_unique_mapping(loader: Any, node: Any, deep: bool = False) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            require(isinstance(key, str), "Workflow mapping keys must be strings")
            require(key not in mapping, f"Duplicate workflow mapping key: {key}")
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    UniqueBaseLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_unique_mapping,
    )
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueBaseLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(f"Unable to parse workflow YAML {path}: {exc}") from exc
    require(isinstance(document, dict), "Deployment workflow must be a YAML mapping")
    return document


def validate_permission_mapping(value: Any, label: str, *, require_contents: bool) -> None:
    require(isinstance(value, dict), f"{label} permissions must use a mapping")
    if require_contents:
        require(value.get("contents") == "read", "Top-level contents permission must be read")
    for raw_scope, raw_access in value.items():
        scope = str(raw_scope)
        access = str(raw_access)
        require(scope in PERMISSION_SCOPES, f"Unknown workflow permission scope: {scope}")
        require(access in {"read", "none"}, f"{label} permission {scope} must be read or none")
        require(not (scope == "id-token" and access != "none"), "id-token must remain none")


def validate_permissions(document: dict[str, Any]) -> None:
    require("permissions" in document, "Workflow must declare top-level permissions")
    validate_permission_mapping(document["permissions"], "Top-level", require_contents=True)
    jobs = document.get("jobs")
    require(isinstance(jobs, dict) and bool(jobs), "Workflow must declare jobs")
    for job_name, raw_job in jobs.items():
        require(isinstance(raw_job, dict), f"Workflow job {job_name} must be a mapping")
        if "permissions" in raw_job:
            validate_permission_mapping(
                raw_job["permissions"],
                f"Job {job_name}",
                require_contents=False,
            )


def validate_action_reference(reference: Any, label: str) -> str:
    require(isinstance(reference, str) and bool(reference), f"{label} uses must be a string")
    if reference.startswith("./"):
        return reference
    action, separator, revision = reference.rpartition("@")
    require(bool(action) and separator == "@", f"Action reference is invalid: {reference}")
    require(
        PINNED_ACTION.fullmatch(revision) is not None,
        f"Action must be pinned to a 40-character commit: {reference}",
    )
    return reference


def validate_actions(document: dict[str, Any]) -> None:
    jobs = document.get("jobs")
    require(isinstance(jobs, dict), "Workflow jobs must be a mapping")
    references: list[str] = []
    checkout_count = 0
    for job_name, raw_job in jobs.items():
        require(isinstance(raw_job, dict), f"Workflow job {job_name} must be a mapping")
        if "uses" in raw_job:
            references.append(validate_action_reference(raw_job["uses"], f"job {job_name}"))
        steps = raw_job.get("steps", [])
        require(isinstance(steps, list), f"Workflow job {job_name} steps must be a list")
        for index, raw_step in enumerate(steps):
            require(isinstance(raw_step, dict), f"Workflow job {job_name} step {index} must be a mapping")
            if "uses" not in raw_step:
                continue
            reference = validate_action_reference(raw_step["uses"], f"job {job_name} step {index}")
            references.append(reference)
            if reference.startswith("actions/checkout@"):
                checkout_count += 1
                configured = raw_step.get("with")
                require(isinstance(configured, dict), "Checkout must declare an explicit with mapping")
                require(
                    str(configured.get("persist-credentials", "")).lower() == "false",
                    "Checkout credentials must not persist",
                )
    require(bool(references), "Deployment preflight must declare reviewed actions explicitly")
    require(checkout_count > 0, "Deployment preflight must use a pinned non-persistent checkout")


def validate_workflow(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    document = load_workflow(path)

    triggers = document.get("on")
    if isinstance(triggers, dict):
        require("pull_request_target" not in triggers, "Deployment preflight must not use pull_request_target")
    elif isinstance(triggers, list):
        require("pull_request_target" not in triggers, "Deployment preflight must not use pull_request_target")
    elif isinstance(triggers, str):
        require(triggers != "pull_request_target", "Deployment preflight must not use pull_request_target")

    validate_permissions(document)
    validate_actions(document)

    forbidden = (
        "secrets.",
        "environment: production",
        "docker " + "login",
        "docker " + "push",
        "docker compose " + "up",
        "docker compose " + "down",
        "caddy " + "reload",
        "systemctl " + "restart",
        "systemctl " + "reload",
        "appleboy/" + "ssh-action",
    )
    for token in forbidden:
        require(token not in text, f"Deployment preflight contains forbidden live-action token: {token}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-json", type=Path, required=True)
    parser.add_argument("--frontend-json", type=Path, required=True)
    parser.add_argument("--workflow", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    warnings = validate_backend(load_json(args.backend_json))
    validate_frontend(load_json(args.frontend_json))
    validate_workflow(args.workflow)
    print("DEPLOYMENT_COMPOSE_SECURITY=PASS")
    print("DEPLOYMENT_WORKFLOW_MUTATION_AUTHORITY=NONE")
    print("LIVE_SERVER_CHANGED=NO")
    for warning in warnings:
        print(warning)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"DEPLOYMENT_PREFLIGHT_ERROR={exc}")
        raise SystemExit(2) from exc
