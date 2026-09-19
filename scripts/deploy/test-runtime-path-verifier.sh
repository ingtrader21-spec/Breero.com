#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
verifier="$root/scripts/deploy/verify-runtime-paths.sh"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT

write_config() {
  local destination="$1"
  cat >"$destination" <<EOF
VERIFICATION_STATE=UNVERIFIED
LIVE_MUTATION_ALLOWED=false
EXPECTED_HOSTNAME=UNVERIFIED
EXPECTED_REPOSITORY_SHA=UNVERIFIED
REPOSITORY_ROOT=$fixture/repository
BACKEND_COMPOSE_PATH=$fixture/repository/docker-compose.production.yml
FRONTEND_COMPOSE_PATH=$fixture/repository/deploy/frontend/docker-compose.frontend.yml
LEGACY_BACKEND_COMPOSE_PATH=$fixture/repository/deploy/production/docker-compose.backend.yml
CADDY_CONFIG_PATH=$fixture/etc/caddy/Caddyfile
BACKEND_ENV_PATH=$fixture/etc/breero/backend.env
FRONTEND_ENV_PATH=$fixture/etc/breero/frontend.env
EXPECTED_BACKEND_COMPOSE_SHA256=UNVERIFIED
EXPECTED_FRONTEND_COMPOSE_SHA256=UNVERIFIED
EXPECTED_CADDY_CONFIG_SHA256=UNVERIFIED
EXPECTED_API_IMAGE=UNVERIFIED
EXPECTED_FRONTEND_IMAGE=UNVERIFIED
EXPECTED_PRIVATE_NETWORK=UNVERIFIED
EXPECTED_BACKEND_EDGE_NETWORK=UNVERIFIED
EXPECTED_FRONTEND_EDGE_NETWORK=UNVERIFIED
EXPECTED_WEB_HOST=UNVERIFIED
EXPECTED_API_HOST=UNVERIFIED
EXPECTED_WEB_UPSTREAM=UNVERIFIED
EXPECTED_API_UPSTREAM=UNVERIFIED
EOF
}

expect_failure() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "scenario unexpectedly passed: $name" >&2
    exit 1
  fi
}

valid="$fixture/valid.env"
write_config "$valid"
output="$($verifier --config "$valid" --mode syntax)"
grep -Fxq 'RUNTIME_PATH_CONFIGURATION=VALID' <<<"$output"
grep -Fxq 'LIVE_MUTATION_ALLOWED=false' <<<"$output"
grep -Fxq 'RUNTIME_PATHS_VERIFIED=NO' <<<"$output"
grep -Fxq 'LIVE_SERVER_CHANGED=NO' <<<"$output"

relative="$fixture/relative.env"
write_config "$relative"
sed -i 's#^REPOSITORY_ROOT=.*#REPOSITORY_ROOT=relative/path#' "$relative"
expect_failure relative-path "$verifier" --config "$relative" --mode syntax

unknown="$fixture/unknown.env"
write_config "$unknown"
printf 'UNEXPECTED_SECRET_PATH=/tmp/not-allowed\n' >>"$unknown"
expect_failure unknown-key "$verifier" --config "$unknown" --mode syntax

mutation="$fixture/mutation.env"
write_config "$mutation"
sed -i 's/^LIVE_MUTATION_ALLOWED=false$/LIVE_MUTATION_ALLOWED=true/' "$mutation"
expect_failure mutation-enabled "$verifier" --config "$mutation" --mode syntax

invalid_sha="$fixture/invalid-sha.env"
write_config "$invalid_sha"
sed -i 's/^EXPECTED_REPOSITORY_SHA=UNVERIFIED$/EXPECTED_REPOSITORY_SHA=main/' "$invalid_sha"
expect_failure invalid-repository-sha "$verifier" --config "$invalid_sha" --mode syntax

mutable_image="$fixture/mutable-image.env"
write_config "$mutable_image"
sed -i 's#^EXPECTED_API_IMAGE=UNVERIFIED$#EXPECTED_API_IMAGE=ghcr.io/example/breero-api:latest#' "$mutable_image"
expect_failure mutable-image "$verifier" --config "$mutable_image" --mode syntax

option_like="$fixture/option-like.env"
write_config "$option_like"
sed -i 's/^EXPECTED_WEB_HOST=UNVERIFIED$/EXPECTED_WEB_HOST=--help/' "$option_like"
expect_failure option-like-evidence "$verifier" --config "$option_like" --mode syntax

