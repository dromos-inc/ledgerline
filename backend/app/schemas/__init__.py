"""Pydantic schemas for request and response payloads.

Models map to DB rows one-for-one where possible; we do not reuse SQLAlchemy
models at the API boundary. Keeping them separate lets us version the API
independently of the schema.
"""
