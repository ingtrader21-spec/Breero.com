#!/usr/bin/env python3
"""Adversarial tests for deployment preflight validators."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


compose_validator = load_module(
    "compose_security_validator",
    ROOT / "scripts" / "deploy" / "validate-compose-security.py",
)
runtime_validator = load_module(
    "runtime_evidence_validator",
    ROOT / "scripts" / "deploy" / "validate-runtime-evidence.py",
)

API_IMAGE = "ghcr.io/example/breero-api@sha256:" + "1" * 64
WEB_IMAGE = "ghcr.io/example/breero-web@sha256:" + "2" * 64


def app_service(*, environment: bool = True, networks: list[str] | None = None) -> dict[str, object]:
    service: dict[str, object] = {
        "image": API_IMAGE,
        "read_only": True,
        "init": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "pids_limit": 64,
        "mem_limit": 268435456,
        "secrets": [
            "breero_database_url",
            "breero_redis_url",
            "breero_jwt_access_secret",
            "breero_jwt_refresh_secret",
        ],
        "networks": networks or ["breero_private"],
    }
    if environment:
        service["environment"] = dict(compose_validator.APP_SECRET_BINDINGS)
    return service


def backend_document(*, environment: bool = True) -> dict[str, object]:
    api = app_service(environment=environment, networks=["breero_private", "caddy_shared"])
    api["healthcheck"] = {"test": ["CMD", "true"]}
    services: dict[str, object] = {
        "migrate": app_service(environment=environment),
        "api": api,
        "worker": app_service(environment=environment),
        "scheduler": app_service(environment=environment),
        "postgres": {
            "image": "postgis/postgis@sha256:" + "3" * 64,
            "read_only": True,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "healthcheck": {"test": ["CMD", "true"]},
            "environment": {"POSTGRES_PASSWORD_FILE": "/run/secrets/breero_postgres_password"},
            "secrets": ["breero_postgres_password"],
            "networks": ["breero_private"],
        },
        "redis": {
            "image": "redis@sha256:" + "4" * 64,
            "read_only": True,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "healthcheck": {"test": ["CMD", "true"]},
            "command": ["redis-server", "--aclfile", "/run/secrets/breero_redis_acl"],
            "secrets": ["breero_redis_acl"],
            "networks": ["breero_private"],
        },
    }
    secret_names = {
        "breero_database_url",
        "breero_redis_url",
        "breero_jwt_access_secret",
        "breero_jwt_refresh_secret",
        "breero_postgres_password",
        "breero_redis_acl",
    }
    return {
        "services": services,
        "networks": {
            "breero_private": {"internal": True, "name": "breero_private_runtime"},
            "caddy_shared": {"external": True, "name": "breero_edge_runtime"},
        },
        "secrets": {name: {"file": f"/tmp/{name}"} for name in secret_names},
    }


def frontend_document() -> dict[str, object]:
    return {
        "services": {
            "web": {
                "image": WEB_IMAGE,
                "user": "1001:1001",
                "read_only": True,
                "init": True,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "pids_limit": 64,
                "mem_limit": 268435456,
                "healthcheck": {"test": ["CMD", "true"]},
                "networks": ["frontend"],
            }
        },
        "networks": {"frontend": {"external": True, "name": "breero_frontend_runtime"}},
    }


def caddy_document(*, reverse: bool = False) -> dict[str, object]:
    web_upstream = "api:8000" if reverse else "web:3000"
    api_upstream = "web:3000" if reverse else "api:8000"
    return {
        "apps": {
            "http": {
                "servers": {
                    "srv0": {
                        "routes": [
                            {
                                "match": [{"host": ["breero.com"]}],
                                "handle": [
                                    {
                                        "handler": "subroute",
                                        "routes": [
                                            {
                                                "handle": [
                                                    {
                                                        "handler": "reverse_proxy",
                                                        "upstreams": [{"dial": web_upstream}],
                                                    }
                                                ]
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "match": [{"host": ["api.breero.com"]}],
                                "handle": [
                                    {
                                        "handler": "reverse_proxy",
                                        "upstreams": [{"dial": api_upstream}],
                                    }
                                ],
                            },
                        ]
                    }
                }
            }
        }
    }


def contradictory_caddy_document() -> dict[str, object]:
    return {
        "routes": [
            {
                "match": [{"host": ["breero.com"]}],
                "handle": [
                    {
                        "handler": "subroute",
                        "routes": [
                            {
                                "match": [{"host": ["api.breero.com"]}],
                                "handle": [
                                    {
                                        "handler": "reverse_proxy",
                                        "upstreams": [{"dial": "web:3000"}],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "match": [{"host": ["api.breero.com"]}],
                "handle": [
                    {
                        "handler": "subroute",
                        "routes": [
                            {
                                "match": [{"host": ["breero.com"]}],
                                "handle": [
                                    {
                                        "handler": "reverse_proxy",
                                        "upstreams": [{"dial": "api:8000"}],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ]
    }


class WorkflowPermissionTests(unittest.TestCase):
    def write_workflow(self, text: str) -> Path:
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        self.addCleanup(lambda: os.unlink(temp.name))
        temp.write(text)
        temp.close()
        return Path(temp.name)

    def safe_workflow(self, extra: str = "") -> str:
        return f"""name: test
