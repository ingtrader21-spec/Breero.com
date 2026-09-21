import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.db.base import Base
from app.domains.administration import models as administration_models  # noqa: F401
from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.booking import capacity_models  # noqa: F401
from app.domains.booking import models as booking_models  # noqa: F401
from app.domains.booking_intents import models as booking_intent_models  # noqa: F401
from app.domains.catalog import models as catalog_models  # noqa: F401
from app.domains.common import outbox as outbox_models  # noqa: F401
from app.domains.compliance import models as compliance_models  # noqa: F401
from app.domains.dispatch import models as dispatch_models  # noqa: F401
from app.domains.finance import models as finance_models  # noqa: F401
from app.domains.geography import models as geography_models  # noqa: F401
from app.domains.jobs import models as job_models  # noqa: F401
from app.domains.payments import models as payment_models  # noqa: F401
from app.domains.professional_leads import models as professional_lead_models  # noqa: F401
from app.domains.provider_catalog import models as provider_catalog_models  # noqa: F401
from app.domains.public_submissions import models as public_submission_models  # noqa: F401
from app.domains.workforce import models as workforce_models  # noqa: F401
from app.domains.workforce import provider_models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
extension_owned_tables = {"spatial_ref_sys"}


def include_object(object_, name, type_, reflected, compare_to):
    """Route semantic constraint/index drift to the name-independent contract checker.

    Alembic remains authoritative for tables, columns, types, nullability, and defaults.
    Tables PostgreSQL records as extension-owned are excluded; application tables are not.
    """
    if type_ == "table" and reflected and name in extension_owned_tables:
        return False
    if type_ in {"index", "unique_constraint", "foreign_key_constraint", "check_constraint"}:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    extension_owned_tables.update(
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
    # End the catalog-read transaction before Alembic owns the migration transaction.
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
