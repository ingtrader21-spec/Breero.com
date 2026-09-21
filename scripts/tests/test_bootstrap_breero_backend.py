from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "bootstrap_breero_backend.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_breero_backend", MODULE_PATH)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap
SPEC.loader.exec_module(bootstrap)


class ExecutionContextTests(unittest.TestCase):
    def test_expected_clean_branch_allows_apply(self) -> None:
        bootstrap.validate_execution_context(
            branch=bootstrap.EXPECTED_BRANCH,
            dirty=[],
            apply=True,
            allow_other_branch=False,
        )

    def test_dirty_dry_run_is_allowed_and_reportable(self) -> None:
        bootstrap.validate_execution_context(
            branch=bootstrap.EXPECTED_BRANCH,
            dirty=[" M README.md"],
            apply=False,
            allow_other_branch=False,
        )

    def test_dirty_apply_is_rejected(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "clean worktree"):
            bootstrap.validate_execution_context(
                branch=bootstrap.EXPECTED_BRANCH,
                dirty=[" M README.md"],
                apply=True,
                allow_other_branch=False,
            )

    def test_protected_branch_apply_is_rejected_even_with_override(self) -> None:
        for branch in ("main", "master", "release/2026-08", "production/hotfix"):
            with self.subTest(branch=branch):
                with self.assertRaisesRegex(bootstrap.BootstrapError, "forbidden"):
                    bootstrap.validate_execution_context(
                        branch=branch,
                        dirty=[],
                        apply=True,
                        allow_other_branch=True,
                    )

    def test_other_branch_requires_explicit_override_for_dry_run(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "Expected branch"):
            bootstrap.validate_execution_context(
                branch="feature/example",
                dirty=[],
                apply=False,
                allow_other_branch=False,
            )

        bootstrap.validate_execution_context(
            branch="feature/example",
            dirty=[],
            apply=False,
            allow_other_branch=True,
        )

    def test_other_branch_apply_is_rejected_without_override(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "Apply mode requires branch"):
            bootstrap.validate_execution_context(
                branch="feature/example",
                dirty=[],
                apply=True,
                allow_other_branch=False,
            )

    def test_branch_override_is_restricted_to_dry_run(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "dry-run mode"):
            bootstrap.validate_execution_context(
                branch="feature/example",
                dirty=[],
                apply=True,
                allow_other_branch=True,
            )

    def test_redundant_override_cannot_be_combined_with_apply(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "dry-run mode"):
            bootstrap.validate_execution_context(
                branch=bootstrap.EXPECTED_BRANCH,
                dirty=[],
                apply=True,
                allow_other_branch=True,
            )

    def test_detached_head_is_rejected(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "Detached HEAD"):
            bootstrap.validate_execution_context(
                branch="",
                dirty=[],
                apply=False,
                allow_other_branch=True,
            )