on: pull_request
permissions:
  contents: read
jobs:
  test:
{extra}    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{'a' * 40}
        with:
          persist-credentials: false
"""

    def test_job_level_write_is_rejected(self) -> None:
        workflow = self.write_workflow(self.safe_workflow("    permissions:\n      actions: write\n"))
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_workflow(workflow)

    def test_quoted_permissions_key_is_parsed_and_rejected(self) -> None:
        workflow = self.write_workflow(self.safe_workflow('    "permissions": write-all\n'))
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_workflow(workflow)

    def test_write_all_is_rejected(self) -> None:
        workflow = self.write_workflow(
            self.safe_workflow().replace("permissions:\n  contents: read", "permissions: write-all")
        )
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_workflow(workflow)

    def test_unpinned_action_is_rejected(self) -> None:
        workflow = self.write_workflow(
            self.safe_workflow().replace("actions/checkout@" + "a" * 40, "actions/checkout@v4")
        )
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_workflow(workflow)

    def test_quoted_uses_key_is_parsed_and_rejected(self) -> None:
        workflow = self.write_workflow(
            self.safe_workflow().replace(
                "- uses: actions/checkout@" + "a" * 40,
                '- "uses": owner/action@main',
            )
        )
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_workflow(workflow)

    def test_persistent_checkout_credentials_are_rejected(self) -> None:
        workflow = self.write_workflow(
            self.safe_workflow().replace("persist-credentials: false", "persist-credentials: true")
        )
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_workflow(workflow)


class ComposeSecretBindingTests(unittest.TestCase):
    def test_complete_file_bindings_pass(self) -> None:
        warnings = compose_validator.validate_backend(backend_document())
        self.assertEqual(
            warnings,
            ["WORKER_HEALTHCHECK=UNVERIFIED", "SCHEDULER_HEALTHCHECK=UNVERIFIED"],
        )

    def test_mounted_but_unused_application_secrets_fail(self) -> None:
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_backend(backend_document(environment=False))

    def test_long_form_secret_with_wrong_target_fails(self) -> None:
        backend = backend_document()
        services = backend["services"]
        assert isinstance(services, dict)
        api = services["api"]
        assert isinstance(api, dict)
        api["secrets"] = [
            {"source": "breero_database_url", "target": "wrong_database_url"},
            "breero_redis_url",
            "breero_jwt_access_secret",
            "breero_jwt_refresh_secret",
        ]
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_backend(backend)

    def test_postgres_secret_with_wrong_target_fails(self) -> None:
        backend = backend_document()
        services = backend["services"]
        assert isinstance(services, dict)
        postgres = services["postgres"]
        assert isinstance(postgres, dict)
        postgres["secrets"] = [
            {"source": "breero_postgres_password", "target": "not_the_password"}
        ]
        with self.assertRaises(compose_validator.ValidationError):
            compose_validator.validate_backend(backend)


class RuntimeEvidenceTests(unittest.TestCase):
    def runtime_args(self) -> argparse.Namespace:
        return argparse.Namespace(
            expected_api_image=API_IMAGE,
            expected_frontend_image=WEB_IMAGE,
            expected_private_network="breero_private_runtime",
            expected_backend_edge_network="breero_edge_runtime",
            expected_frontend_edge_network="breero_frontend_runtime",
            expected_web_host="breero.com",
            expected_api_host="api.breero.com",
            expected_web_upstream="web:3000",
            expected_api_upstream="api:8000",
        )

    def prepare_secret_files(self, backend: dict[str, object]) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(directory))
        secrets = backend["secrets"]
        assert isinstance(secrets, dict)
        for name, definition in secrets.items():
            path = directory / str(name)
            path.write_text("placeholder\n", encoding="utf-8")
            path.chmod(0o600)
            assert isinstance(definition, dict)
            definition["file"] = str(path)

    def test_network_and_secret_bindings_pass(self) -> None:
        backend = backend_document()
        frontend = frontend_document()
        self.prepare_secret_files(backend)
        paths = runtime_validator.validate_compose_bindings(
            backend,
            frontend,
            self.runtime_args(),
        )
        self.assertGreater(len(paths), 0)

    def test_unmounted_postgres_password_consumer_fails(self) -> None:
        for password_path in (None, "/run/secrets/unmounted_password"):
            with self.subTest(password_path=password_path):
                backend = backend_document()
                self.prepare_secret_files(backend)
                backend["services"]["postgres"]["environment"] = (
                    {} if password_path is None else {"POSTGRES_PASSWORD_FILE": password_path}
                )
                with self.assertRaises(runtime_validator.EvidenceError):
                    runtime_validator.validate_compose_bindings(
                        backend, frontend_document(), self.runtime_args()
                    )

    def test_mutable_data_service_images_fail(self) -> None:
        for service_name in ("postgres", "redis"):
            with self.subTest(service=service_name):
                backend = backend_document()
                self.prepare_secret_files(backend)
                backend["services"][service_name]["image"] = f"example/{service_name}:latest"
                with self.assertRaises(runtime_validator.EvidenceError):
                    runtime_validator.validate_compose_bindings(
                        backend, frontend_document(), self.runtime_args()
                    )

    def test_runtime_secret_mounts_require_approved_source_and_target(self) -> None:
        for service_name, source in (
            ("api", "breero_database_url"),
            ("worker", "breero_redis_url"),
            ("scheduler", "breero_jwt_access_secret"),
            ("migrate", "breero_jwt_refresh_secret"),
            ("postgres", "breero_postgres_password"),
            ("redis", "breero_redis_acl"),
        ):
            for defect in ("missing", "wrong-source", "wrong-target", "duplicate-target"):
                with self.subTest(service=service_name, defect=defect):
                    backend = backend_document()
                    self.prepare_secret_files(backend)
                    mounts = backend["services"][service_name]["secrets"]
                    mounts.remove(source)
                    wrong_source = (
                        "breero_redis_acl" if source != "breero_redis_acl" else "breero_postgres_password"
                    )
                    if defect == "wrong-source":
                        mounts.append({"source": wrong_source, "target": source})
                    elif defect == "wrong-target":
                        mounts.append({"source": source, "target": "unconsumed_secret"})
                    elif defect == "duplicate-target":
                        mounts.extend([
                            source,
                            {"source": wrong_source, "target": source},
                        ])
                    with self.assertRaises(runtime_validator.EvidenceError):
                        runtime_validator.validate_compose_bindings(
                            backend, frontend_document(), self.runtime_args()
                        )

    def test_application_consumers_cannot_use_another_verified_secret(self) -> None:
        backend = backend_document()
        self.prepare_secret_files(backend)
        backend["services"]["api"]["environment"]["DATABASE_URL_FILE"] = (
            "/run/secrets/breero_redis_url"
        )
        with self.assertRaises(runtime_validator.EvidenceError):
            runtime_validator.validate_compose_bindings(
                backend, frontend_document(), self.runtime_args()
            )

    def test_redis_must_consume_its_verified_acl_mount(self) -> None:
        for command in (
            ["redis-server"],
            ["redis-server", "--aclfile", "/run/secrets/unmounted_acl"],
            ["redis-server", "--logfile", "/run/secrets/breero_redis_acl"],
        ):
            with self.subTest(command=command):
                backend = backend_document()
                self.prepare_secret_files(backend)
                backend["services"]["redis"]["command"] = command
                with self.assertRaises(runtime_validator.EvidenceError):
                    runtime_validator.validate_compose_bindings(
                        backend, frontend_document(), self.runtime_args()
                    )

    def test_long_form_runtime_secret_bindings_pass(self) -> None:
        for absolute_target in (False, True):
            with self.subTest(absolute_target=absolute_target):
                backend = backend_document()
                self.prepare_secret_files(backend)
                for service in backend["services"].values():
                    service["secrets"] = [
                        {
                            "source": source,
                            "target": "/run/secrets/" + source if absolute_target else source,
                        }
                        for source in service["secrets"]
                    ]
                self.assertEqual(
                    len(runtime_validator.validate_compose_bindings(
                        backend, frontend_document(), self.runtime_args()
                    )),
                    6,
                )

    def test_unbound_runtime_network_name_fails(self) -> None:
        backend = backend_document()
        frontend = frontend_document()
        self.prepare_secret_files(backend)
        args = self.runtime_args()
        args.expected_backend_edge_network = "other_edge"
        with self.assertRaises(runtime_validator.EvidenceError):
            runtime_validator.validate_compose_bindings(backend, frontend, args)

    def test_reversed_caddy_routes_fail(self) -> None:
        with self.assertRaises(runtime_validator.EvidenceError):
            runtime_validator.validate_caddy_routes(caddy_document(reverse=True), self.runtime_args())

    def test_contradictory_nested_host_matchers_fail(self) -> None:
        with self.assertRaises(runtime_validator.EvidenceError):
            runtime_validator.validate_caddy_routes(
                contradictory_caddy_document(),
                self.runtime_args(),
            )

    def test_expected_caddy_route_associations_pass(self) -> None:
        runtime_validator.validate_caddy_routes(caddy_document(), self.runtime_args())


if __name__ == "__main__":
    unittest.main(verbosity=2)
