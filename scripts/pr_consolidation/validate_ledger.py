"""Validate the historical PR ledger offline; never merge, close or certify a PR."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys


ORIGINAL_PRS = frozenset({39, 40, 41, 47, 55, 58, 59, 60, 62, 65, 67, 69,
                          70, 71, 72, 100, 101, 102, 105, 109, 110, 115, 117, 123})
DISPOSITIONS = {"candidate", "replacement_required", "stacked", "superseded", "unsafe"}
REPOSITORY = "ingtrader21-spec/Breero.com"
DEFAULT_LEDGER = Path(__file__).resolve().parents[2] / "artifacts/pr-consolidation/ledger.v1.json"


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def sha(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}", value)) and value != "0" * 40


def timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is not None
    except ValueError:
        return False


def github_url(value):
    return isinstance(value, str) and value.startswith("https://github.com/") and not any(
        char.isspace() for char in value
    )


def validate(data):
    """Return human-readable structural errors; historical failures remain evidence.

    A successful validation proves record completeness, not semantic acceptance,
    live GitHub state, test success, branch protection compliance or deployability.
    """
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    if not isinstance(data, dict):
        return ["ledger must be an object"]
    require(data.get("schema_version") == 1, "schema_version must be 1")
    require(data.get("repository") == REPOSITORY, "repository must identify canonical BREERO")
    require(sha(data.get("baseline_sha")), "baseline_sha must be a full commit SHA")
    require(timestamp(data.get("captured_at")), "captured_at must be a timezone-aware timestamp")
    require(data.get("capability_changed") is False, "consolidation must keep capabilities unchanged")
    rows = data.get("prs")
    if not isinstance(rows, list):
        return errors + ["prs must be a list containing all 24 original PRs"]
    numbers = [row.get("number") for row in rows if isinstance(row, dict)]
    valid_numbers = [number for number in numbers if type(number) is int]
    require(len(rows) == 24 and len(valid_numbers) == 24 and set(valid_numbers) == ORIGINAL_PRS,
            "prs must contain each original PR exactly once, with no additional PRs")
    graph = {}
    for index, row in enumerate(rows):
        label = f"prs[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{label} must be an object")
            continue
        number = row.get("number")
        if type(number) is int:
            label = f"PR #{number}"
        required = {"number", "title", "url", "original", "owning_domain", "dependencies",
                    "dependency_basis", "affected_contracts", "disposition", "disposition_reason",
                    "replacement_pr", "accepted_sha", "evidence"}
        require(required <= row.keys(), f"{label}: missing fields {sorted(required - row.keys())}")
        for field in ("title", "owning_domain", "disposition_reason", "dependency_basis"):
            require(nonempty(row.get(field)), f"{label}: {field} must be nonempty")
        require(row.get("url") == f"https://github.com/{REPOSITORY}/pull/{number}",
                f"{label}: url must point to its canonical PR")
        disposition = row.get("disposition")
        require(isinstance(disposition, str) and disposition in DISPOSITIONS,
                f"{label}: disposition must be exactly one known value")
        contracts = row.get("affected_contracts")
        require(isinstance(contracts, list) and bool(contracts) and all(map(nonempty, contracts)),
                f"{label}: affected_contracts must be a nonempty list of names or paths")
        dependencies = row.get("dependencies")
        valid_dependencies = isinstance(dependencies, list) and all(
            type(dep) is int and dep in ORIGINAL_PRS and dep != number for dep in dependencies
        )
        require(valid_dependencies, f"{label}: invalid dependencies")
        if valid_dependencies:
            require(len(dependencies) == len(set(dependencies)), f"{label}: duplicate dependencies")
            if type(number) is int:
                graph[number] = dependencies
        original = row.get("original")
        if not isinstance(original, dict):
            errors.append(f"{label}: original must be an object")
            original = {}
        for field in ("head_sha", "base_sha", "merge_base_sha"):
            require(sha(original.get(field)), f"{label}: original.{field} must be a full commit SHA")
        require(nonempty(original.get("base_ref")), f"{label}: original.base_ref is required")
        replacement = row.get("replacement_pr")
        require(replacement is None or (type(replacement) is int and replacement > 0),
                f"{label}: replacement_pr must be null or a positive PR number")
        accepted = row.get("accepted_sha")
        require(accepted is None or sha(accepted), f"{label}: accepted_sha must be null or a full SHA")
        evidence = row.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"{label}: evidence must be an object")
            continue
        status = evidence.get("status")
        require(isinstance(status, str) and status in {"captured_not_accepted", "blocked", "accepted"},
                f"{label}: unknown evidence status")
        if status == "accepted":
            require(type(replacement) is int and replacement > 0 and sha(accepted),
                    f"{label}: accepted evidence requires replacement/merge PR and accepted SHA")
            require(bool(evidence.get("acceptance_evidence_urls")) and
                    isinstance(evidence.get("acceptance_evidence_urls"), list) and
                    all(map(github_url, evidence["acceptance_evidence_urls"])),
                    f"{label}: accepted evidence requires linked acceptance records")
        else:
            require(accepted is None, f"{label}: unaccepted evidence cannot claim an accepted SHA")
        require(evidence.get("main_sha") == data.get("baseline_sha"),
                f"{label}: evidence must name the ledger baseline")
        require(timestamp(evidence.get("captured_at")), f"{label}: evidence capture time is required")
        require(evidence.get("retrieval_complete") is True,
                f"{label}: evidence retrieval must be explicitly complete")
        require(evidence.get("retrieval_errors") == [], f"{label}: evidence retrieval errors must be resolved")
        files = evidence.get("changed_files")
        count = evidence.get("changed_file_count")
        require(type(count) is int and count > 0, f"{label}: changed_file_count must be positive")
        require(isinstance(files, list) and len(files) == count,
                f"{label}: changed files must match the API count")
        paths = []
        if isinstance(files, list):
            for item in files:
                if not isinstance(item, dict):
                    errors.append(f"{label}: changed file must be an object")
                    continue
                path = item.get("path")
                require(nonempty(path) and not path.startswith("/") and ".." not in path.split("/"),
                        f"{label}: changed file needs a repository-relative path")
                if nonempty(path):
                    paths.append(path)
                require(nonempty(item.get("status")) and github_url(item.get("url")),
                        f"{label}: changed file needs status and source URL")
            require(len(paths) == len(set(paths)), f"{label}: duplicate changed files")
        checks = evidence.get("checks")
        require(isinstance(checks, list), f"{label}: checks must be a captured list (possibly empty)")
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    errors.append(f"{label}: check must be an object")
                    continue
                require(check.get("head_sha") == original.get("head_sha"),
                        f"{label}: check belongs to a different head")
                require(nonempty(check.get("name")) and nonempty(check.get("status")) and
                        "conclusion" in check and github_url(check.get("url")),
                        f"{label}: check needs name, status, conclusion and URL")
        reviews = evidence.get("reviews")
        require(isinstance(reviews, list), f"{label}: reviews must be a captured list (possibly empty)")
        if isinstance(reviews, list):
            for review in reviews:
                require(isinstance(review, dict) and nonempty(review.get("state")) and
                        sha(review.get("commit_sha")) and nonempty(review.get("reviewer")) and
                        github_url(review.get("url")), f"{label}: incomplete review record")
        threads = evidence.get("unresolved_threads")
        if not isinstance(threads, dict):
            errors.append(f"{label}: unresolved_threads must be a captured count and URLs")
        else:
            urls = threads.get("urls")
            require(type(threads.get("count")) is int and threads["count"] >= 0 and
                    isinstance(urls, list) and threads["count"] == len(urls) and
                    all(map(github_url, urls)), f"{label}: unresolved thread evidence is incomplete")

    def cycle(number, visiting, visited):
        if number in visiting:
            return True
        if number in visited:
            return False
        visiting.add(number)
        found = any(cycle(dep, visiting, visited) for dep in graph.get(number, []))
        visiting.remove(number)
        visited.add(number)
        return found

    visited = set()
    require(not any(cycle(number, set(), visited) for number in graph), "dependency graph contains a cycle")
    return errors


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    try:
        data = json.loads(args.ledger.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, ValueError) as error:
        print(f"Invalid ledger: {error}", file=sys.stderr)
        return 1
    errors = validate(data)
    if errors:
        print("Invalid ledger:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print("Valid ledger: 24 historical PR records; structure only, not acceptance or deployment approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