unready="$fixture/unready.env"
write_config "$unready"
expect_failure unready-host-verification "$verifier" --config "$unready" --mode host-read-only

stdin_output="$($verifier --config - --mode syntax <"$valid")"
grep -Fxq 'RUNTIME_PATH_CONFIGURATION=VALID' <<<"$stdin_output"

forbidden_tokens=(
  "docker compose u""p"
  "docker compose d""own"
  "docker compose p""ull"
  "docker compose r""un"
  "docker compose e""xec"
  "caddy v""alidate"
  "caddy r""eload"
  "systemctl r""estart"
  "systemctl r""eload"
  "alembic u""pgrade"
  "ssh "
  "scp "
  "rsync "
)
for token in "${forbidden_tokens[@]}"; do
  if grep -Fq "$token" "$verifier"; then
    echo "read-only verifier contains forbidden mutation token: $token" >&2
    exit 1
  fi
done

if grep -Eq '(^|[;&|[:space:]])(rm|mv|cp|touch|mkdir|chmod|chown)([;&|[:space:]]|$)' "$verifier"; then
  echo 'read-only verifier contains a filesystem mutation command' >&2
  exit 1
fi

mock_root="$fixture/mock-host"
repo="$mock_root/repository"
mock_bin="$mock_root/bin"
secret_dir="$mock_root/secrets"
mkdir -p \
  "$repo/deploy/frontend" \
  "$repo/deploy/production" \
  "$repo/scripts/deploy" \
  "$mock_root/etc/caddy" \
  "$mock_root/etc/breero" \
  "$mock_bin" \
  "$secret_dir"

printf 'backend-compose\n' >"$repo/docker-compose.production.yml"
printf 'frontend-compose\n' >"$repo/deploy/frontend/docker-compose.frontend.yml"
printf 'legacy-compose\n' >"$repo/deploy/production/docker-compose.backend.yml"
cp "$root/scripts/deploy/verify-runtime-paths.sh" "$repo/scripts/deploy/verify-runtime-paths.sh"
cp "$root/scripts/deploy/validate-runtime-evidence.py" "$repo/scripts/deploy/validate-runtime-evidence.py"
chmod +x "$repo/scripts/deploy/verify-runtime-paths.sh" "$repo/scripts/deploy/validate-runtime-evidence.py"
printf 'breero.com { reverse_proxy web:3000 }\napi.breero.com { reverse_proxy api:8000 }\n' \
  >"$mock_root/etc/caddy/Caddyfile"
printf 'APP_ENV=production\nPOSTGRES_PASSWORD_FILE=/run/secrets/breero_postgres_password\n' \
  >"$mock_root/etc/breero/backend.env"
printf 'NEXT_PUBLIC_API_BASE_URL=https://api.breero.com\n' >"$mock_root/etc/breero/frontend.env"
chmod 600 "$mock_root/etc/breero/backend.env" "$mock_root/etc/breero/frontend.env"

secret_names=(
  breero_database_url breero_redis_url breero_jwt_access_secret
  breero_jwt_refresh_secret breero_postgres_password breero_redis_acl
)
for secret_name in "${secret_names[@]}"; do
  printf 'placeholder\n' >"$secret_dir/$secret_name"
  chmod 600 "$secret_dir/$secret_name"
done

backend_json="$mock_root/backend.json"
frontend_json="$mock_root/frontend.json"
caddy_json="$mock_root/caddy.json"
python3 - "$backend_json" "$frontend_json" "$caddy_json" "$secret_dir" <<'PY'
import json
import sys
from pathlib import Path

backend_path, frontend_path, caddy_path, secret_dir = map(Path, sys.argv[1:])
api_image = "ghcr.io/example/breero-api@sha256:" + "1" * 64
web_image = "ghcr.io/example/breero-web@sha256:" + "2" * 64
services = {
    name: {"image": api_image, "networks": {"breero_private": None}}
    for name in ("migrate", "worker", "scheduler", "postgres", "redis")
}
services["api"] = {
    "image": api_image,
    "networks": {"breero_private": None, "caddy_shared": None},
}
for name in ("api", "worker", "scheduler", "migrate"):
    bindings = {"DATABASE_URL_FILE": "breero_database_url", "REDIS_URL_FILE": "breero_redis_url", "JWT_SECRET_FILE": "breero_jwt_access_secret", "JWT_REFRESH_SECRET_FILE": "breero_jwt_refresh_secret"}
    services[name]["environment"] = {key: "/run/secrets/" + value for key, value in bindings.items()}
    services[name]["secrets"] = [{"source": value, "target": value} for value in bindings.values()]