class FileSafetyTests(unittest.TestCase):
    def test_planned_directory_occupied_by_file_fails_before_writes(self) -> None:
        for directory in (*bootstrap.PACKAGE_DIRS, *bootstrap.TEST_DIRS):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                target = root / directory
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("existing content")
                before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
                with self.assertRaises(bootstrap.BootstrapError):
                    bootstrap.plan_actions(root)
                self.assertEqual(before, sorted(str(p.relative_to(root)) for p in root.rglob("*")))
                self.assertEqual(target.read_text(), "existing content")

    def test_safe_relative_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(bootstrap.BootstrapError, "escaped"):
                bootstrap.safe_relative(root, Path("../outside.txt"))

    def test_plan_rejects_symlinked_scaffold_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            redirect = root / "redirect"
            redirect.mkdir()
            boundary = root / bootstrap.APP_ROOT / "application"
            boundary.parent.mkdir(parents=True)
            boundary.symlink_to(redirect, target_is_directory=True)
            with self.assertRaisesRegex(bootstrap.BootstrapError, "symlinked component"):
                bootstrap.plan_actions(root)
            self.assertFalse((redirect / "__init__.py").exists())

    def test_write_if_missing_is_idempotent_for_identical_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "file.txt"
            self.assertTrue(bootstrap.write_if_missing(path, "expected\n"))
            self.assertFalse(bootstrap.write_if_missing(path, "expected\n"))

    def test_write_if_missing_rejects_non_identical_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "file.txt"
            path.write_text("existing\n", encoding="utf-8")
            with self.assertRaisesRegex(bootstrap.BootstrapError, "Refusing to overwrite"):
                bootstrap.write_if_missing(path, "different\n")

    def test_apply_plan_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            actions = bootstrap.plan_actions(root)
            self.assertTrue(actions)
            bootstrap.apply_actions(root, actions)
            self.assertEqual(bootstrap.plan_actions(root), [])

    def test_apply_tracks_test_boundaries_and_preserves_odoo_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            integrations = root / "apps" / "api" / "app" / "integrations"
            integrations.mkdir(parents=True)
            (root / "apps" / "api" / "app" / "__init__.py").write_text("", encoding="utf-8")
            (integrations / "__init__.py").write_text("", encoding="utf-8")
            (integrations / "odoo.py").write_text(
                "class OdooAdapter: pass\nclass OdooDeliveryError(Exception): pass\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"],
                cwd=root,
                check=True,
            )

            bootstrap.apply_actions(root, bootstrap.plan_actions(root))
            status = subprocess.run(
                ["git", "status", "--short", "--untracked-files=all"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            for directory in bootstrap.TEST_DIRS:
                marker = directory / "README.md"
                self.assertTrue((root / marker).is_file())
                self.assertIn(str(marker), status)
            self.assertFalse((integrations / "odoo" / "__init__.py").exists())

            previous_path = list(sys.path)
            previous_cwd = Path.cwd()
            try:
                os.chdir(root / "apps" / "api")
                sys.path.insert(0, str(root / "apps" / "api"))
                from app.integrations.odoo import OdooAdapter, OdooDeliveryError

                self.assertIsNotNone(OdooAdapter)
                self.assertTrue(issubclass(OdooDeliveryError, Exception))
            finally:
                os.chdir(previous_cwd)
                sys.path[:] = previous_path
                for name in tuple(sys.modules):
                    if name == "app" or name.startswith("app."):
                        sys.modules.pop(name, None)

            self.assertEqual(bootstrap.plan_actions(root), [])

    def test_plan_fails_closed_for_any_same_name_module_and_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            conflicting = bootstrap.PACKAGE_DIRS[0]
            module = (root / conflicting).with_suffix(".py")
            module.parent.mkdir(parents=True)
            module.write_text("VALUE = 1\n", encoding="utf-8")
            with self.assertRaisesRegex(bootstrap.BootstrapError, "shadow"):
                bootstrap.plan_actions(root)


class RepositoryScopeTests(unittest.TestCase):
    def _create_repo(self, remote: str, readme: str = "# BREERO\n") -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "apps" / "api").mkdir(parents=True)
        (root / "README.md").write_text(readme, encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=root, check=True)
        return root

    def test_verified_breero_https_origin_is_accepted(self) -> None:
        root = self._create_repo("https://github.com/appolon1908-hue/Breero.com.git")
        bootstrap.verify_breero_scope(root)

    def test_verified_breero_ssh_origin_is_accepted(self) -> None:
        root = self._create_repo("git@github.com:appolon1908-hue/Breero.com.git")
        bootstrap.verify_breero_scope(root)

    def test_readme_cannot_mask_an_unrelated_origin(self) -> None:
        root = self._create_repo("https://github.com/example/unrelated-service.git")
        with self.assertRaisesRegex(bootstrap.BootstrapError, "origin identity"):
            bootstrap.verify_breero_scope(root)

    def test_cross_project_remote_is_rejected(self) -> None:
        cross_project = "https://github.com/example/" + "Money" + "bee-Backend.git"
        root = self._create_repo(cross_project)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "origin identity"):
            bootstrap.verify_breero_scope(root)

    def test_breero_origin_still_requires_breero_readme_identity(self) -> None:
        root = self._create_repo(
            "https://github.com/appolon1908-hue/Breero.com.git",
            readme="# Unrelated application\n",
        )
        with self.assertRaisesRegex(bootstrap.BootstrapError, "README"):
            bootstrap.verify_breero_scope(root)

    def test_repository_name_parser_handles_supported_remote_forms(self) -> None:
        remotes = (
            "https://github.com/appolon1908-hue/Breero.com.git",
            "ssh://git@github.com/appolon1908-hue/Breero.com.git",
            "git@github.com:appolon1908-hue/Breero.com.git",
        )
        for remote in remotes:
            with self.subTest(remote=remote):
                self.assertEqual(
                    bootstrap.repository_name_from_remote(remote),
                    bootstrap.EXPECTED_REPOSITORY_NAME,
                )

    def test_missing_monorepo_structure_is_rejected(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "expected BREERO"):
            bootstrap.verify_breero_scope(root)


if __name__ == "__main__":
    unittest.main()
