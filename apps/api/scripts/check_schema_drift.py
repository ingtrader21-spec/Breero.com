"""Fail when application tables/columns/nullability differ from SQLAlchemy metadata.

Supplementary operational indexes and PostGIS-owned objects are intentionally allowed;
they are versioned migrations but are not destructive model drift.
"""

import asyncio

from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.domains.administration import models as _administration  # noqa: F401
from app.domains.auth import models as _auth  # noqa: F401
from app.domains.booking import capacity_models as _booking_capacity  # noqa: F401
from app.domains.booking import models as _booking  # noqa: F401
from app.domains.booking_intents import models as _booking_intents  # noqa: F401
from app.domains.catalog import models as _catalog  # noqa: F401
from app.domains.common import outbox as _outbox  # noqa: F401
from app.domains.compliance import models as _compliance  # noqa: F401
from app.domains.dispatch import models as _dispatch  # noqa: F401
from app.domains.finance import models as _finance  # noqa: F401
from app.domains.geography import models as _geography  # noqa: F401
from app.domains.jobs import models as _jobs  # noqa: F401
from app.domains.payments import models as _payments  # noqa: F401
from app.domains.professional_leads import models as _professional_leads  # noqa: F401
from app.domains.provider_catalog import models as _provider_catalog  # noqa: F401
from app.domains.public_submissions import models as _public_submissions  # noqa: F401
from app.domains.workforce import models as _workforce  # noqa: F401
from app.domains.workforce import provider_models as _workforce_provider  # noqa: F401


def compare(connection) -> list[str]:
    inspector = inspect(connection)
    extension_owned = set(
        connection.execute(
            text(
                """SELECT c.relname
                FROM pg_depend d
                JOIN pg_class c ON c.oid = d.objid
                WHERE d.refclassid = 'pg_extension'::regclass
                  AND d.classid = 'pg_class'::regclass
                  AND d.deptype = 'e'"""
            )
        ).scalars()
    )
    database_tables = set(inspector.get_table_names()) - extension_owned - {
        "alembic_version"
    }
    model_tables = set(Base.metadata.tables)
    errors = [
        f"unexpected table: {name}"
        for name in sorted(database_tables - model_tables)
    ]
    errors += [
        f"missing table: {name}"
        for name in sorted(model_tables - database_tables)
    ]
    for table_name in sorted(model_tables & database_tables):
        expected = Base.metadata.tables[table_name]
        actual = {
            column["name"]: column
            for column in inspector.get_columns(table_name)
        }
        expected_names = set(expected.columns.keys())
        errors += [
            f"{table_name}: unexpected column {name}"
            for name in sorted(set(actual) - expected_names)
        ]
        errors += [
            f"{table_name}: missing column {name}"
            for name in sorted(expected_names - set(actual))
        ]
        for name in sorted(expected_names & set(actual)):
            if bool(expected.columns[name].nullable) != bool(
                actual[name]["nullable"]
            ):
                errors.append(f"{table_name}.{name}: nullability differs")
        expected_unique = {
            tuple(sorted(constraint.columns.keys()))
            for constraint in expected.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        actual_unique = {
            tuple(sorted(item["column_names"]))
            for item in inspector.get_unique_constraints(table_name)
        }
        actual_unique |= {
            tuple(sorted(item["column_names"]))
            for item in inspector.get_indexes(table_name)
            if item.get("unique")
        }
        if not expected_unique.issubset(actual_unique):
            errors.append(
                f"{table_name}: missing unique sets "
                f"{sorted(expected_unique - actual_unique)}"
            )
        expected_fks = {
            (
                tuple(constraint.column_keys),
                tuple(
                    element.target_fullname
                    for element in constraint.elements
                ),
                (constraint.ondelete or "").upper(),
            )
            for constraint in expected.foreign_key_constraints
        }
        actual_fks = {
            (
                tuple(item["constrained_columns"]),
                tuple(
                    f"{item['referred_table']}.{column}"
                    for column in item["referred_columns"]
                ),
                (item.get("options", {}).get("ondelete") or "").upper(),
            )
            for item in inspector.get_foreign_keys(table_name)
        }
        if expected_fks != actual_fks:
            errors.append(f"{table_name}: foreign-key semantics differ")
    return errors


async def main() -> None:
    async with engine.connect() as connection:
        errors = await connection.run_sync(compare)
    await engine.dispose()
    if errors:
        raise SystemExit("Schema drift detected:\n" + "\n".join(errors))
    print("No destructive schema drift detected")


if __name__ == "__main__":
    asyncio.run(main())