services["postgres"]["environment"] = {
    "POSTGRES_PASSWORD_FILE": "/run/secrets/breero_postgres_password",
}
services["postgres"]["secrets"] = ["breero_postgres_password"]
services["redis"]["command"] = ["redis-server", "--aclfile", "/run/secrets/breero_redis_acl"]
services["redis"]["secrets"] = ["breero_redis_acl"]
backend = {
    "services": services,
    "networks": {
        "breero_private": {"name": "breero_private_runtime", "internal": True},
        "caddy_shared": {"name": "breero_edge_runtime", "external": True},
    },
    "secrets": {
        name: {"file": str(secret_dir / name)}
        for name in (
            "breero_database_url",
            "breero_redis_url",
            "breero_jwt_access_secret",
            "breero_jwt_refresh_secret",
            "breero_postgres_password",
            "breero_redis_acl",
        )
    },
}
frontend = {
    "services": {"web": {"image": web_image, "networks": {"frontend": None}}},
    "networks": {"frontend": {"name": "breero_frontend_runtime", "external": True}},
}
caddy = {
    "apps": {
        "http": {
            "servers": {
                "srv0": {
                    "routes": [
                        {
                            "match": [{"host": ["breero.com"]}],
                            "handle": [
                                {
                                    "handler": "reverse_proxy",
                                    "upstreams": [{"dial": "web:3000"}],
                                }
                            ],
                        },
                        {
                            "match": [{"host": ["api.breero.com"]}],
                            "handle": [
                                {
                                    "handler": "reverse_proxy",
                                    "upstreams": [{"dial": "api:8000"}],
                                }
                            ],
                        },
                    ]
                }
            }
        }
    }
}
backend_path.write_text(json.dumps(backend), encoding="utf-8")
frontend_path.write_text(json.dumps(frontend), encoding="utf-8")
caddy_path.write_text(json.dumps(caddy), encoding="utf-8")
PY

git -C "$repo" init -q
git -C "$repo" config user.name runtime-verifier-test
git -C "$repo" config user.email runtime-verifier-test@example.invalid
git -C "$repo" add .
git -C "$repo" commit -qm fixture
repo_sha="$(git -C "$repo" rev-parse HEAD)"
host_verifier="$repo/scripts/deploy/verify-runtime-paths.sh"

cat >"$mock_bin/hostname" <<'EOF'
#!/usr/bin/env bash
printf 'breero-test-host\n'
EOF
cat >"$mock_bin/docker" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == compose ]]; then
  for argument in "$@"; do
    case "$argument" in
      */docker-compose.frontend.yml|docker-compose.frontend.yml)
        cat "$MOCK_FRONTEND_JSON"
        exit 0
        ;;
    esac
  done
  cat "$MOCK_BACKEND_JSON"
  exit 0
fi
if [[ ${1:-} == network && ${2:-} == inspect ]]; then
  if [[ " $* " == *" --format "* ]]; then
    printf 'true\n'
  fi
  exit 0
fi
exit 2
EOF
cat >"$mock_bin/caddy" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[[ ${1:-} == adapt ]] || exit 2
cat "$MOCK_CADDY_JSON"
EOF
cat >"$mock_bin/ss" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ ${MOCK_SS_FAIL:-0} == 1 ]]; then
  exit 9
fi
printf 'LISTEN 0 128 127.0.0.1:22 0.0.0.0:*\n'
EOF
chmod +x "$mock_bin/hostname" "$mock_bin/docker" "$mock_bin/caddy" "$mock_bin/ss"

