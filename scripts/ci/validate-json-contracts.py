#!/usr/bin/env python3
"""Validate repository JSON and the release-image count contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class JsonContractError(ValueError):
    """Raised when JSON syntax or a cross-field contract is invalid."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JsonContractError(f"duplicate object key: {key}")
        result[key] = value
    return result


def _json_files(root: Path) -> list[Path]:
    ignored = {".git", "node_modules", ".next", "coverage"}
    return sorted(
        path
        for path in root.rglob("*.json")
        if not any(part in ignored for part in path.relative_to(root).parts)
    )


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, JsonContractError) as error:
        raise JsonContractError(f"{path}: {error}") from error


def _validate_orchestrator_contract(root: Path, documents: dict[Path, Any]) -> None:
    path = root / ".codestra/production-orchestrator-contract.v1.json"
    if path not in documents:
        return

    document = documents[path]
    if not isinstance(document, dict):
        raise JsonContractError(f"{path}: top-level value must be an object")
    policy = document.get("artifact_policy")
    if not isinstance(policy, dict):
        raise JsonContractError(f"{path}: artifact_policy must be an object")
    repositories = policy.get("image_repositories")
    if not isinstance(repositories, list) or not all(
        isinstance(repository, str) and repository for repository in repositories
    ):
        raise JsonContractError(f"{path}: image_repositories must be non-empty strings")

    expected = len(repositories)
    minimum = policy.get("minimum_images")
    maximum = policy.get("maximum_images")
    if minimum != expected or maximum != expected:
        raise JsonContractError(
            f"{path}: image count must match {expected} declared repositories "
            f"(minimum={minimum!r}, maximum={maximum!r})"
        )

    blockers = document.get("blockers")
    count_marker = f"{expected} immutable release images"
    if not isinstance(blockers, list) or not any(
        isinstance(blocker, str) and count_marker in blocker for blocker in blockers
    ):
        raise JsonContractError(
            f"{path}: blockers must state the canonical count as {count_marker!r}"
        )


def validate(root: Path) -> int:
    files = _json_files(root)
    documents = {path: _load(path) for path in files}
    _validate_orchestrator_contract(root, documents)
    return len(files)


def main() -> int:
    root = Path.cwd().resolve()
    try:
        count = validate(root)
    except JsonContractError as error:
        print(f"JSON_CONTRACTS=FAIL {error}", file=sys.stderr)
        return 1
    print(f"JSON_CONTRACTS=PASS files={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
