"""Schema bootstrapping.

Phase 1 uses SQLAlchemy's ``create_all`` to materialize tables on first
use. Once the schema freezes at Phase 1 exit (PRD §15 Q10), this module
will be replaced with Alembic migrations. The public functions below
(``ensure_registry_schema``, ``ensure_company_schema``) stay stable so
callers don't change.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, text

from app.db.base import CompanyBase, RegistryBase

logger = logging.getLogger(__name__)

# Bumped when a schema change lands.
SCHEMA_VERSION = 1


def _record_schema_version(engine: Engine, version: int) -> None:
    """Write the current schema version into a small metadata table."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                "  id INTEGER PRIMARY KEY CHECK (id = 1),"
                "  version INTEGER NOT NULL,"
                "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
                ")"
            )
        )
        conn.execute(
            text(
                "INSERT INTO schema_version (id, version) VALUES (1, :v) "
                "ON CONFLICT (id) DO UPDATE SET version = excluded.version, "
                "  applied_at = datetime('now')"
            ),
            {"v": version},
        )


def ensure_registry_schema(engine: Engine) -> None:
    """Create all registry tables if not already present."""
    # Importing here avoids circular imports: models pull Base which pulls
    # from app.db.__init__ which pulls from this module.
    from app.models import registry as _registry_models  # noqa: F401

    RegistryBase.metadata.create_all(engine)
    _record_schema_version(engine, SCHEMA_VERSION)
    logger.debug("Registry schema ensured at version %s", SCHEMA_VERSION)


def ensure_company_schema(engine: Engine) -> None:
    """Create all company-scoped tables if not already present."""
    # Import all company-scoped models so Base.metadata knows about them.
    # Each import triggers table registration as a side effect.
    # NOTE: every new model file must be imported here.
    from app.models import account as _account  # noqa: F401
    from app.models import audit as _audit  # noqa: F401
    from app.models import journal as _journal  # noqa: F401

    CompanyBase.metadata.create_all(engine)
    _record_schema_version(engine, SCHEMA_VERSION)
    logger.debug("Company schema ensured at version %s", SCHEMA_VERSION)
