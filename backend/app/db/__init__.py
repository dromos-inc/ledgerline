"""Database layer.

Two distinct SQLite databases are managed by this module:

1. The *registry* database holds metadata about which companies exist, their
   file paths, fiscal year info, and any global application settings.
2. Each *company* database holds the full set of accounting records for a
   single business: chart of accounts, journal entries, audit log, etc.

The split keeps user books portable: a single company .db file can be copied,
emailed, backed up, or moved to another machine and opened from there. The
registry never leaves the host that owns it.
"""

from app.db.base import Base, CompanyBase, RegistryBase
from app.db.engines import (
    company_engine,
    dispose_company_engines,
    registry_engine,
)
from app.db.session import company_session, registry_session

__all__ = [
    "Base",
    "CompanyBase",
    "RegistryBase",
    "company_engine",
    "company_session",
    "dispose_company_engines",
    "registry_engine",
    "registry_session",
]
