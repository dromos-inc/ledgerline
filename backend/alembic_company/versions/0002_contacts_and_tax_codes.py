"""contacts and tax codes — Phase 2 S1 prerequisite

Revision ID: 0002_contacts_and_tax_codes
Revises: 0001_initial_company
Create Date: 2026-04-19 00:00:00

Adds the schema Phase 2 AR/AP needs, without yet shipping the domain
logic that consumes it. After this migration the per-company database
gains:

- ``accounts.role`` nullable VARCHAR(32) column with a partial unique
  index (one account per role). Used to flag the AR control, AP control,
  and default sales-tax-payable accounts.
- ``customers`` table: billable contacts (name, email, default income
  account, default tax code, default terms).
- ``vendors`` table: bill recipients (name, email, default expense
  account, default terms, 1099 flag).
- ``tax_codes`` table: tax rates stored as basis points (e.g. 625 for
  6.25%). Each tax code points at a payable account.
- Three integrity triggers:

  * ``trg_accounts_control_no_delete`` rejects DELETE on any account
    whose ``role`` is one of the reserved control roles.
  * ``trg_accounts_control_no_direct_je`` rejects INSERT on
    ``journal_lines`` when the target account has a reserved role and
    the owning journal entry's ``source_type`` is ``'manual'``. The sub-
    ledger (invoices, bills, payments) posts through different source
    types, so those lines land fine; only hand-written JEs are blocked.
  * ``trg_tax_codes_rate_immutable`` guards rate mutations, but the
    body only has meaning once the ``invoice_lines`` table exists.
    Migration 0003 wires that side in; for now the trigger enforces
    only ``rate_bps >= 0``.

No seed data runs here. Migration 0003 will attach roles to existing
control accounts and ensure brand-new companies get the right markers
via the seed templates.

Follows the Phase 1 trigger-atomicity pattern: each trigger executes
via ``op.execute(sa.text(...))`` inside Alembic's transaction, so the
whole migration rolls back cleanly on failure.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_contacts_and_tax_codes"
down_revision: Union[str, None] = "0001_initial_company"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Integrity triggers. See module docstring for semantics. Same single-SQL-
# statement-per-entry contract as migration 0001.
# ---------------------------------------------------------------------------

TRIGGERS: tuple[str, ...] = (
    """
    CREATE TRIGGER IF NOT EXISTS trg_accounts_control_no_delete
    BEFORE DELETE ON accounts
    FOR EACH ROW
    WHEN OLD.role IN ('ar_control', 'ap_control', 'sales_tax_default')
    BEGIN
        SELECT RAISE(ABORT, 'control accounts cannot be deleted');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_accounts_control_no_direct_je
    BEFORE INSERT ON journal_lines
    FOR EACH ROW
    WHEN (
        SELECT role FROM accounts WHERE id = NEW.account_id
    ) IN ('ar_control', 'ap_control', 'sales_tax_default')
      AND (
        SELECT source_type FROM journal_entries
        WHERE id = NEW.journal_entry_id
    ) = 'manual'
    BEGIN
        SELECT RAISE(ABORT, 'direct manual posting to a control account is not allowed; post through the sub-ledger (invoice, bill, or payment)');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_tax_codes_rate_non_negative
    BEFORE UPDATE OF rate_bps ON tax_codes
    FOR EACH ROW
    WHEN NEW.rate_bps < 0 OR NEW.rate_bps >= 10000
    BEGIN
        SELECT RAISE(ABORT, 'tax rate must be between 0 and 10000 basis points');
    END
    """,
)


TRIGGER_NAMES: list[str] = [
    "trg_accounts_control_no_delete",
    "trg_accounts_control_no_direct_je",
    "trg_tax_codes_rate_non_negative",
]


def _apply_triggers() -> None:
    """Run each CREATE TRIGGER through Alembic's managed transaction."""
    for trigger_sql in TRIGGERS:
        op.execute(sa.text(trigger_sql.strip()))


def upgrade() -> None:
    # --- accounts.role column ----------------------------------------------
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=32), nullable=True),
        )
    # Partial unique index: each reserved role appears on at most one
    # account. NULLs are allowed in unlimited quantity (the vast majority
    # of accounts have no role).
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_accounts_role "
            "ON accounts(role) WHERE role IS NOT NULL"
        )
    )

    # --- tax_codes ---------------------------------------------------------
    # Created first so customers can reference it below.
    op.create_table(
        "tax_codes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("rate_bps", sa.Integer, nullable=False),
        sa.Column(
            "payable_account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint("code", name="uq_tax_codes_code"),
        sa.CheckConstraint(
            "rate_bps >= 0 AND rate_bps < 10000",
            name="ck_tax_codes_rate_valid",
        ),
    )

    # --- customers ---------------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("tax_id", sa.String(length=64), nullable=True),
        sa.Column("billing_address", sa.String(length=512), nullable=True),
        sa.Column("shipping_address", sa.String(length=512), nullable=True),
        sa.Column(
            "default_terms",
            sa.String(length=32),
            nullable=False,
            server_default="net_30",
        ),
        sa.Column(
            "default_income_account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "default_tax_code_id",
            sa.Integer,
            sa.ForeignKey("tax_codes.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint("code", name="uq_customers_code"),
        sa.CheckConstraint(
            "default_terms IN "
            "('net_15','net_30','net_60','due_on_receipt','custom')",
            name="ck_customers_terms_valid",
        ),
    )
    op.create_index("ix_customers_is_active", "customers", ["is_active"])

    # --- vendors -----------------------------------------------------------
    op.create_table(
        "vendors",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("tax_id", sa.String(length=64), nullable=True),
        sa.Column("billing_address", sa.String(length=512), nullable=True),
        sa.Column(
            "default_terms",
            sa.String(length=32),
            nullable=False,
            server_default="net_30",
        ),
        sa.Column(
            "default_expense_account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "is_1099",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint("code", name="uq_vendors_code"),
        sa.CheckConstraint(
            "default_terms IN "
            "('net_15','net_30','net_60','due_on_receipt','custom')",
            name="ck_vendors_terms_valid",
        ),
    )
    op.create_index("ix_vendors_is_active", "vendors", ["is_active"])

    # --- triggers ----------------------------------------------------------
    _apply_triggers()


def downgrade() -> None:
    for name in TRIGGER_NAMES:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.drop_index("ix_vendors_is_active", table_name="vendors")
    op.drop_table("vendors")
    op.drop_index("ix_customers_is_active", table_name="customers")
    op.drop_table("customers")
    op.drop_table("tax_codes")
    op.execute("DROP INDEX IF EXISTS uq_accounts_role")
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("role")
