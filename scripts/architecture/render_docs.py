"""Render M00 architecture truth docs from SOURCE_INVENTORY.json.

This renderer deliberately distinguishes source evidence from runtime/deployment
certification. It does not call providers, databases, or external systems.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "docs" / "architecture"
INVENTORY = ARCH / "SOURCE_INVENTORY.json"

TARGETS = (
    "CURRENT_SYSTEM.md",
    "API_REGISTRY.md",
    "INTEGRATION_REGISTRY.md",
    "CAPABILITY_REGISTRY.md",
    "DATA_CLASSIFICATION.md",
)


def esc(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def link_source(path: str) -> str:
    return f"[{path}](../../{path})"


def inventory() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def operation_memberships(data: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for profile_name, profile in data["runtime_profiles"].items():
        for operation in profile["operations"]:
            result.setdefault(operation, []).append(profile_name)
    return result


def render_current(data: dict) -> str:
    sha = data["baseline_main_sha"]
    openapi = data["openapi_artifact"]
    profiles = data["runtime_profiles"]
    lines = [
        "# Current BREERO system",
        "",
        (f"Generated from executable source inventory at `{sha}`. "
        "This is source truth only; deployed database revision, external services, "
        "and production activation require separate runtime certification."),
        "",
        "## Canonical source record",
        "",
        "| Field | Source evidence |",
        "|---|---|",
        "| REPOSITORY | `ingtrader21-spec/Breero.com` |",
        f"| SOURCE_SHA | `{sha}` |",
        f"| ALEMBIC_HEADS | `{', '.join(data['alembic_heads'])}` |",
        f"| ALEMBIC_REVISIONS | {len(data['alembic_revisions'])} |",
        f"| OPENAPI_ARTIFACT | `{openapi['path']}` / `{openapi['sha256']}` |",
        f"| BACKEND_DOMAINS | {len(data['backend_domains'])} |",
        f"| FRONTEND_ROUTES | {len(data['frontend_routes'])} |",
        f"| WORKER_TASKS | {len(data['workers'])} |",
        f"| DEPLOYMENT_FILES | {len(data['deployment_files'])} |",
        "| LIVE_PRODUCTION_CERTIFICATION | NOT ESTABLISHED BY THIS INVENTORY |",
        "",
        ("Stale PR/issue counts are intentionally not copied into this source document. "
        "GitHub state must be verified live when a release or mission decision depends on it."),
        "",
        "## Runtime/API profiles",
        "",
        "| Profile | OpenAPI paths | OpenAPI operations | Checked artifact match | Duplicate registrations |",
        "|---|---:|---:|---|---:|",
    ]
    for name, profile in profiles.items():
        lines.append(
            f"| {name} | {profile['paths']} | {profile['openapi_operations']} | "
            f"{str(profile['openapi_matches_artifact']).upper()} | "
            f"{len(profile.get('duplicate_route_registrations', []))} |"
        )
    lines += [
        "",
        ("The `canonical_contract` profile is the checked-in OpenAPI authority. "
        "The default profile is the fail-closed route surface; implemented/dark profiles "
        "are evidence of code presence, not authorization to activate capabilities."),
        "",
        "## Route ambiguity evidence",
        "",
        (f"Profile-contract variants: **{len(data.get('profile_contract_variants', []))}**. "
        "Duplicate registrations remain explicit evidence for the API-authority mission; "
        "they are not silently collapsed into a claim of unique ownership."),
        "",
    ]
    for profile_name, profile in profiles.items():
        dups = profile.get("duplicate_route_registrations", [])
        if not dups:
            continue
        lines += [f"### {profile_name}", "", "| Method | Path | Registrations |", "|---|---|---|"]
        for dup in dups:
            regs = "; ".join(
                f"{r['source']}::{r['handler']}" for r in dup["registrations"]
            )
            lines.append(f"| {dup['method']} | `{dup['path']}` | {esc(regs)} |")
        lines.append("")
    lines += [
        "## Backend domains",
        "",
        "| Directory under apps/api/app/domains | Source state |",
        "|---|---|",
    ]
    for domain in data["backend_domains"]:
        lines.append(f"| `{domain}` | SOURCE_PRESENT |")
    lines += [
        "",
        ("Functional completeness is intentionally not inferred from directory presence. "
        "Domain acceptance remains governed by the M00–M30 mission board."),
        "",
        "## Worker tasks",
        "",
        "| Source | Function | Configuration |",
        "|---|---|---|",
    ]
    for row in data["workers"]:
        lines.append(
            f"| {link_source(row['source'])} | `{row['function']}` | "
            f"`{esc(json.dumps(row['configuration'], sort_keys=True))}` |"
        )
    lines += [
        "",
        "## Deployment definitions",
        "",
        "| Path | SHA-256 |",
        "|---|---|",
    ]
    for row in data["deployment_files"]:
        lines.append(f"| {link_source(row['path'])} | `{row['sha256']}` |")
    lines += [
        "",
        "## All frontend routes",
        "",
        ("Filesystem route presence is source evidence, not proof of authentication, "
        "accessibility, real-data completeness, or deployed reachability."),
        "",
        "| App | Kind | Route | Source |",
        "|---|---|---|---|",
    ]
    for row in data["frontend_routes"]:
        lines.append(
            f"| {row['app']} | {row['kind']} | `{row['route']}` | "
            f"{link_source(row['path'])} |"
        )
    return "\n".join(lines) + "\n"


def render_api(data: dict) -> str:
    memberships = operation_memberships(data)
    lines = [
        "# BREERO API registry",
        "",
        (f"Generated from `SOURCE_INVENTORY.json` at `{data['baseline_main_sha']}`. "
        "The canonical contract profile is authoritative for shared method/path pairs. "
        "Implemented/dark-only routes remain inventoried but are not activation evidence."),
        "",
        "## Profile summary",
        "",
        "| Profile | Paths | Operations | Artifact match |",
        "|---|---:|---:|---|",
    ]
    for name, profile in data["runtime_profiles"].items():
        lines.append(
            f"| {name} | {profile['paths']} | {profile['openapi_operations']} | "
            f"{str(profile['openapi_matches_artifact']).upper()} |"
        )
    lines += [
        "",
        "## Duplicate route registrations",
        "",
        "Duplicate method/path registrations are source-authority defects to be resolved by M02/PR #62.",
        "",
    ]
    seen = set()
    for profile in data["runtime_profiles"].values():
        for dup in profile.get("duplicate_route_registrations", []):
            key = (dup["method"], dup["path"])
            if key in seen:
                continue
            seen.add(key)
            regs = "; ".join(
                f"{r['source']}::{r['handler']}" for r in dup["registrations"]
            )
            lines.append(f"- **{dup['method']} `{dup['path']}`** — {regs}")
    if not seen:
        lines.append("- None.")
    lines += [
        "",
        "## Profile contract variants",
        "",
    ]
    variants = data.get("profile_contract_variants", [])
    if not variants:
        lines.append("- None.")
    else:
        for row in variants:
            lines.append(
                f"- **{row['method']} `{row['path']}`**: "
                f"{row['authoritative_profile']} authority differs from "
                f"{row['variant_profile']}."
            )
    lines += [
        "",
        "## Operation inventory",
        "",
        "| Method | Path | Profiles | Version | Source | Handler | Operation ID | Owner | Permission | Capability |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in data["api_operations"]:
        key = f"{row['method']} {row['path']}"
        lines.append(
            f"| {row['method']} | `{row['path']}` | "
            f"{', '.join(memberships.get(key, []))} | {row['version']} | "
            f"{link_source(row['source'])} | `{row['handler']}` | "
            f"`{esc(row.get('operation_id'))}` | {row['owner']} | "
            f"{row['permission']} | {row['capability']} |"
        )
    lines += [
        "",
        ("Fields still marked `UNREGISTERED` are explicit M02 work; this document does "
        "not invent policy metadata to make the registry appear complete."),
    ]
    return "\n".join(lines) + "\n"


def render_capability(data: dict) -> str:
    lines = [
        "# Capability registry",
        "",
        (f"Generated from source defaults at `{data['baseline_main_sha']}`. "
        "Defaults describe code/configuration only; they are not production activation evidence."),
        "",
        "| Source setting | Default | Source |",
        "|---|---|---|",
    ]
    for row in sorted(data["feature_defaults"], key=lambda r: r["setting"]):
        lines.append(
            f"| `{row['setting']}` | `{esc(row['default'])}` | "
            f"{link_source(row['source'])} |"
        )
    lines += [
        "",
        "## Activation rule",
        "",
        ("Adding a route, migration, provider credential, or environment variable does not "
        "activate a protected capability. Production activation remains a separate M30 decision "
        "after staging, security, rollback and monitoring evidence."),
    ]
    return "\n".join(lines) + "\n"


def render_integration(data: dict) -> str:
    modules = [
        row
        for row in data["backend_modules"]
        if row["path"].startswith("apps/api/app/integrations/")
    ]
    lines = [
        "# Integration registry",
        "",
        (f"Generated source evidence at `{data['baseline_main_sha']}`. "
        "File presence does not certify external provider connectivity or authorize live effects."),
        "",
        "## BREERO integration source modules",
        "",
        "| Module | SHA-256 |",
        "|---|---|",
    ]
    for row in modules:
        lines.append(f"| {link_source(row['path'])} | `{row['sha256']}` |")
    lines += [
        "",
        "## Odoo projection source",
        "",
        "| Source | SHA-256 |",
        "|---|---|",
    ]
    for row in data["odoo_addon_sources"]:
        lines.append(f"| {link_source(row['path'])} | `{row['sha256']}` |")
    lines += [
        "",
        "## Authority boundary",
        "",
        "- BREERO owns marketplace transactional truth.",
        "- Keycloak owns production identity credentials.",
        "- Klyrow is email transport; Telnexa is SMS transport.",
        "- Middleware owns governed cross-platform writes; Odoo is CRM/ERP projection.",
        "- Redis is operational coordination/transport, not booking/capacity/payment authority.",
        "- External side effects must follow durable commit → outbox → worker/provider → inbox/reconciliation.",
        "",
        "Runtime/provider certification belongs to M06/M19/M25 and staging missions; it is not inferred here.",
    ]
    return "\n".join(lines) + "\n"


def render_data(data: dict) -> str:
    return f"""# Data classification and handling baseline

