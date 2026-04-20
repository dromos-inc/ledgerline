"""bills + bill payments — Phase 2 S2 (AP one-liner)

Revision ID: 0004_bills_and_bill_payments
Revises: 0003_invoices_and_payments
Create Date: 2026-04-20 00:00:00

AP mirror of the AR tables landed in 0003. Four new tables:

- ``bills``: header for a vendor-owed document. Status FSM
  draft -> open -> partial -> paid (+ void from any state). The
  approval step (``approved_at`` / ``approved_by``) is captured on
  post; we don't ship a separate approval workflow in Phase 2/S2.
- ``bill_lines``: one line per expense category. Same milli-unit
  quantities and cents amounts as invoice_lines. ``account_id`` must
  be an expense (or asset, for capex) account — the service layer
  validates at post time; the DB layer just requires an FK.
- ``bill_payments``: vendor-side payment header. Draws from a chosen
  asset account (bank or cash), creates its own journal entry. One
  bill_payment can apply to many bills.
- ``bill_payment_applications``: many-to-many between bill_payments
  and bills with per-application amount.

Plus nine triggers that mirror 0003's AR sub-ledger rules for AP:

- ``trg_bills_post_auto_je`` — non-draft status requires JE link.
- ``trg_bills_immutable_posted`` — header frozen except status + paid.
- ``trg_bill_lines_no_*_on_posted`` — lines locked once bill leaves
  draft (mirror of invoice_lines_no_update/delete/insert).
- ``trg_bills_no_delete_posted`` — hard-delete of non-draft bills
  refused; use void (reversal) instead.
- ``trg_bills_status_fsm`` — void is terminal, draft re-entry blocked.
- ``trg_vendors_no_delete_with_bills`` — hard-deleting a vendor that
  has any bill row is refused. Deactivation stays available.
- ``trg_bill_payments_immutable_posted`` — header frozen after post.
- ``trg_bill_payments_no_delete_posted`` — DELETE on posted/voided
  bill_payments refused.

Note on bill status labels: invoices use ``'sent'`` for the initial
posted state; bills use ``'open'``. This matches how every accounting
product names the two states (invoices go out; bills come in and sit
open).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_bills_and_bill_payments"
down_revision: Union[str, None] = "0003_invoices_and_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Integrity triggers. Same single-SQL-statement-per-entry contract as the
# 0001/0002/0003 triggers so the whole migration is atomic.
# ---------------------------------------------------------------------------

TRIGGERS: tuple[str, ...] = (
    """
    CREATE TRIGGER IF NOT EXISTS trg_bills_post_auto_je
    BEFORE UPDATE OF status ON bills
    FOR EACH ROW
    WHEN NEW.status IN ('open', 'partial', 'paid') AND NEW.journal_entry_id IS NULL
    BEGIN
        SELECT RAISE(ABORT, 'bill must have a journal_entry_id before transitioning out of draft');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_bills_immutable_posted
    BEFORE UPDATE ON bills
    FOR EACH ROW
    WHEN OLD.status != 'draft'
      AND (
           NEW.vendor_id != OLD.vendor_id
        OR NEW.bill_date != OLD.bill_date
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
        SELECT RAISE(ABORT, 'posted bill fields are immutable except status and amount_paid_cents');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_bill_lines_no_update_on_posted
    BEFORE UPDATE ON bill_lines
    FOR EACH ROW
    WHEN (
        SELECT status FROM bills WHERE id = OLD.bill_id
    ) != 'draft'
    BEGIN
        SELECT RAISE(ABORT, 'cannot modify lines of a posted or voided bill');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_bill_lines_no_delete_on_posted
    BEFORE DELETE ON bill_lines
    FOR EACH ROW
    WHEN (
        SELECT status FROM bills WHERE id = OLD.bill_id
    ) != 'draft'
    BEGIN
        SELECT RAISE(ABORT, 'cannot delete lines of a posted or voided bill');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_bill_lines_no_insert_on_posted
    BEFORE INSERT ON bill_lines
    FOR EACH ROW
    WHEN (
        SELECT status FROM bills WHERE id = NEW.bill_id
    ) != 'draft'
    BEGIN
        SELECT RAISE(ABORT, 'cannot add lines to a posted or voided bill');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_bills_no_delete_posted
    BEFORE DELETE ON bills
    FOR EACH ROW
    WHEN OLD.status != 'draft'
    BEGIN
        SELECT RAISE(ABORT, 'posted or voided bills cannot be deleted');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_bills_status_fsm
    BEFORE UPDATE OF status ON bills
    FOR EACH ROW
    WHEN OLD.status = 'void'
      OR (NEW.status = 'draft' AND OLD.status != 'draft')
    BEGIN
        SELECT RAISE(ABORT, 'illegal bill status transition');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_vendors_no_delete_with_bills
    BEFORE DELETE ON vendors
    FOR EACH ROW
    WHEN EXISTS (
        SELECT 1 FROM bills WHERE vendor_id = OLD.id LIMIT 1
    )
    BEGIN
        SELECT RAISE(ABORT, 'cannot delete a vendor with bills; deactivate instead');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_bill_payments_immutable_posted
    BEFORE UPDATE ON bill_payments
    FOR EACH ROW
    WHEN OLD.status = 'posted'
      AND (
           NEW.vendor_id != OLD.vendor_id
        OR NEW.payment_date != OLD.payment_date
        OR NEW.amount_cents != OLD.amount_cents
        OR NEW.payout_account_id != OLD.payout_account_id
        OR COALESCE(NEW.method, '') != COALESCE(OLD.method, '')
        OR COALESCE(NEW.reference, '') != COALESCE(OLD.reference, '')
        OR COALESCE(NEW.memo, '') != COALESCE(OLD.memo, '')
        OR NEW.journal_entry_id != OLD.journal_entry_id
      )
      AND NEW.status NOT IN ('void')
    BEGIN
        SELECT RAISE(ABORT, 'posted bill_payment fields are immutable except for void transition');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_bill_payments_no_delete_posted
    BEFORE DELETE ON bill_payments
    FOR EACH ROW
    WHEN OLD.status IN ('posted', 'void')
    BEGIN
        SELECT RAISE(ABORT, 'posted or voided bill_payments cannot be deleted');
    END
    """,
)


TRIGGER_NAMES: list[str] = [
    "trg_bills_post_auto_je",
    "trg_bills_immutable_posted",
    "trg_bill_lines_no_update_on_posted",
    "trg_bill_lines_no_delete_on_posted",
    "trg_bill_lines_no_insert_on_posted",
    "trg_bills_no_delete_posted",
    "trg_bills_status_fsm",
    "trg_vendors_no_delete_with_bills",
    "trg_bill_payments_immutable_posted",
    "trg_bill_payments_no_delete_posted",
]


def _apply_triggers() -> None:
    """Run each CREATE TRIGGER through Alembic's managed transaction."""
    for trigger_sql in TRIGGERS:
        op.execute(sa.text(trigger_sql.strip()))


def upgrade() -> None:
    # --- bills -------------------------------------------------------------
    op.create_table(
        "bills",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column(
            "vendor_id",
            sa.Integer,
            sa.ForeignKey("vendors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("bill_date", sa.Date, nullable=False),
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
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
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
        sa.UniqueConstraint("number", name="uq_bills_number"),
        sa.CheckConstraint(
            "status IN ('draft','open','partial','paid','void')",
            name="ck_bills_status_valid",
        ),
        sa.CheckConstraint(
            "subtotal_cents >= 0 AND tax_total_cents >= 0 AND total_cents >= 0",
            name="ck_bills_non_negative",
        ),
        sa.CheckConstraint(
            "total_cents = subtotal_cents + tax_total_cents",
            name="ck_bills_total_is_sum",
        ),
        sa.CheckConstraint(
            "amount_paid_cents >= 0 AND amount_paid_cents <= total_cents",
            name="ck_bills_paid_within_total",
        ),
        sa.CheckConstraint(
            "terms IN ('net_15','net_30','net_60','due_on_receipt','custom')",
            name="ck_bills_terms_valid",
        ),
    )
    op.create_index("ix_bills_vendor", "bills", ["vendor_id"])
    op.create_index("ix_bills_status", "bills", ["status"])
    op.create_index("ix_bills_due_date", "bills", ["due_date"])

    # --- bill_lines --------------------------------------------------------
    op.create_table(
        "bill_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "bill_id",
            sa.Integer,
            sa.ForeignKey("bills.id", ondelete="RESTRICT"),
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
            name="ck_bill_lines_qty_positive",
        ),
        sa.CheckConstraint(
            "unit_price_cents >= 0",
            name="ck_bill_lines_price_non_negative",
        ),
        sa.CheckConstraint(
            "tax_amount_cents >= 0 AND amount_cents >= 0",
            name="ck_bill_lines_amounts_non_negative",
        ),
    )
    op.create_index("ix_bill_lines_bill", "bill_lines", ["bill_id"])
    op.create_index("ix_bill_lines_tax_code", "bill_lines", ["tax_code_id"])

    # --- bill_payments -----------------------------------------------------
    op.create_table(
        "bill_payments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "vendor_id",
            sa.Integer,
            sa.ForeignKey("vendors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("payment_date", sa.Date, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column(
            "payout_account_id",
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
            name="ck_bill_payments_amount_positive",
        ),
        sa.CheckConstraint(
            "status IN ('posted','void')",
            name="ck_bill_payments_status_valid",
        ),
        sa.CheckConstraint(
            "method IS NULL OR method IN ('check','ach','card','wire','cash','other')",
            name="ck_bill_payments_method_valid",
        ),
    )
    op.create_index("ix_bill_payments_vendor", "bill_payments", ["vendor_id"])
    op.create_index("ix_bill_payments_date", "bill_payments", ["payment_date"])

    # --- bill_payment_applications ----------------------------------------
    op.create_table(
        "bill_payment_applications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "bill_payment_id",
            sa.Integer,
            sa.ForeignKey("bill_payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "bill_id",
            sa.Integer,
            sa.ForeignKey("bills.id", ondelete="RESTRICT"),
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
            "bill_payment_id", "bill_id", name="uq_bill_payment_applications_pair"
        ),
        sa.CheckConstraint(
            "amount_cents > 0",
            name="ck_bill_payment_applications_amount_positive",
        ),
        sa.CheckConstraint(
            "discount_cents >= 0 AND writeoff_cents >= 0",
            name="ck_bill_payment_applications_discount_non_negative",
        ),
    )
    op.create_index(
        "ix_bill_payment_applications_bill",
        "bill_payment_applications",
        ["bill_id"],
    )

    # --- triggers ----------------------------------------------------------
    _apply_triggers()


def downgrade() -> None:
    for name in TRIGGER_NAMES:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.drop_index(
        "ix_bill_payment_applications_bill",
        table_name="bill_payment_applications",
    )
    op.drop_table("bill_payment_applications")
    op.drop_index("ix_bill_payments_date", table_name="bill_payments")
    op.drop_index("ix_bill_payments_vendor", table_name="bill_payments")
    op.drop_table("bill_payments")
    op.drop_index("ix_bill_lines_tax_code", table_name="bill_lines")
    op.drop_index("ix_bill_lines_bill", table_name="bill_lines")
    op.drop_table("bill_lines")
    op.drop_index("ix_bills_due_date", table_name="bills")
    op.drop_index("ix_bills_status", table_name="bills")
    op.drop_index("ix_bills_vendor", table_name="bills")
    op.drop_table("bills")