#!/usr/bin/env python3
"""Safely bootstrap missing BREERO backend production-foundation boundaries.

The tool is intentionally conservative:

- dry-run is the default;
- it operates only in a verified BREERO repository checkout;
- apply mode is allowed only on the expected clean feature branch;
- the other-branch override is dry-run only;
- apply mode is forbidden on protected/release branches;
- existing non-identical files are never overwritten;
- database migrations and production/runtime activation are never performed;
- generated boundaries extend ``apps/api`` instead of rebuilding it.

Typical use::

    python scripts/bootstrap_breero_backend.py
    python scripts/bootstrap_breero_backend.py --apply

The expected implementation branch is::

    bootstrap/backend-production-foundation
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

EXPECTED_BRANCH = "bootstrap/backend-production-foundation"
EXPECTED_REPOSITORY_NAME = "breero.com"
PROTECTED_BRANCHES = frozenset({"main", "master", "production", "prod"})
PROTECTED_PREFIXES = ("release/", "production/", "prod/")

BACKEND_ROOT = Path("apps/api")
APP_ROOT = BACKEND_ROOT / "app"
TEST_ROOT = BACKEND_ROOT / "tests"

# These are structural package boundaries only. Domain behavior belongs in
# independently reviewable implementation PRs.
PACKAGE_DIRS: tuple[Path, ...] = (
    APP_ROOT / "api" / "v2",
    APP_ROOT / "application",
    APP_ROOT / "core",
    APP_ROOT / "domains" / "identity",
    APP_ROOT / "domains" / "tenancy",
    APP_ROOT / "domains" / "requests",
    APP_ROOT / "domains" / "marketplace",
    APP_ROOT / "domains" / "providers",
    APP_ROOT / "domains" / "quotes",
    APP_ROOT / "domains" / "bookings",
    APP_ROOT / "domains" / "jobs",
    APP_ROOT / "domains" / "documents",
    APP_ROOT / "domains" / "geo",
    APP_ROOT / "domains" / "operations",
    APP_ROOT / "domains" / "authorization",
    APP_ROOT / "domains" / "capabilities",
    APP_ROOT / "domains" / "integrations",
    APP_ROOT / "integrations" / "codestra",
    # Keep this name distinct from the deployed integrations/odoo.py module.
    APP_ROOT / "integrations" / "odoo_extensions",
    APP_ROOT / "integrations" / "klyrow",
    APP_ROOT / "integrations" / "telnexa",
    APP_ROOT / "integrations" / "n8n",
    APP_ROOT / "workers",
)

TEST_DIRS: tuple[Path, ...] = (
    TEST_ROOT / "unit",
    TEST_ROOT / "integration",
    TEST_ROOT / "security",
    TEST_ROOT / "concurrency",
    TEST_ROOT / "postgres",
    TEST_ROOT / "postgis",
)

PACKAGE_MARKERS: tuple[Path, ...] = tuple(
    directory / "__init__.py" for directory in PACKAGE_DIRS
)

TEST_MARKERS: tuple[Path, ...] = tuple(directory / "README.md" for directory in TEST_DIRS)

README_FILES: dict[Path, str] = {
    APP_ROOT / "domains" / "README.md": """# BREERO backend domains

Domain packages own business rules, policies, state machines, commands,
repositories, queries, events, and domain errors.

Transport code must remain thin. External provider calls must not occur inside
authoritative PostgreSQL transactions. Production-sensitive mutations must
follow the shared authentication, authorization, policy, capability,
idempotency/concurrency, audit, and transactional-outbox path.
""",
    APP_ROOT / "integrations" / "README.md": """# BREERO backend integrations

Provider-specific code belongs behind provider-neutral interfaces.

Outbound work:
domain command -> transactional outbox -> worker -> adapter -> provider.

Inbound work:
verified callback -> durable inbox -> worker -> translator -> authorized
domain command.

Adapters must not become authoritative for marketplace state.
""",
    TEST_ROOT / "README.md": """# BREERO backend tests

Production-foundation work must include, where applicable:

- unit/domain tests;
- PostgreSQL integration tests;
- PostGIS tests for geographic behavior;
- negative authorization tests;
- idempotency and concurrency tests;
- outbox/inbox/webhook tests;
- migration and OpenAPI drift checks;
- security and fail-closed capability tests.

Do not substitute SQLite for PostgreSQL-specific behavior.
""",
}

BRANCH_PLAN = """BREERO backend branch plan

main
├── bootstrap/backend-production-foundation
├── auth/identity-tenancy
├── domain/request-marketplace
├── domain/provider-network
├── domain/quotes-bookings-jobs
├── integration/outbox-inbox
├── adapters/codestra-odoo-klyrow-telnexa-n8n
├── documents/secure-pipeline
├── geo/postgis-matching
├── operations/recovery
├── observability/postgres-tests
└── release/staging-recovery
"""

PACKAGE_MARKER_CONTENT = (
    '"""BREERO backend package boundary.\n\n'
    "Behavior is added only in the owning reviewed implementation PR.\n"
    '"""\n'
)

