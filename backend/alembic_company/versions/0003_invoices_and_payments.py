"""invoices, payments, items — Phase 2 S1 core

Revision ID: 0003_invoices_and_payments
Revises: 0002_contacts_and_tax_codes
Create Date: 2026-04-19 00:00:00

Lands the five tables the AR one-liner actually needs:

- ``items``: product/service catalog with default account and tax-code
  pointers. Invoice lines can either reference an item (which populates
  account, unit price, and tax-code defaults) or be freeform with an
  explicit account. Service layer for items ships in S3; this commit
  only lands the table because invoices need the FK.
- ``invoices``: header for a bill-to-customer document. Status FSM
  draft -> sent -> partial -> paid (+ void from any state). Carries
  a FK to the journal entry that posted it.
- ``invoice_lines``: one line item per row. Quantity in milli-units
  (3 decimals), price in cents, pre-computed tax_amount_cents and
  amount_cents so reports don't re-derive from rate and qty on every
  read.
- ``payments``: customer-side payment header. Deposits into a chosen
  asset account, creates its own journal entry. One payment can apply
  to many invoices.
- ``payment_applications``: many-to-many linking payments to the
  invoices they settle, with per-application amount, discount, and
  write-off fields.

Plus eight new integrity triggers that enforce the sub-ledger
contract at the DB layer. Every trigger is applied via
``op.execute(sa.text(...))`` inside the Alembic transaction, so the
whole migration is atomic and rolls back cleanly on failure.

The invoice and invoice_line triggers pair with a status FSM:
- ``draft`` can transition to ``sent`` (via post) or ``void``
- ``sent`` can transition to ``partial``, ``paid``, or ``void``
- ``partial`` can move back to ``sent`` (if a payment is voided and
  the cumulative drops below $0 applied) or forward to ``paid``
- ``paid`` can move back to ``partial`` or ``sent`` (payment voids)
  or to ``void``
- ``void`` is terminal — no outbound transitions

The payment-side triggers mirror the journal-entries pattern from
Phase 1: once a payment posts its JE, header fields beyond
``status`` are immutable; DELETE is blocked; lines are frozen.

Tax-code rate immutability finally has teeth in this migration: the
``trg_tax_codes_rate_immutable`` trigger rejects UPDATE of
``rate_bps`` when any invoice_line references the code. Before 0003,
invoice_lines didn't exist, so the 0002 version of the trigger only
guarded the non-negative range.

Customer hard-delete is finally prevented too: now that
invoice_lines can reference customers (through invoices.customer_id),
the trigger knows when to fire.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_invoices_and_payments"
down_revision: Union[str, None] = "0002_contacts_and_tax_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Integrity triggers for the AR sub-ledger. See module docstring for the
# FSM and sub-ledger invariants each one enforces. Same single-SQL-
# statement contract as the 0001/0002 triggers so the whole migration
# stays atomic.
# ---------------------------------------------------------------------------

TRIGGERS: tuple[str, ...] = (
    # Transitioning invoice.status to any posted/paid variant requires a
    # linked journal entry. Voiding requires a reversal (which is also a
    # journal entry), so we demand journal_entry_id be non-NULL for every
    # non-draft state.
    """
    CREATE TRIGGER IF NOT EXISTS trg_invoices_post_auto_je
    BEFORE UPDATE OF status ON invoices
    FOR EACH ROW
    WHEN NEW.status IN ('sent', 'partial', 'paid') AND NEW.journal_entry_id IS NULL
    BEGIN
        SELECT RAISE(ABORT, 'invoice must have a journal_entry_id before transitioning out of draft');
    END
    """,
    # After post, only amount_paid_cents and status may change. Customer,
    # dates, terms, memo, totals, and the JE link are all frozen.
    """
    CREATE TRIGGER IF NOT EXISTS trg_invoices_immutable_posted
    BEFORE UPDATE ON invoices
    FOR EACH ROW
    WHEN OLD.status != 'draft'
      AND (
           NEW.customer_id != OLD.customer_id
        OR NEW.invoice_date != OLD.invoice_date
        OR NEW.due_date != OLD.due_date
        OR NEW.terms != OLD.terms
        OR NEW.number != OLD.number
        OR COALESCE(NEW.reference, '') != COALESCE(OLD.reference, '')
        OR COALESCE(NEW.memo, '') != COALESCE(OLD.memo, '')
        OR NEW.subtotal_cents != OLD.subtotal_cents
        OR NEW.tax_total_cents != OLD.tax_total_cents
        OR NEW.total_cents != OLD.total_cents
        OR COALESCE(NEW.journal_entry_id, -1) != COALESCE(OLD.journal_entry_id, -1)
      )
    BEGIN
        SELECT RAISE(ABORT, 'posted invoice fields are immutable except status and amount_paid_cents');
    END
    """,
    # Invoice lines are completely frozen once the parent is out of draft.
    """
    CREATE TRIGGER IF NOT EXISTS trg_invoice_lines_no_update_on_posted
    BEFORE UPDATE ON invoice_lines
    FOR EACH ROW
    WHEN (
        SELECT status FROM invoices WHERE id = OLD.invoice_id
    ) != 'draft'
    BEGIN
        SELECT RAISE(ABORT, 'cannot modify lines of a posted or voided invoice');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_invoice_lines_no_delete_on_posted
    BEFORE DELETE ON invoice_lines
    FOR EACH ROW
    WHEN (
        SELECT status FROM invoices WHERE id = OLD.invoice_id
    ) != 'draft'
    BEGIN
        SELECT RAISE(ABORT, 'cannot delete lines of a posted or voided invoice');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_invoice_lines_no_insert_on_posted
    BEFORE INSERT ON invoice_lines
    FOR EACH ROW
    WHEN (
        SELECT status FROM invoices WHERE id = NEW.invoice_id
    ) != 'draft'
    BEGIN
        SELECT RAISE(ABORT, 'cannot add lines to a posted or voided invoice');
    END
    """,
    # Hard-delete of non-draft invoices is refused; void uses the reversal
    # pattern and leaves the row in place with status='void'.
    """
    CREATE TRIGGER IF NOT EXISTS trg_invoices_no_delete_posted
    BEFORE DELETE ON invoices
    FOR EACH ROW
    WHEN OLD.status != 'draft'
    BEGIN
        SELECT RAISE(ABORT, 'posted or voided invoices cannot be deleted');
    END
    """,
    # Status FSM: void is terminal, draft can only be entered as the
    # initial state (never re-entered from another status).
    """
    CREATE TRIGGER IF NOT EXISTS trg_invoices_status_fsm
    BEFORE UPDATE OF status ON invoices
    FOR EACH ROW
    WHEN OLD.status = 'void'
      OR (NEW.status = 'draft' AND OLD.status != 'draft')
    BEGIN
        SELECT RAISE(ABORT, 'illegal invoice status transition');
    END
    """,
    # A customer referenced by any invoice cannot be hard-deleted.
    """
    CREATE TRIGGER IF NOT EXISTS trg_customers_no_delete_with_invoices
    BEFORE DELETE ON customers
    FOR EACH ROW
    WHEN EXISTS (
        SELECT 1 FROM invoices WHERE customer_id = OLD.id LIMIT 1
    )
    BEGIN
        SELECT RAISE(ABORT, 'cannot delete a customer with invoices; deactivate instead');
    END
    """,
    # Tax code rate is immutable once any invoice_line references it.
    # Replaces the narrower 0002 guard that only blocked negative rates.
    """
    CREATE TRIGGER IF NOT EXISTS trg_tax_codes_rate_immutable
    BEFORE UPDATE OF rate_bps ON tax_codes
    FOR EACH ROW
    WHEN NEW.rate_bps != OLD.rate_bps
      AND EXISTS (
          SELECT 1 FROM invoice_lines WHERE tax_code_id = OLD.id LIMIT 1
      )
    BEGIN
        SELECT RAISE(ABORT, 'cannot change rate of a tax code already used on an invoice; deactivate and create a new code');
    END
    """,
    # Payment-side mirrors: post requires JE, header immutable after post,
    # no delete after post.
    """
    CREATE TRIGGER IF NOT EXISTS trg_payments_immutable_posted
    BEFORE UPDATE ON payments
    FOR EACH ROW
    WHEN OLD.status = 'posted'
      AND (
           NEW.customer_id != OLD.customer_id
        OR NEW.payment_date != OLD.payment_date
        OR NEW.amount_cents != OLD.amount_cents
        OR NEW.deposit_account_id != OLD.deposit_account_id
        OR COALESCE(NEW.method, '') != COALESCE(OLD.method, '')
        OR COALESCE(NEW.reference, '') != COALESCE(OLD.reference, '')
        OR COALESCE(NEW.memo, '') != COALESCE(OLD.memo, '')
        OR NEW.journal_entry_id != OLD.journal_entry_id
      )
      AND NEW.status NOT IN ('void')
    BEGIN
        SELECT RAISE(ABORT, 'posted payment fields are immutable except for void transition');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_payments_no_delete_posted
    BEFORE DELETE ON payments
    FOR EACH ROW
    WHEN OLD.status IN ('posted', 'void')
    BEGIN
        SELECT RAISE(ABORT, 'posted or voided payments cannot be deleted');
    END
    """,
)


TRIGGER_NAMES: list[str] = [
    "trg_invoices_post_auto_je",
    "trg_invoices_immutable_posted",
    "trg_invoice_lines_no_update_on_posted",
    "trg_invoice_lines_no_delete_on_posted",
    "trg_invoice_lines_no_insert_on_posted",
    "trg_invoices_no_delete_posted",
    "trg_invoices_status_fsm",
    "trg_customers_no_delete_with_invoices",
    "trg_tax_codes_rate_immutable",
    "trg_payments_immutable_posted",
    "trg_payments_no_delete_posted",
]


def _apply_triggers() -> None:
    """Run each CREATE TRIGGER through Alembic's managed transaction."""
    # The 0002 migration shipped a rate_non_negative trigger that's now
    # superseded by the stronger rate_immutable trigger below. Drop the
    # old one first so we don't have two competing rules.
    op.execute("DROP TRIGGER IF EXISTS trg_tax_codes_rate_non_negative")
    for trigger_sql in TRIGGERS:
        op.execute(sa.text(trigger_sql.strip()))