host_config="$mock_root/host.env"
cat >"$host_config" <<EOF
VERIFICATION_STATE=READY_FOR_READ_ONLY_VERIFICATION
LIVE_MUTATION_ALLOWED=false
EXPECTED_HOSTNAME=breero-test-host
EXPECTED_REPOSITORY_SHA=$repo_sha
REPOSITORY_ROOT=$repo
BACKEND_COMPOSE_PATH=$repo/docker-compose.production.yml
FRONTEND_COMPOSE_PATH=$repo/deploy/frontend/docker-compose.frontend.yml
LEGACY_BACKEND_COMPOSE_PATH=$repo/deploy/production/docker-compose.backend.yml
CADDY_CONFIG_PATH=$mock_root/etc/caddy/Caddyfile
BACKEND_ENV_PATH=$mock_root/etc/breero/backend.env
FRONTEND_ENV_PATH=$mock_root/etc/breero/frontend.env
EXPECTED_BACKEND_COMPOSE_SHA256=$(sha256sum "$repo/docker-compose.production.yml" | awk '{print $1}')
EXPECTED_FRONTEND_COMPOSE_SHA256=$(sha256sum "$repo/deploy/frontend/docker-compose.frontend.yml" | awk '{print $1}')
EXPECTED_CADDY_CONFIG_SHA256=$(sha256sum "$mock_root/etc/caddy/Caddyfile" | awk '{print $1}')
EXPECTED_API_IMAGE=ghcr.io/example/breero-api@sha256:$(printf '1%.0s' {1..64})
EXPECTED_FRONTEND_IMAGE=ghcr.io/example/breero-web@sha256:$(printf '2%.0s' {1..64})
EXPECTED_PRIVATE_NETWORK=breero_private_runtime
EXPECTED_BACKEND_EDGE_NETWORK=breero_edge_runtime
EXPECTED_FRONTEND_EDGE_NETWORK=breero_frontend_runtime
EXPECTED_WEB_HOST=breero.com
EXPECTED_API_HOST=api.breero.com
EXPECTED_WEB_UPSTREAM=web:3000
EXPECTED_API_UPSTREAM=api:8000
EOF

run_host_verifier() {
  env \
    PATH="$mock_bin:$PATH" \
    MOCK_BACKEND_JSON="$backend_json" \
    MOCK_FRONTEND_JSON="$frontend_json" \
    MOCK_CADDY_JSON="$caddy_json" \
    "$@"
}

host_output="$(run_host_verifier "$host_verifier" --config "$host_config" --mode host-read-only)"
grep -Fxq 'COMPOSE_RUNTIME_BINDING=PASS' <<<"$host_output"
grep -Fxq 'CADDY_HOST_UPSTREAM_BINDING=PASS' <<<"$host_output"
grep -Fxq 'RUNTIME_PATHS_VERIFIED=YES' <<<"$host_output"
grep -Fxq 'LIVE_SERVER_CHANGED=NO' <<<"$host_output"

invalid_backend_json="$mock_root/backend-unmounted-password.json"
python3 - "$backend_json" "$invalid_backend_json" <<'PY'
import json
import sys
from pathlib import Path

backend = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
backend["services"]["postgres"]["environment"]["POSTGRES_PASSWORD_FILE"] = (
    "/run/secrets/unmounted_password"
)
Path(sys.argv[2]).write_text(json.dumps(backend), encoding="utf-8")
PY
if invalid_output="$(run_host_verifier env MOCK_BACKEND_JSON="$invalid_backend_json" \
  "$host_verifier" --config "$host_config" --mode host-read-only 2>&1)"; then
  echo 'unmounted PostgreSQL password consumer unexpectedly passed' >&2
  exit 1
fi
grep -Fq 'POSTGRES_PASSWORD_FILE' <<<"$invalid_output"
if grep -Fxq 'RUNTIME_PATHS_VERIFIED=YES' <<<"$invalid_output"; then
  echo 'invalid secret consumer emitted a verified runtime verdict' >&2
  exit 1
fi

expect_failure ss-enumeration-failure \
  env \
    PATH="$mock_bin:$PATH" \
    MOCK_BACKEND_JSON="$backend_json" \
    MOCK_FRONTEND_JSON="$frontend_json" \
    MOCK_CADDY_JSON="$caddy_json" \
    MOCK_SS_FAIL=1 \
    "$host_verifier" --config "$host_config" --mode host-read-only

validator_relative="scripts/deploy/validate-runtime-evidence.py"
git -C "$repo" update-index --skip-worktree "$validator_relative"
printf '\n# modified despite skip-worktree\n' >>"$repo/$validator_relative"
expect_failure skip-worktree-validator-mutation \
  run_host_verifier "$host_verifier" --config "$host_config" --mode host-read-only
git -C "$repo" update-index --no-skip-worktree "$validator_relative"
git -C "$repo" checkout -- "$validator_relative"

echo 'RUNTIME_PATH_VERIFIER_TESTS=PASS'
echo 'LIVE_SERVER_CHANGED=NO'
