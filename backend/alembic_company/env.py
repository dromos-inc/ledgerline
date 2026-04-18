"""Alembic environment for per-company databases.

A Ledgerline instance has N company databases, one SQLite file per
company. Each file runs through the same migration tree and ends up at
the same schema version.

Programmatic path (most common): ``ensure_company_schema(engine)`` opens a
connection to a specific company file and hands it to Alembic via
``config.attributes['connection']``.

CLI path (rare, for out-of-band schema work):
``alembic --name company -x company=<id> upgrade head``. The ``-x
company=<id>`` tells env.py which file to migrate.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import Connection

from alembic import context
from app.db.base import CompanyBase

# Import every per-company model so its Table registers on CompanyBase.metadata.
from app.models import account as _account  # noqa: F401
from app.models import audit as _audit  # noqa: F401
from app.models import journal as _journal  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = CompanyBase.metadata


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    existing_connection = config.attributes.get("connection")
    if existing_connection is not None:
        _run_migrations(existing_connection)
        return

    # CLI path: resolve company id from -x args.
    x_args = context.get_x_argument(as_dictionary=True)
    company_id = x_args.get("company")
    if not company_id:
        raise RuntimeError(
            "company DB migrations require a company id. "
            "Pass `-x company=<id>` to the alembic CLI."
        )

    from app.config import get_settings
    from app.db.engines import company_engine

    engine = company_engine(get_settings(), company_id)
    with engine.connect() as connection:
        _run_migrations(connection)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
