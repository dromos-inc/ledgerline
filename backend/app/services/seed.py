"""Apply a chart-of-accounts template to a freshly-created company."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit import AuditAction
from app.seed import get_template
from app.services.audit import record_audit


def apply_template(
    session: Session,
    template_key: str,
    *,
    actor: str | None = None,
) -> int:
    """Seed a company's CoA from a named template. Returns count inserted."""
    template = get_template(template_key)
    inserted = 0
    for seed_account in template.accounts:
        account = Account(
            code=seed_account.code,
            name=seed_account.name,
            type=seed_account.type,
            subtype=seed_account.subtype,
            description=seed_account.description,
        )
        session.add(account)
        session.flush()
        inserted += 1
    session.flush()
    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="coa_template",
        entity_id=template.key,
        after={"inserted": inserted, "label": template.label},
        actor=actor,
        note=f"applied template {template.key!r}",
    )
    return inserted
