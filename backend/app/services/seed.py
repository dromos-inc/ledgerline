"""Apply a chart-of-accounts template to a freshly-created company.

Phase 2 addition: when we seed an account whose code matches a known
control-account slot, we also set ``role`` on that row. This flags the
account for the trigger that forbids direct manual journal entries
against it, and for the future reconciliation-canary report.

The mapping is hardcoded because the templates themselves are static
Python structs — seed accounts don't carry a ``role`` field and we
don't want to extend every template entry just to paint three cells.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit import AuditAction
from app.seed import get_template
from app.services.audit import record_audit

# Maps the conventional numeric code in every Phase 1 seed template to
# the control role it should carry after Phase 2 lands. Accounts
# outside this map keep role=NULL.
_ROLE_BY_CODE: dict[str, str] = {
    "1200": "ar_control",
    "2000": "ap_control",
    "2200": "sales_tax_default",
}


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
            role=_ROLE_BY_CODE.get(seed_account.code),
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