TEST_MARKER_CONTENT = """# Tracked test boundary

Tests for this boundary are added by its owning independently reviewed mission.
The tracked marker keeps the intended suite visible across clean checkouts.
"""


@dataclass(frozen=True)
class Action:
    kind: str
    path: Path
    detail: str


class BootstrapError(RuntimeError):
    """Raised when the repository or requested operation is not safe."""


def run_git(root: Path, *args: str) -> str:
    """Run one read-only Git command in *root* and return stripped stdout."""

    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BootstrapError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or 'unknown error'}"
        )
    return result.stdout.strip()


def find_repo_root(start: Path) -> Path:
    """Return the nearest parent containing a Git worktree marker."""

    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise BootstrapError("No Git repository found from the current directory.")


def repository_name_from_remote(remote: str) -> str:
    """Extract a repository name from HTTPS, SSH, or SCP-style Git remotes."""

    normalized = remote.strip().rstrip("/")
    if normalized.casefold().endswith(".git"):
        normalized = normalized[:-4]
    repository_name = normalized.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return repository_name.casefold()


def verify_breero_scope(root: Path) -> None:
    """Fail unless *root* has the expected BREERO monorepo identity."""

    required = (
        root / "apps",
        root / "apps" / "api",
        root / "README.md",
    )
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    if missing:
        raise BootstrapError(
            "This checkout does not have the expected BREERO monorepo structure: "
            + ", ".join(missing)
        )

    readme = (root / "README.md").read_text(encoding="utf-8", errors="ignore")
    if "breero" not in readme.casefold():
        raise BootstrapError(
            "Repository identity check failed: README does not identify BREERO."
        )

    remote = run_git(root, "remote", "get-url", "origin")
    repository_name = repository_name_from_remote(remote)
    if repository_name != EXPECTED_REPOSITORY_NAME:
        raise BootstrapError(
            "Repository origin identity check failed: expected repository "
            f"{EXPECTED_REPOSITORY_NAME!r}, found {repository_name!r}."
        )


def current_branch(root: Path) -> str:
    """Return the current branch name; reject detached HEAD."""

    branch = run_git(root, "branch", "--show-current")
    if not branch:
        raise BootstrapError("Detached HEAD is not a safe bootstrap execution context.")
    return branch


def worktree_changes(root: Path) -> list[str]:
    status = run_git(root, "status", "--porcelain")
    return [line for line in status.splitlines() if line.strip()]


def is_protected_branch(branch: str) -> bool:
    return branch in PROTECTED_BRANCHES or branch.startswith(PROTECTED_PREFIXES)


def validate_execution_context(
    *,
    branch: str,
    dirty: Sequence[str],
    apply: bool,
    allow_other_branch: bool,
) -> None:
    """Enforce branch and worktree safety before planning or applying changes."""

    if not branch:
        raise BootstrapError("Detached HEAD is not a safe bootstrap execution context.")

    if apply and is_protected_branch(branch):
        raise BootstrapError(
            f"Apply mode is forbidden on protected/release branch {branch!r}."
        )

    if apply and allow_other_branch:
        raise BootstrapError(
            "--allow-other-branch is restricted to dry-run mode and cannot be "
            "combined with --apply."
        )

    if apply and branch != EXPECTED_BRANCH:
        raise BootstrapError(
            f"Apply mode requires branch {EXPECTED_BRANCH!r}; found {branch!r}."
        )

    if branch != EXPECTED_BRANCH and not allow_other_branch:
        raise BootstrapError(
            f"Expected branch {EXPECTED_BRANCH!r}, found {branch!r}. "
            "Switch branches or use --allow-other-branch for an intentional dry-run."
        )

    if apply and dirty:
        raise BootstrapError(
            "Apply mode requires a clean worktree; commit, stash, or remove unrelated "
            "changes before retrying."
        )


def safe_relative(root: Path, path: Path) -> Path:
    """Validate *path* beneath *root* without following scaffold symlinks."""

    lexical = Path(path)
    if lexical.is_absolute():
        raise BootstrapError(f"Path escaped repository root: {path}")
    candidate = root / lexical
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BootstrapError(f"Path escaped repository root: {path}") from exc

    current = root
    for component in lexical.parts:
        if component in {"", "."}:
            continue
        current /= component
        if current.is_symlink():
            raise BootstrapError(
                f"Refusing scaffold path with symlinked component: {path}"
            )
    return lexical


