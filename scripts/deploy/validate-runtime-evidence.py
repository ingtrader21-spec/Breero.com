#!/usr/bin/env python3
"""Validate rendered Compose and adapted Caddy evidence without mutating a host."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections.abc import Mapping
from typing import Any

APP_SECRET_BINDINGS = {
    "DATABASE_URL_FILE": "/run/secrets/breero_database_url",
    "REDIS_URL_FILE": "/run/secrets/breero_redis_url",
    "JWT_SECRET_FILE": "/run/secrets/breero_jwt_access_secret",
    "JWT_REFRESH_SECRET_FILE": "/run/secrets/breero_jwt_refresh_secret",
}


class EvidenceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def parse_json_document(raw: bytes, label: str) -> dict[str, Any]:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    require(isinstance(document, dict), f"{label} must be a JSON object")
    return document


def read_documents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    parts = sys.stdin.buffer.read().split(b"\0")
    require(len(parts) == 3, "expected backend, frontend and Caddy JSON separated by NUL bytes")
    return (
        parse_json_document(parts[0], "backend Compose"),
        parse_json_document(parts[1], "frontend Compose"),
        parse_json_document(parts[2], "adapted Caddy configuration"),
    )


def mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def service_networks(service: Mapping[str, Any]) -> set[str]:
    configured = service.get("networks")
    if isinstance(configured, dict):
        return {str(name) for name in configured}
    if isinstance(configured, list):
        return {str(name) for name in configured if isinstance(name, str)}
    return set()


def actual_network_name(document: Mapping[str, Any], logical_name: str) -> str:
    networks = mapping(document.get("networks") or {}, "Compose networks")
    definition = mapping(networks.get(logical_name), f"network {logical_name}")
    name = definition.get("name")
    require(isinstance(name, str) and bool(name), f"network {logical_name} has no rendered runtime name")
    return name


def secret_mounts(
    service_name: str,
    service: Mapping[str, Any],
    secret_definitions: Mapping[str, Any],
) -> dict[str, str]:
    """Bind each verified Compose source to its unique in-container target."""

    configured = service.get("secrets") or []
    require(isinstance(configured, list), f"{service_name} requires rendered secret mounts")
    mounts: dict[str, str] = {}
    targets: set[str] = set()
    for mount in configured:
        require(isinstance(mount, (str, dict)), f"{service_name} secret mount is malformed")
        source = mount if isinstance(mount, str) else mount.get("source")
        target = source if isinstance(mount, str) else mount.get("target", source)
        require(
            isinstance(source, str) and source in secret_definitions,
            f"{service_name} uses an unverified secret",
        )
        require(isinstance(target, str) and bool(target), f"{service_name} secret target is malformed")
        target = target if target.startswith("/") else "/run/secrets/" + target
        require(source not in mounts, f"{service_name} duplicates secret source {source}")
        require(target not in targets, f"{service_name} duplicates secret target {target}")
        mounts[source] = target
        targets.add(target)
    return mounts


def validate_compose_bindings(
    backend: Mapping[str, Any],
    frontend: Mapping[str, Any],
    args: argparse.Namespace,
) -> list[str]:
    backend_services = mapping(backend.get("services") or {}, "backend services")
    frontend_services = mapping(frontend.get("services") or {}, "frontend services")

    for name in ("migrate", "api", "worker", "scheduler", "postgres", "redis"):
        require(name in backend_services, f"backend service is missing: {name}")
    require(set(backend_services) == {"migrate", "api", "worker", "scheduler", "postgres", "redis"}, "unapproved backend services")
    require(set(frontend_services) == {"web"}, "frontend must contain only web")

    api = mapping(backend_services["api"], "backend api service")
    web = mapping(frontend_services["web"], "frontend web service")
    for name in ("api", "worker", "scheduler", "migrate"):
        require(backend_services[name].get("image") == args.expected_api_image, f"rendered {name} image does not match the approved digest")
    for name in ("postgres", "redis"):
        image = backend_services[name].get("image")
        require(
            isinstance(image, str) and re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image) is not None,
            f"rendered {name} image must use an immutable digest",
        )
    require(web.get("image") == args.expected_frontend_image, "rendered frontend image does not match the approved digest")

    require(
        actual_network_name(backend, "breero_private") == args.expected_private_network,
        "rendered private network name does not match the approved runtime network",
    )
    require(
        actual_network_name(backend, "caddy_shared") == args.expected_backend_edge_network,
        "rendered backend edge network name does not match the approved runtime network",
    )
    require(
        actual_network_name(frontend, "frontend") == args.expected_frontend_edge_network,
        "rendered frontend edge network name does not match the approved runtime network",
    )

    require(
        {"breero_private", "caddy_shared"} <= service_networks(api),
        "API is not attached to both rendered private and backend edge networks",
    )
    for name in ("migrate", "worker", "scheduler", "postgres", "redis"):
        service = mapping(backend_services[name], f"backend {name} service")
        require(
            "breero_private" in service_networks(service),
            f"{name} is not attached to the rendered private network",
        )
    require("frontend" in service_networks(web), "frontend web is not attached to its rendered edge network")

    secret_definitions = mapping(backend.get("secrets") or {}, "backend secrets")
    require(bool(secret_definitions), "rendered backend Compose contains no file-backed secrets")
    verified_paths: list[str] = []
    for logical_name, raw_definition in secret_definitions.items():
        definition = mapping(raw_definition, f"secret {logical_name}")
        path = definition.get("file")
        require(isinstance(path, str) and path.startswith("/"), f"secret {logical_name} path is not absolute")
        require("\n" not in path and "\r" not in path and "\0" not in path, f"secret {logical_name} path is malformed")
        resolved = os.path.realpath(path)
        require(os.path.isfile(resolved), f"secret {logical_name} is not a regular file")
        require(os.access(resolved, os.R_OK), f"secret {logical_name} is not readable")
        mode = stat.S_IMODE(os.stat(resolved).st_mode)
        require(mode & 0o007 == 0, f"secret {logical_name} is world-accessible")
        verified_paths.append(resolved)

    for name in ("api", "worker", "scheduler", "migrate", "postgres", "redis"):
        service = backend_services[name]
        mounts = secret_mounts(name, service, secret_definitions)
        if name == "redis":
            expected_path = "/run/secrets/breero_redis_acl"
            require(
                mounts.get("breero_redis_acl") == expected_path,
                f"redis must mount breero_redis_acl at {expected_path}",
            )
            command = service.get("command") or []
            require(
                isinstance(command, list)
                and command.count("--aclfile") == 1
                and any(
                    option == "--aclfile" and value == expected_path
                    for option, value in zip(command, command[1:])
                ),
                "redis must consume its verified ACL secret through --aclfile",
            )
            continue

        bindings = (
            {"POSTGRES_PASSWORD_FILE": "/run/secrets/breero_postgres_password"}
            if name == "postgres" else APP_SECRET_BINDINGS
        )
        env = service.get("environment") or {}
        require(isinstance(env, dict), f"{name} environment must be rendered")
        for variable, expected_path in bindings.items():
            source = expected_path.rsplit("/", 1)[-1]
            require(
                mounts.get(source) == expected_path,
                f"{name} must mount {source} at {expected_path}",
            )
            require(
                env.get(variable) == expected_path,
                f"{name} must bind {variable} to {expected_path}",
            )
    return sorted(set(verified_paths))


def route_allows_host(route: Mapping[str, Any], host: str) -> bool:
    """Return whether at least one route matcher alternative can match host."""

    matchers = route.get("match")
    if matchers is None or matchers == []:
        return True
    require(isinstance(matchers, list), "Caddy route match must be a list")
    for matcher in matchers:
        require(isinstance(matcher, dict), "Caddy route matcher must be an object")
        require("not" not in matcher, "Negated Caddy matchers require explicit routing review")
        configured_hosts = matcher.get("host")
        if configured_hosts is None:
            return True
        require(isinstance(configured_hosts, list), "Caddy host matcher must be a list")
        if host in {item for item in configured_hosts if isinstance(item, str)}:
            return True
    return False


def upstreams_for_host(value: Any, host: str) -> set[str]:
    """Collect only proxies reachable through compatible nested host predicates."""

    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(upstreams_for_host(item, host))
        return result

    if not isinstance(value, dict):
        return set()

    if value.get("handler") == "reverse_proxy":
        configured = value.get("upstreams")
        require(isinstance(configured, list), "Caddy reverse_proxy upstreams must be a list")
        return {
            upstream["dial"]
            for upstream in configured
            if isinstance(upstream, dict) and isinstance(upstream.get("dial"), str)
        }

    if "handle" in value:
        if not route_allows_host(value, host):
            return set()
        return upstreams_for_host(value.get("handle"), host)

    result: set[str] = set()
    for child in value.values():
        result.update(upstreams_for_host(child, host))
    return result


def validate_caddy_routes(caddy: Mapping[str, Any], args: argparse.Namespace) -> None:
    web_upstreams = upstreams_for_host(caddy, args.expected_web_host)
    api_upstreams = upstreams_for_host(caddy, args.expected_api_host)
    require(
        args.expected_web_upstream in web_upstreams,
        "adapted Caddy routes do not bind the approved web host to the approved web upstream",
    )
    require(
        args.expected_api_upstream in api_upstreams,
        "adapted Caddy routes do not bind the approved API host to the approved API upstream",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-api-image", required=True)
    parser.add_argument("--expected-frontend-image", required=True)
    parser.add_argument("--expected-private-network", required=True)
    parser.add_argument("--expected-backend-edge-network", required=True)
    parser.add_argument("--expected-frontend-edge-network", required=True)
    parser.add_argument("--expected-web-host", required=True)
    parser.add_argument("--expected-api-host", required=True)
    parser.add_argument("--expected-web-upstream", required=True)
    parser.add_argument("--expected-api-upstream", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backend, frontend, caddy = read_documents()
    secret_paths = validate_compose_bindings(backend, frontend, args)
    validate_caddy_routes(caddy, args)
    print("COMPOSE_RUNTIME_BINDING=PASS")
    print("CADDY_HOST_UPSTREAM_BINDING=PASS")
    print(f"FILE_BACKED_SECRET_PATHS_VERIFIED={len(secret_paths)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(f"RUNTIME_EVIDENCE_ERROR={exc}", file=sys.stderr)
        raise SystemExit(2) from exc