Regenerated for source baseline `{data['baseline_main_sha']}`. This is handling
policy and source-boundary evidence, not legal advice or production-retention certification.

| Class | Examples | Required handling |
|---|---|---|
| PUBLIC | Service catalog, approved public provider profile, published reviews | Integrity controls; publish/cache only approved fields |
| INTERNAL | Operational reason codes, non-sensitive configuration, aggregate KPIs | Authenticated workforce access; do not publish by default |
| CONFIDENTIAL | Customer/provider contact data, addresses, conversations, quotes, schedules, support cases | Tenant/record authorization, encryption, audited access, minimized telemetry |
| RESTRICTED | Credentials/tokens, tax IDs, background/license/insurance evidence, job evidence/signatures, payment/payout/fraud records | Least privilege, strong audit, secret/document isolation, no raw telemetry, explicit retention/legal hold |

## Store and flow rules

BREERO PostgreSQL/PostGIS is marketplace transactional authority. Redis is not a
system of record. OpenBao owns secrets/PKI. Klyrow/Telnexa receive only data needed
for authorized delivery. Middleware receives governed minimum event payloads and
Odoo remains a projection. Analytics must use projections/reporting stores rather
than mutation paths.

## Current implementation boundary

The source inventory records {len(data['backend_domains'])} backend domain packages,
{len(data['workers'])} worker tasks and {len(data['api_operations'])} unique logical
API operations across the inventoried profiles. Those counts do not prove complete
retention, export, deletion, legal hold, secure-document, messaging/support, or
financial certification. Those remain owned by their M00–M30 gates.

## Never log

Passwords, access/refresh/reset tokens, API keys, webhook secrets, OpenBao material,
SMTP/SMS credentials, raw payment data, full private document contents, and unrestricted
trust/safety notes must not enter logs, traces, metrics or analytics labels.

## Retention rule

Do not invent retention durations. Automated deletion/retention remains disabled
until approved product/legal policy, evidence preservation, financial/audit constraints,
and restore/reconciliation behavior are explicitly certified.
"""


def render_all(data: dict) -> dict[str, str]:
    return {
        "CURRENT_SYSTEM.md": render_current(data),
        "API_REGISTRY.md": render_api(data),
        "INTEGRATION_REGISTRY.md": render_integration(data),
        "CAPABILITY_REGISTRY.md": render_capability(data),
        "DATA_CLASSIFICATION.md": render_data(data),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = inventory()
    rendered = render_all(data)
    drift = []
    for name, content in rendered.items():
        path = ARCH / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                drift.append(name)
        else:
            path.write_text(content, encoding="utf-8")
            print(path.relative_to(ROOT))
    if drift:
        raise SystemExit("Architecture docs drift: " + ", ".join(drift))


if __name__ == "__main__":
    main()
