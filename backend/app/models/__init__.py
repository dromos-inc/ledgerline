"""ORM models.

Registry models live in ``registry.py`` (one file, rarely changes).
Per-company models live in their own files by domain. Each per-company
model must be imported inside
``app.db.schema.ensure_company_schema`` for ``create_all`` to see it.
"""
