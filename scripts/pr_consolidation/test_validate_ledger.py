"""Exercise the offline ledger gate using missing, malformed and incomplete evidence."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "artifacts/pr-consolidation/ledger.v1.json"
VALIDATOR = Path(__file__).with_name("validate_ledger.py")
ORIGINAL_PRS = {39, 40, 41, 47, 55, 58, 59, 60, 62, 65, 67, 69,
                70, 71, 72, 100, 101, 102, 105, 109, 110, 115, 117, 123}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(LEDGER.is_file(), "The required 24-PR ledger is absent")
        self.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))

    def validate(self, value):
        self.assertTrue(VALIDATOR.is_file(), "The ledger validator is absent")
        spec = importlib.util.spec_from_file_location("validate_ledger", VALIDATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate(value)

    def test_seed_covers_all_original_prs_and_passes(self):
        self.assertEqual({row["number"] for row in self.ledger["prs"]}, ORIGINAL_PRS)
        self.assertEqual(len(self.ledger["prs"]), 24)
        self.assertEqual(self.validate(self.ledger), [])

    def test_missing_or_duplicate_pr_is_rejected(self):
        for kind in ("missing", "duplicate", "unexpected"):
            with self.subTest(kind=kind):
                data = copy.deepcopy(self.ledger)
                if kind == "missing":
                    data["prs"].pop()
                elif kind == "duplicate":
                    data["prs"].append(copy.deepcopy(data["prs"][0]))
                else:
                    data["prs"][0]["number"] = 999
                self.assertTrue(self.validate(data))

    def test_required_fields_cannot_be_omitted(self):
        for field in ("original", "owning_domain", "dependencies", "affected_contracts",
                      "disposition", "disposition_reason", "replacement_pr", "accepted_sha",
                      "evidence"):
            with self.subTest(field=field):
                data = copy.deepcopy(self.ledger)
                del data["prs"][0][field]
                self.assertTrue(self.validate(data))

    def test_original_identity_requires_full_head_base_and_merge_base(self):
        for field in ("head_sha", "base_sha", "merge_base_sha"):
            for bad in (None, "93d72d0", "z" * 40, "0" * 40):
                with self.subTest(field=field, value=bad):
                    data = copy.deepcopy(self.ledger)
                    data["prs"][0]["original"][field] = bad
                    self.assertTrue(self.validate(data))

    def test_disposition_must_be_one_known_value(self):
        for bad in (None, "merged", ["candidate", "unsafe"], ""):
            with self.subTest(value=bad):
                data = copy.deepcopy(self.ledger)
                data["prs"][0]["disposition"] = bad
                self.assertTrue(self.validate(data))

    def test_empty_ownership_contracts_or_reason_is_rejected(self):
        for field, value in (("owning_domain", " "), ("affected_contracts", []),
                             ("affected_contracts", [""]), ("disposition_reason", "")):
            with self.subTest(field=field):
                data = copy.deepcopy(self.ledger)
                data["prs"][0][field] = value
                self.assertTrue(self.validate(data))

    def test_invalid_or_cyclic_dependencies_are_rejected(self):
        for bad in (None, [999], [39], [40, 40], [True]):
            with self.subTest(value=bad):
                data = copy.deepcopy(self.ledger)
                data["prs"][0]["dependencies"] = bad
                self.assertTrue(self.validate(data))
        data = copy.deepcopy(self.ledger)
        by_number = {row["number"]: row for row in data["prs"]}
        by_number[39]["dependencies"] = [40]
        by_number[40]["dependencies"] = [39]
        self.assertTrue(self.validate(data))

    def test_unassessed_rows_cannot_claim_replacement_acceptance(self):
        for field, bad in (("replacement_pr", True), ("replacement_pr", 0),
                           ("accepted_sha", "short"), ("accepted_sha", "a" * 40)):
            with self.subTest(field=field, value=bad):
                data = copy.deepcopy(self.ledger)
                data["prs"][0][field] = bad
                self.assertTrue(self.validate(data))

    def test_evidence_status_is_required_and_known(self):
        for value in (None, "green", "accepted"):
            with self.subTest(value=value):
                data = copy.deepcopy(self.ledger)
                data["prs"][0]["evidence"]["status"] = value
                self.assertTrue(self.validate(data))

    def test_missing_or_wrong_head_check_evidence_is_rejected(self):
        for change in ("missing_checks", "wrong_head", "missing_reviews", "unknown_threads"):
            with self.subTest(change=change):
                data = copy.deepcopy(self.ledger)
                evidence = data["prs"][0]["evidence"]
                if change == "missing_checks":
                    del evidence["checks"]
                elif change == "wrong_head":
                    evidence["checks"][0]["head_sha"] = "a" * 40
                elif change == "missing_reviews":
                    del evidence["reviews"]
                else:
                    evidence["unresolved_threads"] = None
                self.assertTrue(self.validate(data))

    def test_truncated_files_or_threads_are_rejected(self):
        for change in ("files", "threads"):
            with self.subTest(change=change):
                data = copy.deepcopy(self.ledger)
                evidence = data["prs"][0]["evidence"]
                if change == "files":
                    evidence["changed_files"].pop()
                else:
                    evidence["unresolved_threads"]["count"] += 1
                self.assertTrue(self.validate(data))

    def test_malformed_shapes_report_errors_without_crashing(self):
        for value in (None, [], {}, {"prs": None}, {"prs": [None]},
                      {"prs": [{"number": []}]}):
            with self.subTest(value=value):
                self.assertTrue(self.validate(value))
        for field in ("original", "evidence"):
            data = copy.deepcopy(self.ledger)
            data["prs"][0][field] = []
            self.assertTrue(self.validate(data))

    def test_cli_is_read_only_and_independent_of_working_directory(self):
        before = LEDGER.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=directory,
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("24", result.stdout)
        self.assertEqual(LEDGER.read_bytes(), before)

    def test_cli_rejects_missing_invalid_and_duplicate_key_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            for content in (None, "{broken", '{"prs": [], "prs": []}'):
                with self.subTest(content=content):
                    if content is not None:
                        path.write_text(content, encoding="utf-8")
                    result = subprocess.run([sys.executable, str(VALIDATOR), str(path)],
                                            capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