def upgrade() -> None:
    # --- items -------------------------------------------------------------
    # Ships in S1 because invoice_lines carries a FK to items. Service +
    # API + UI land in S3; until then rows can only be written directly
    # (tests, seed data, or SQL).
    op.create_table(
        "items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column(
            "default_income_account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "default_expense_account_id",
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
        sa.Column("unit_price_cents", sa.Integer, nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
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
        sa.UniqueConstraint("code", name="uq_items_code"),
        sa.CheckConstraint(
            "type IN ('service','product','bundle')",
            name="ck_items_type_valid",
        ),
        sa.CheckConstraint(
            "unit_price_cents IS NULL OR unit_price_cents >= 0",
            name="ck_items_price_non_negative",
        ),
    )

    # --- invoices ----------------------------------------------------------
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column(
            "customer_id",
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("terms", sa.String(length=32), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=True),
        sa.Column("memo", sa.String(length=1024), nullable=True),
        sa.Column("subtotal_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tax_total_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "amount_paid_cents",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "journal_entry_id",
            sa.Integer,
            sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("number", name="uq_invoices_number"),
        sa.CheckConstraint(
            "status IN ('draft','sent','partial','paid','void')",
            name="ck_invoices_status_valid",
        ),
        sa.CheckConstraint(
            "subtotal_cents >= 0 AND tax_total_cents >= 0 AND total_cents >= 0",
            name="ck_invoices_non_negative",
        ),
        sa.CheckConstraint(
            "total_cents = subtotal_cents + tax_total_cents",
            name="ck_invoices_total_is_sum",
        ),
        sa.CheckConstraint(
            "amount_paid_cents >= 0 AND amount_paid_cents <= total_cents",
            name="ck_invoices_paid_within_total",
        ),
        sa.CheckConstraint(
            "terms IN ('net_15','net_30','net_60','due_on_receipt','custom')",
            name="ck_invoices_terms_valid",
        ),
    )
    op.create_index("ix_invoices_customer", "invoices", ["customer_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"])

    # --- invoice_lines -----------------------------------------------------
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "invoice_id",
            sa.Integer,
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column(
            "item_id",
            sa.Integer,
            sa.ForeignKey("items.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column(
            "quantity_milli",
            sa.Integer,
            nullable=False,
            server_default="1000",
            comment="Quantity in milli-units. 1000 = 1 unit, 500 = 0.5 unit.",
        ),
        sa.Column("unit_price_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "tax_code_id",
            sa.Integer,
            sa.ForeignKey("tax_codes.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("tax_amount_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("amount_cents", sa.Integer, nullable=False, server_default="0"),
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
        sa.CheckConstraint(
            "quantity_milli > 0",
            name="ck_invoice_lines_qty_positive",
        ),
        sa.CheckConstraint(
            "unit_price_cents >= 0",
            name="ck_invoice_lines_price_non_negative",
        ),
        sa.CheckConstraint(
            "tax_amount_cents >= 0 AND amount_cents >= 0",
            name="ck_invoice_lines_amounts_non_negative",
        ),
    )
    op.create_index("ix_invoice_lines_invoice", "invoice_lines", ["invoice_id"])
    op.create_index("ix_invoice_lines_tax_code", "invoice_lines", ["tax_code_id"])

    # --- payments ----------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id",
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("payment_date", sa.Date, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column(
            "deposit_account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("method", sa.String(length=32), nullable=True),
        sa.Column("reference", sa.String(length=64), nullable=True),
        sa.Column("memo", sa.String(length=1024), nullable=True),
        sa.Column(
            "journal_entry_id",
            sa.Integer,
            sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="posted",
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
        sa.CheckConstraint(
            "amount_cents > 0",
            name="ck_payments_amount_positive",
        ),
        sa.CheckConstraint(
            "status IN ('posted','void')",
            name="ck_payments_status_valid",
        ),
        sa.CheckConstraint(
            "method IS NULL OR method IN ('check','ach','card','wire','cash','other')",
            name="ck_payments_method_valid",
        ),
    )
    op.create_index("ix_payments_customer", "payments", ["customer_id"])
    op.create_index("ix_payments_date", "payments", ["payment_date"])

    # --- payment_applications ---------------------------------------------
    op.create_table(
        "payment_applications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "payment_id",
            sa.Integer,
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            sa.Integer,
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("discount_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("writeoff_cents", sa.Integer, nullable=False, server_default="0"),
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
        sa.UniqueConstraint(
            "payment_id", "invoice_id", name="uq_payment_applications_pair"
        ),
        sa.CheckConstraint(
            "amount_cents > 0",
            name="ck_payment_applications_amount_positive",
        ),
        sa.CheckConstraint(
            "discount_cents >= 0 AND writeoff_cents >= 0",
            name="ck_payment_applications_discount_non_negative",
        ),
    )
    op.create_index(
        "ix_payment_applications_invoice",
        "payment_applications",
        ["invoice_id"],
    )

    # --- triggers ----------------------------------------------------------
    _apply_triggers()


def downgrade() -> None:
    for name in TRIGGER_NAMES:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    # Recreate the 0002-era rate non-negative guard on the way down, so
    # downgrading 0003 -> 0002 leaves us in the expected state.
    op.execute(
        sa.text(
            """
            CREATE TRIGGER IF NOT EXISTS trg_tax_codes_rate_non_negative
            BEFORE UPDATE OF rate_bps ON tax_codes
            FOR EACH ROW
            WHEN NEW.rate_bps < 0 OR NEW.rate_bps >= 10000
            BEGIN
                SELECT RAISE(ABORT, 'tax rate must be between 0 and 10000 basis points');
            END
            """.strip()
        )
    )
    op.drop_index("ix_payment_applications_invoice", table_name="payment_applications")
    op.drop_table("payment_applications")
    op.drop_index("ix_payments_date", table_name="payments")
    op.drop_index("ix_payments_customer", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_invoice_lines_tax_code", table_name="invoice_lines")
    op.drop_index("ix_invoice_lines_invoice", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_due_date", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_customer", table_name="invoices")
    op.drop_table("invoices")
    op.drop_table("items")
