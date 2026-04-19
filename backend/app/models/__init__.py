"""ORM models.

Registry models live in ``registry.py`` (one file, rarely changes).
Per-company models live in their own files by domain. Importing any
single per-company model re-exports all of them through this package's
``__init__`` so SQLAlchemy's metadata graph can resolve ForeignKey
references between siblings (e.g. ``customers.default_tax_code_id``
points at ``tax_codes.id``; without both classes on the metadata,
flushing Customer would fail with ``NoReferencedTableError``).
"""

from __future__ import annotations

# Importing each per-company model here guarantees its Table registers
# on CompanyBase.metadata before any ORM operation touches the graph.
# Order doesn't matter for correctness but mirrors the migration order
# for readability.
from app.models import account as _account  # noqa: F401
from app.models import audit as _audit  # noqa: F401
from app.models import contact as _contact  # noqa: F401
from app.models import journal as _journal  # noqa: F401
from app.models import tax_code as _tax_code  # noqa: F401
