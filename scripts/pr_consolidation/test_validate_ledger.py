from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = ROOT / "artifacts" / "pr-consolidation" / "ledger.v1.json"
VALIDATOR_PATH = ROOT / "scripts" / "pr_consolidation" / "validate_ledger.py"
EXPECTED_PULL_REQUESTS = {
    39,
    40,
    41,
    47,
    55,
    58,
    59,
    60,
    62,
    65,
    67,
    69,
    70,
    71,
    72,
    100,
    101,
    102,
    105,
    109,
    110,
    115,
    117,
    123,
}


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_ledger", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load validator at {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConsolidationLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_validator()
        self.document = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))

    def test_canonical_ledger_is_valid(self) -> None:
        self.assertEqual([], self.validator.validate(self.document))

    def test_ledger_covers_each_remaining_pull_request_once(self) -> None:
        numbers = [entry["pull_request"] for entry in self.document["entries"]]
        self.assertEqual(EXPECTED_PULL_REQUESTS, set(numbers))
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_missing_required_evidence_is_rejected(self) -> None:
        invalid = json.loads(json.dumps(self.document))
        del invalid["entries"][0]["evidence_status"]
        self.assertIn(
            "entries[0].evidence_status must be present",
            self.validator.validate(invalid),
        )

    def test_invalid_top_level_provenance_is_rejected(self) -> None:
        invalid = json.loads(json.dumps(self.document))
        invalid["repository"] = "example/wrong-repository"
        invalid["generated_at"] = "yesterday"
        invalid["production_deployed"] = "false"
        errors = self.validator.validate(invalid)
        self.assertIn("repository must equal ingtrader21-spec/Breero.com", errors)
        self.assertIn("generated_at must be an RFC 3339 UTC timestamp", errors)
        self.assertIn("production_deployed must be false", errors)

    def test_dependency_must_reference_another_known_pull_request(self) -> None:
        invalid = json.loads(json.dumps(self.document))
        invalid["entries"][0]["dependencies"] = ["41", 999, 39]
        errors = self.validator.validate(invalid)
        self.assertTrue(any("dependencies must contain only integer" in error for error in errors))
        self.assertTrue(any("dependencies contains unknown pull request 999" in error for error in errors))
        self.assertTrue(any("dependencies cannot reference itself" in error for error in errors))

    def test_affected_contracts_require_non_empty_strings(self) -> None:
        invalid = json.loads(json.dumps(self.document))
        invalid["entries"][0]["affected_contracts"] = [123, ""]
        self.assertTrue(
            any(
                "affected_contracts must contain only non-empty strings" in error
                for error in self.validator.validate(invalid)
            )
        )

    def test_final_evidence_requires_exact_head_tests_review_and_merge(self) -> None:
        invalid = json.loads(json.dumps(self.document))
        invalid["entries"][0]["evidence_status"] = "complete"
        invalid["entries"][0]["final_evidence"] = {
            "checked_head_sha": "bad-sha",
            "tests": [],
            "review_state": "pending",
            "accepted_merge_sha": None,
            "checked_at": "yesterday",
        }
        errors = self.validator.validate(invalid)
        self.assertTrue(any("final_evidence.checked_head_sha" in error for error in errors))
        self.assertTrue(any("final_evidence.tests" in error for error in errors))
        self.assertTrue(any("final_evidence.review_state must equal approved" in error for error in errors))
        self.assertTrue(any("final_evidence.accepted_merge_sha" in error for error in errors))
        self.assertTrue(any("final_evidence.checked_at" in error for error in errors))

    def test_unknown_disposition_is_rejected(self) -> None:
        invalid = json.loads(json.dumps(self.document))
        invalid["entries"][0]["disposition"] = "merge_everything"
        self.assertIn(
            "entries[0].disposition must be one of candidate, replacement_required, "
            "stacked, superseded, unsafe",
            self.validator.validate(invalid),
        )

    def test_duplicate_pull_request_is_rejected(self) -> None:
        invalid = json.loads(json.dumps(self.document))
        invalid["entries"][1]["pull_request"] = invalid["entries"][0]["pull_request"]
        errors = self.validator.validate(invalid)
        self.assertTrue(any("duplicate pull_request" in error for error in errors))

    def test_validator_accepts_an_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps(self.document), encoding="utf-8")
            self.assertEqual(0, self.validator.main([str(path)]))


if __name__ == "__main__":
    unittest.main()
