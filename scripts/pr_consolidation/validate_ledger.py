#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


EXPECTED_PULL_REQUESTS = {
    39, 40, 41, 47, 55, 58, 59, 60, 62, 65, 67, 69,
    70, 71, 72, 100, 101, 102, 105, 109, 110, 115, 117, 123,
}
DISPOSITIONS = {
    "candidate",
    "replacement_required",
    "stacked",
    "superseded",
    "unsafe",
}
FINAL_EVIDENCE_STATUSES = {"complete", "merged", "superseded_verified"}
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
REQUIRED_ENTRY_FIELDS = {
    "pull_request",
    "title",
    "branch",
    "original_head",
    "original_base",
    "owning_domain",
    "dependencies",
    "affected_contracts",
    "disposition",
    "evidence_status",
    "final_evidence",
    "replacement_pr",
    "replacement_sha",
    "rationale",
}


def _is_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_utc_timestamp(value: Any) -> bool:
    return isinstance(value, str) and UTC_TIMESTAMP.fullmatch(value) is not None


def validate(document: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["ledger root must be an object"]
    if document.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if document.get("repository") != "ingtrader21-spec/Breero.com":
        errors.append("repository must equal ingtrader21-spec/Breero.com")
    if not _is_sha(document.get("baseline_main_sha")):
        errors.append("baseline_main_sha must be a lowercase 40-character SHA")
    if not _is_utc_timestamp(document.get("generated_at")):
        errors.append("generated_at must be an RFC 3339 UTC timestamp")
    if document.get("production_deployed") is not False:
        errors.append("production_deployed must be false")

    entries = document.get("entries")
    if not isinstance(entries, list):
        return errors + ["entries must be an array"]

    seen: set[int] = set()
    for index, entry in enumerate(entries):
        prefix = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in sorted(REQUIRED_ENTRY_FIELDS):
            if field not in entry:
                errors.append(f"{prefix}.{field} must be present")

        number = entry.get("pull_request")
        if not isinstance(number, int):
            errors.append(f"{prefix}.pull_request must be an integer")
        elif number in seen:
            errors.append(f"{prefix}.pull_request duplicate pull_request {number}")
        else:
            seen.add(number)

        disposition = entry.get("disposition")
        if disposition not in DISPOSITIONS:
            errors.append(
                f"{prefix}.disposition must be one of "
                "candidate, replacement_required, stacked, superseded, unsafe"
            )
        for field in ("original_head", "original_base"):
            if field in entry and not _is_sha(entry[field]):
                errors.append(f"{prefix}.{field} must be a lowercase 40-character SHA")
        dependencies = entry.get("dependencies")
        if not isinstance(dependencies, list):
            errors.append(f"{prefix}.dependencies must contain only integer pull requests")
        else:
            for dependency in dependencies:
                if not isinstance(dependency, int) or isinstance(dependency, bool):
                    errors.append(
                        f"{prefix}.dependencies must contain only integer pull requests"
                    )
                    continue
                if dependency not in EXPECTED_PULL_REQUESTS:
                    errors.append(
                        f"{prefix}.dependencies contains unknown pull request {dependency}"
                    )
                if dependency == number:
                    errors.append(f"{prefix}.dependencies cannot reference itself")

        affected_contracts = entry.get("affected_contracts")
        if not isinstance(affected_contracts, list) or not all(
            isinstance(item, str) and bool(item.strip())
            for item in affected_contracts
        ):
            errors.append(
                f"{prefix}.affected_contracts must contain only non-empty strings"
            )
        for field in ("title", "branch", "owning_domain", "evidence_status", "rationale"):
            if field in entry and (not isinstance(entry[field], str) or not entry[field].strip()):
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if entry.get("replacement_pr") is not None and not isinstance(
            entry.get("replacement_pr"), int
        ):
            errors.append(f"{prefix}.replacement_pr must be null or an integer")
        if entry.get("replacement_sha") is not None and not _is_sha(
            entry.get("replacement_sha")
        ):
            errors.append(
                f"{prefix}.replacement_sha must be null or a lowercase 40-character SHA"
            )

        final_evidence = entry.get("final_evidence")
        if entry.get("evidence_status") in FINAL_EVIDENCE_STATUSES:
            if not isinstance(final_evidence, dict):
                errors.append(f"{prefix}.final_evidence must be present for final status")
            else:
                if not _is_sha(final_evidence.get("checked_head_sha")):
                    errors.append(
                        f"{prefix}.final_evidence.checked_head_sha must be a lowercase 40-character SHA"
                    )
                tests = final_evidence.get("tests")
                if not isinstance(tests, list) or not tests or not all(
                    isinstance(test, str) and bool(test.strip()) for test in tests
                ):
                    errors.append(
                        f"{prefix}.final_evidence.tests must contain non-empty test results"
                    )
                if final_evidence.get("review_state") != "approved":
                    errors.append(
                        f"{prefix}.final_evidence.review_state must equal approved"
                    )
                if not _is_sha(final_evidence.get("accepted_merge_sha")):
                    errors.append(
                        f"{prefix}.final_evidence.accepted_merge_sha must be a lowercase 40-character SHA"
                    )
                if not _is_utc_timestamp(final_evidence.get("checked_at")):
                    errors.append(
                        f"{prefix}.final_evidence.checked_at must be an RFC 3339 UTC timestamp"
                    )
        elif final_evidence is not None:
            errors.append(f"{prefix}.final_evidence must be null until final status")

    missing = sorted(EXPECTED_PULL_REQUESTS - seen)
    unexpected = sorted(seen - EXPECTED_PULL_REQUESTS)
    if missing:
        errors.append(f"entries missing pull requests: {missing}")
    if unexpected:
        errors.append(f"entries contain unexpected pull requests: {unexpected}")
    if len(entries) != len(EXPECTED_PULL_REQUESTS):
        errors.append(f"entries must contain exactly {len(EXPECTED_PULL_REQUESTS)} records")
    return errors


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    path = Path(arguments[0]) if arguments else Path(
        "artifacts/pr-consolidation/ledger.v1.json"
    )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ledger read failed: {exc}", file=sys.stderr)
        return 2
    errors = validate(document)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated {len(document['entries'])} pull-request records from {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
