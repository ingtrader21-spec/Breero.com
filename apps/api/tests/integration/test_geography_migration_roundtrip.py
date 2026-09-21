import os
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="geography migration round trip requires PostgreSQL",
)


def _alembic(database_url: str, *arguments: str) -> None:
    environment = {**os.environ, "DATABASE_URL": database_url}
    result = subprocess.run(
        ["alembic", *arguments],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise AssertionError(
            f"alembic {' '.join(arguments)} failed\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def test_geography_migration_downgrade_and_reupgrade() -> None:
    source = make_url(os.environ["DATABASE_URL"])
    database_name = f"breero_geo_{uuid.uuid4().hex[:12]}"
    admin_kwargs = {
        "host": source.host or "localhost",
        "port": source.port or 5432,
        "user": source.username,
        "password": source.password,
        "dbname": "postgres",
    }
    target_url = source.set(database=database_name).render_as_string(
        hide_password=False
    )

    with psycopg.connect(**admin_kwargs, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(database_name)
            )
        )
    try:
        _alembic(target_url, "upgrade", "029_booking_intents")
        _alembic(target_url, "upgrade", "030_geography_service_zones")
        with psycopg.connect(
            **{**admin_kwargs, "dbname": database_name}
        ) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    """
                )
            }
            assert {
                "service_zone_services",
                "service_area_postal_codes",
                "postal_code_imports",
            } <= tables
            columns = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'addresses'
                    """
                )
            }
            assert {
                "line2",
                "county",
                "postal_code_plus4",
                "validation_status",
                "provider_reference",
                "validation_confidence",
            } <= columns

        _alembic(target_url, "downgrade", "029_booking_intents")
        with psycopg.connect(
            **{**admin_kwargs, "dbname": database_name}
        ) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    """
                )
            }
            assert "service_zone_services" not in tables
            assert "service_area_postal_codes" not in tables
            assert "postal_code_imports" not in tables
            # Migration 018 owns the live-runtime service-zone postal table;
            # downgrading only migration 030 must preserve earlier authority.
            assert "service_zone_postal_codes" in tables
            address_columns = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'addresses'
                    """
                )
            }
            assert "postal_code_plus4" not in address_columns

        _alembic(target_url, "upgrade", "030_geography_service_zones")
        with psycopg.connect(
            **{**admin_kwargs, "dbname": database_name}
        ) as connection:
            revision = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
            assert revision and revision[0] == "030_geography_service_zones"
    finally:
        with psycopg.connect(**admin_kwargs, autocommit=True) as admin:
            admin.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s
                  AND pid <> pg_backend_pid()
                """,
                (database_name,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(database_name)
                )
            )