def plan_actions(root: Path) -> list[Action]:
    """Return only missing, safe scaffold actions."""

    actions: list[Action] = []

    for directory in PACKAGE_DIRS:
        relative = safe_relative(root, directory)
        sibling_module = (root / relative).with_suffix(".py")
        if sibling_module.is_file():
            raise BootstrapError(
                "Refusing to shadow existing Python module with a package: "
                f"{sibling_module.relative_to(root)}"
            )

    for directory in (*PACKAGE_DIRS, *TEST_DIRS):
        relative = safe_relative(root, directory)
        target = root / relative
        if target.exists() and not target.is_dir():
            raise BootstrapError(f"Planned directory is occupied by a file: {relative}")
        if not target.exists():
            actions.append(Action("mkdir", relative, "create directory"))

    for marker in PACKAGE_MARKERS:
        relative = safe_relative(root, marker)
        if not (root / relative).exists():
            actions.append(Action("write", relative, "create Python package marker"))

    for marker in TEST_MARKERS:
        relative = safe_relative(root, marker)
        if not (root / relative).exists():
            actions.append(Action("write", relative, "create tracked test-boundary marker"))

    for path, content in README_FILES.items():
        relative = safe_relative(root, path)
        if not (root / relative).exists():
            actions.append(Action("write", relative, f"create {len(content)}-byte README"))

    plan_file = Path("docs") / "backend" / "BRANCH_PLAN.md"
    relative = safe_relative(root, plan_file)
    if not (root / relative).exists():
        actions.append(Action("write", relative, "record backend branch sequence"))

    return actions


def write_if_missing(path: Path, content: str) -> bool:
    """Write *content* only when *path* is absent.

    Identical existing content is idempotent. Any different existing content is a
    hard error rather than an overwrite.
    """

    if path.exists():
        existing = path.read_text(encoding="utf-8", errors="strict")
        if existing == content:
            return False
        raise BootstrapError(
            f"Refusing to overwrite existing non-identical file: {path}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def content_for_action(root: Path, action: Action) -> str:
    readme_lookup = {
        safe_relative(root, path): content for path, content in README_FILES.items()
    }
    package_markers = {safe_relative(root, path) for path in PACKAGE_MARKERS}
    test_markers = {safe_relative(root, path) for path in TEST_MARKERS}
    branch_plan_path = safe_relative(
        root, Path("docs") / "backend" / "BRANCH_PLAN.md"
    )

    if action.path in package_markers:
        return PACKAGE_MARKER_CONTENT
    if action.path in test_markers:
        return TEST_MARKER_CONTENT
    if action.path in readme_lookup:
        return readme_lookup[action.path]
    if action.path == branch_plan_path:
        return f"# {BRANCH_PLAN}"
    raise BootstrapError(f"No content template for {action.path}")


def apply_actions(root: Path, actions: Iterable[Action]) -> None:
    """Apply a reviewed action plan without overwriting existing files."""

    for action in actions:
        target = root / action.path

        if action.kind == "mkdir":
            target.mkdir(parents=True, exist_ok=True)
            print(f"CREATE_DIR {action.path}")
            continue

        if action.kind != "write":
            raise BootstrapError(f"Unknown action kind: {action.kind}")

        if write_if_missing(target, content_for_action(root, action)):
            print(f"CREATE_FILE {action.path}")


def print_plan(actions: Iterable[Action]) -> None:
    planned = list(actions)
    if not planned:
        print("BOOTSTRAP_STATUS=NO_CHANGES_REQUIRED")
        return

    print("BOOTSTRAP_STATUS=CHANGES_PLANNED")
    for action in planned:
        print(f"{action.kind.upper()} {action.path} :: {action.detail}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safely scaffold missing BREERO backend production-foundation "
            "package boundaries."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write missing files/directories on the expected clean feature branch.",
    )
    parser.add_argument(
        "--allow-other-branch",
        action="store_true",
        help=(
            "Allow an intentional dry-run outside "
            "bootstrap/backend-production-foundation. This option cannot be "
            "combined with --apply."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        root = find_repo_root(Path.cwd())
        verify_breero_scope(root)
        branch = current_branch(root)
        dirty = worktree_changes(root)

        print(f"REPOSITORY_ROOT={root}")
        print(f"BRANCH={branch}")
        print("SCOPE=BREERO_BACKEND_ONLY")
        print("PRODUCTION_ACTIVATION=DISABLED")
        print("EXTERNAL_SENDS=DISABLED")
        print("PAYMENTS=DISABLED")
        print("PAYOUTS=DISABLED")
        print(f"WORKTREE_DIRTY={'YES' if dirty else 'NO'}")
        for line in dirty:
            print(f"WORKTREE_CHANGE={line}")

        validate_execution_context(
            branch=branch,
            dirty=dirty,
            apply=args.apply,
            allow_other_branch=args.allow_other_branch,
        )

        actions = plan_actions(root)
        print_plan(actions)

        if not args.apply:
            print("MODE=DRY_RUN")
            print("NEXT_SAFE_ACTION=review the plan on a clean feature branch")
            return 0

        apply_actions(root, actions)
        print("MODE=APPLY")
        print("BOOTSTRAP_APPLIED=YES")
        print(
            "NEXT_SAFE_ACTION=review git diff, run backend CI/tests, "
            "then update the draft PR"
        )
        return 0
    except BootstrapError as exc:
        print(f"BOOTSTRAP_ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
