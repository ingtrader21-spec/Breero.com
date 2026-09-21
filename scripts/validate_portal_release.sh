#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-production}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRODUCTION="${ROOT}/deploy/production/docker-compose.portals.yml"
STAGING="${ROOT}/deploy/staging/docker-compose.portals.override.yml"

case "${MODE}" in
  production)
    COMPOSE_FILES=(-f "${PRODUCTION}")
    ;;
  staging)
    COMPOSE_FILES=(-f "${PRODUCTION}" -f "${STAGING}")
    ;;
  *)
    echo "usage: $0 [production|staging]" >&2
    exit 64
    ;;
esac

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 69; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 69; }

CONFIG="$(mktemp)"
trap 'rm -f "${CONFIG}"' EXIT
docker compose "${COMPOSE_FILES[@]}" config --format json >"${CONFIG}"

python3 - "${MODE}" "${CONFIG}" <<'PY'
import json
import re
import sys
from urllib.parse import urlparse

mode, path = sys.argv[1:]
with open(path, encoding="utf-8") as handle:
    config = json.load(handle)

expected = {"web", "partner", "ops", "admin"}
services = config.get("services", {})
if set(services) != expected:
    raise SystemExit(f"expected exactly {sorted(expected)}, got {sorted(services)}")

digest = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")
sha = re.compile(r"^[0-9a-f]{40}$")

for name, service in services.items():
    image = service.get("image", "")
    if not digest.fullmatch(image):
        raise SystemExit(f"{name}: image is not digest pinned: {image!r}")
    if service.get("ports"):
        raise SystemExit(f"{name}: published host ports are forbidden")
    if service.get("read_only") is not True:
        raise SystemExit(f"{name}: read_only must be true")
    if str(service.get("user")) not in {"10001", "10001:10001"}:
        raise SystemExit(f"{name}: runtime user must be 10001:10001")
    if "ALL" not in set(service.get("cap_drop") or []):
        raise SystemExit(f"{name}: all Linux capabilities must be dropped")
    security = set(service.get("security_opt") or [])
    if not any(item.replace("=", ":") == "no-new-privileges:true" for item in security):
        raise SystemExit(f"{name}: no-new-privileges is required")
    if not service.get("healthcheck"):
        raise SystemExit(f"{name}: healthcheck is required")
    labels = service.get("labels") or {}
    release_sha = labels.get("com.codestra.release.sha", "")
    if not sha.fullmatch(release_sha):
        raise SystemExit(f"{name}: com.codestra.release.sha must be an exact 40-hex commit")

for name in ("partner", "ops", "admin"):
    service = services[name]
    networks = set(service.get("networks") or [])
    if not {"edge", "gateway"}.issubset(networks):
        raise SystemExit(f"{name}: both edge and gateway networks are required")
    if len(service.get("secrets") or []) != 2:
        raise SystemExit(f"{name}: exactly one Keycloak client secret and one session secret are required")
    environment = service.get("environment") or {}
    origin = environment.get("PORTAL_PUBLIC_ORIGIN", "")
    parsed_origin = urlparse(origin)
    if parsed_origin.scheme != "https" or not parsed_origin.netloc or parsed_origin.path not in {"", "/"}:
        raise SystemExit(f"{name}: PORTAL_PUBLIC_ORIGIN must be an HTTPS origin")
    if "*" in origin:
        raise SystemExit(f"{name}: wildcard origins are forbidden")
    api = environment.get("BREERO_API_INTERNAL_URL", "")
    parsed_api = urlparse(api)
    if parsed_api.scheme not in {"http", "https"} or not parsed_api.hostname:
        raise SystemExit(f"{name}: BREERO_API_INTERNAL_URL is invalid")
    if not parsed_api.path.rstrip("/").endswith("/api/v1"):
        raise SystemExit(f"{name}: BREERO_API_INTERNAL_URL must end in /api/v1")
    public_hosts = {"api.breero.com", "breero.com", "www.breero.com"}
    if parsed_api.hostname in public_hosts:
        raise SystemExit(f"{name}: BFF must use private Kong, not a public API host")

web_networks = set(services["web"].get("networks") or [])
if web_networks != {"edge"}:
    raise SystemExit("web: only the edge network is permitted")

print(f"BREERO portal {mode} composition: PASS")
PY
