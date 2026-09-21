#!/usr/bin/env bash
set -euo pipefail

backend=false
frontend=false
bootstrap=false

while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  case "$path" in
    apps/api/*|deploy/production/*|deploy/staging/*|docker-compose.production.yml|scripts/deploy/*|.github/workflows/deployment-preflight.yml|.github/workflows/backend-production.yml)
      backend=true
      ;;
  esac
  case "$path" in
    apps/web/*|apps/partner/*|apps/ops/*|apps/admin/*|apps/api/*|packages/portal/*|deploy/portals/*|deploy/frontend/*|scripts/deploy/*|packages/api-client/*|packages/types/*|packages/ui/*|scripts/check-frontend-openapi.mjs|package.json|pnpm-lock.yaml|pnpm-workspace.yaml|turbo.json|.github/workflows/deployment-preflight.yml|.github/workflows/frontend-production.yml)
      frontend=true
      ;;
  esac
  case "$path" in
    scripts/bootstrap_breero_backend.py|scripts/tests/test_bootstrap_breero_backend.py|.github/workflows/backend-bootstrap-tool.yml)
      bootstrap=true
      ;;
  esac
done

printf 'backend=%s\nfrontend=%s\nbootstrap=%s\n' "$backend" "$frontend" "$bootstrap"
