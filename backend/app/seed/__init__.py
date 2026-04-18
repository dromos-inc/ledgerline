"""Seed data: default chart-of-accounts templates.

PRD §10.1 calls for templates per business type. MVP ships three:
- Schedule C (service business): minimal CoA for a sole proprietor
- Schedule C (retail): adds inventory, COGS, sales tax
- S-corp (general): common stock, APIC, shareholder distributions,
  retained earnings per PRD §15 Q5.

More templates can be added in `app/seed/templates.py` without touching
the service or API layers.
"""

from app.seed.templates import TEMPLATES, Template, get_template

__all__ = ["TEMPLATES", "Template", "get_template"]
