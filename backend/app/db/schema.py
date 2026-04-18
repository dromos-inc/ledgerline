"""Schema bootstrapping via Alembic.

Phase 1 previously used ``create_all`` + a hand-rolled ``schema_version``
table + a loose ``triggers.sql`` loader. This module has been rewritten to
run the committed Alembic migrations instead, satisfying PRD §15 Q10
("every schema change ships with an automated migration script").

Programmatic use is the common case — ``ensure_registry_schema(engine)``
runs the registry migrations against the given engine. ``ensure_company_schema(engine)``
does the same for a per-company file. CLI use is also supported:

.. code-block:: bash

    alembic --name registry upgrade head
    alembic --name company -x company=<id> upgrade head
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine

from alembic import command

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_REGISTRY_SCRIPT_LOCATION = str(_BACKEND_ROOT / "alembic")
_COMPANY_SCRIPT_LOCATION = str(_BACKEND_ROOT / "alembic_company")


def _alembic_config(script_location: str, connection) -> Config:
    """Build an in-memory Alembic Config bound to an existing connection."""
    cfg = Config()
    cfg.set_main_option("script_location", script_location)
    cfg.attributes["connection"] = connection
    return cfg


def _upgrade(engine: Engine, script_location: str) -> None:
    """Run ``upgrade head`` against ``engine`` using the given script tree.

    Alembic opens its own transaction; we give it a fresh connection scoped
    to this call so the caller's SQLAlchemy session state isn't polluted.
    """
    with engine.begin() as connection:
        cfg = _alembic_config(script_location, connection)
        command.upgrade(cfg, "head")


def ensure_registry_schema(engine: Engine) -> None:
    """Run the registry migrations to head."""
    _upgrade(engine, _REGISTRY_SCRIPT_LOCATION)
    logger.debug("Registry schema upgraded via Alembic")


def ensure_company_schema(engine: Engine) -> None:
    """Run the per-company migrations to head."""
    _upgrade(engine, _COMPANY_SCRIPT_LOCATION)
    logger.debug("Company schema upgraded via Alembic")
