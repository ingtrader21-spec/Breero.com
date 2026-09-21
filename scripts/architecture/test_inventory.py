"""Acceptance checks for the architecture evidence, without running business flows."""

import json
import os
import unittest
from unittest.mock import patch

import inventory


class InventoryAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recorded = json.loads(inventory.OUTPUT.read_text(encoding="utf-8"))
        # Ambient production configuration must neither alter the evidence nor
        # trigger file-backed credentials, telemetry or external connections.
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL_FILE": "/nonexistent/breero-inventory-must-not-read",
                "STRIPE_SECRET_KEY": "invalid-if-loaded",
                "PAYMENTS_ENABLED": "true",
                "GEOCODING_ENABLED": "true",
                "KEYCLOAK_ENABLED": "true",
                "OTEL_ENABLED": "true",
            },
        ):
            cls.actual = inventory.collect(cls.recorded["baseline_main_sha"])

    def test_reproducible_despite_ambient_configuration(self):
        self.assertEqual(json.loads(json.dumps(self.actual)), self.recorded)

    def test_nested_application_routes_and_hidden_metrics_are_inventoried(self):
        for profile in self.actual["runtime_profiles"].values():
            operations = profile["operations"]
            self.assertEqual(len(operations), len(set(operations)))
            self.assertIn("GET /api/v2/capabilities", operations)
            self.assertIn("GET /metrics", operations)
            indexed = {
                f"{row['method']} {row['path']}": row
                for row in self.actual["api_operations"]
            }
            self.assertEqual(
                sum(indexed[key]["included_in_openapi"] for key in operations),
                profile["openapi_operations"],
            )
            self.assertTrue(
                any(
                    row["path"] == "/openapi.json"
                    for row in profile["framework_routes"]
                )
            )

    def test_capability_profiles_do_not_misreport_dark_routes(self):
        default = self.actual["runtime_profiles"]["default"]
        canonical = self.actual["runtime_profiles"]["canonical_contract"]
        implemented = self.actual["runtime_profiles"]["implemented_routes"]
        self.assertFalse(default["openapi_matches_artifact"])
        self.assertTrue(canonical["openapi_matches_artifact"])
        self.assertNotIn("POST /api/v1/booking/holds", default["operations"])
        self.assertIn("POST /api/v1/booking/holds", canonical["operations"])
        self.assertNotIn("POST /api/v1/payments/webhooks/stripe", default["operations"])
        self.assertIn(
            "POST /api/v1/payments/webhooks/stripe", implemented["operations"]
        )
        self.assertGreater(
            canonical["openapi_operations"], default["openapi_operations"]
        )
        self.assertGreater(
            implemented["openapi_operations"], default["openapi_operations"]
        )

    def test_reviewed_audiences_are_preserved_as_dependency_evidence(self):
        indexed = {
            f"{row['method']} {row['path']}": row
            for row in self.actual["api_operations"]
        }
        customer = indexed["POST /api/v1/jobs/work-requests/{request_id}/decision"]
        self.assertTrue(
            any(
                "customer" in dep.get("allowed_roles", [])
                for dep in customer["authentication"]["dependencies"]
            )
        )
        for row in self.actual["api_operations"]:
            if row["path"].startswith("/api/v1/integrations/"):
                allowed = {
                    role
                    for dep in row["authentication"]["dependencies"]
                    for role in dep.get("allowed_roles", [])
                }
                self.assertIn("finance", allowed)
                self.assertNotIn("operations", allowed)

    def test_recorded_sources_exist_and_have_valid_digests(self):
        for section in (
            "backend_modules",
            "alembic_revisions",
            "frontend_routes",
            "deployment_files",
            "contract_sources",
            "odoo_addon_sources",
        ):
            for row in self.actual[section]:
                with self.subTest(source=row["path"]):
                    path = inventory.ROOT / row["path"]
                    self.assertTrue(path.is_file())
                    self.assertEqual(inventory.digest(path), row["sha256"])
        self.assertFalse(self.actual["required_directories"]["infrastructure"])
        self.assertEqual(
            set(self.actual["backend_domains"]),
            {
                path.name
                for path in (inventory.ROOT / "apps/api/app/domains").iterdir()
                if path.is_dir() and (path / "__init__.py").is_file()
            },
        )

    def test_narrative_route_tables_cover_machine_inventory(self):
        current = (inventory.ROOT / "docs/architecture/CURRENT_SYSTEM.md").read_text()
        api = (inventory.ROOT / "docs/architecture/API_REGISTRY.md").read_text()
        for row in self.actual["frontend_routes"]:
            self.assertIn(
                f"| {row['app']} | {row['kind']} | `{row['route']}` |", current
            )
        for row in self.actual["api_operations"]:
            self.assertIn(f"| {row['method']} | `{row['path']}` |", api)
        for domain in self.actual["backend_domains"]:
            self.assertIn(f"| `{domain}` |", current)


if __name__ == "__main__":
    unittest.main()
