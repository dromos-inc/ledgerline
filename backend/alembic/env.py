"""Alembic environment for the registry database.

Used both programmatically (via ``ensure_registry_schema``) and from the
CLI (``alembic --name registry upgrade head``). When invoked
programmatically, the caller passes an open connection via
``config.attributes['connection']``. When invoked from the CLI, we
construct an engine from the running app's ``Settings``.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import Connection

from alembic import context
from app.db.base import RegistryBase

# Ensure every registry model is imported so its table registers on the
# RegistryBase metadata before Alembic inspects it.
from app.models import registry as _registry_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = RegistryBase.metadata


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite needs batch mode for ALTERs
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    existing_connection = config.attributes.get("connection")
    if existing_connection is not None:
        _run_migrations(existing_connection)
        return

    # CLI path: build a fresh engine from the app's settings.
    from app.config import get_settings
    from app.db.engines import registry_engine

    engine = registry_engine(get_settings())
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
