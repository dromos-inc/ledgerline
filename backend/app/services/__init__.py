"""Business-logic services.

Routers are thin: they parse input, call a service function, and shape
the response. Services own the actual domain operations and write to
the audit log where appropriate.
"""
