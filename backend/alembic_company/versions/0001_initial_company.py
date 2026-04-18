"""initial per-company schema

Revision ID: 0001_initial_company
Revises:
Create Date: 2026-04-18 00:00:00

Establishes the per-company database at v1:

- ``accounts``: chart of accounts with CHECK on type and unique on code.
- ``journal_entries`` / ``journal_lines``: the ledger with
  per-line CHECK constraints (non-negative, exactly-one-side) and the
  status/entry_date indexes that reports need.
- ``audit_log``: append-only (enforced by triggers below).

Triggers land in this same migration so the integrity guarantees are
created atomically with the tables themselves. Any future schema change
that touches these triggers ships its own migration that drops + recreates
the affected ones.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_company"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Trigger SQL. Inlined here rather than loaded from triggers.sql so the
# migration is self-contained and survives source-tree reorganization.
# ---------------------------------------------------------------------------

TRIGGERS_SQL: str = """
CREATE TRIGGER IF NOT EXISTS trg_journal_entries_balance_on_post
BEFORE UPDATE OF status ON journal_entries
FOR EACH ROW
WHEN NEW.status = 'posted' AND OLD.status != 'posted'
BEGIN
    SELECT CASE
        WHEN (
            SELECT COUNT(*)
            FROM journal_lines
            WHERE journal_entry_id = NEW.id
        ) < 2 THEN
            RAISE(ABORT, 'journal entry must have at least two lines')
    END;
    SELECT CASE
        WHEN (
            SELECT COALESCE(SUM(debit_cents), 0) - COALESCE(SUM(credit_cents), 0)
            FROM journal_lines
            WHERE journal_entry_id = NEW.id
        ) != 0 THEN
            RAISE(ABORT, 'journal entry does not balance: debits != credits')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_journal_entries_immutable_posted
BEFORE UPDATE ON journal_entries
FOR EACH ROW
WHEN OLD.status = 'posted'
BEGIN
    SELECT CASE
        WHEN NEW.status NOT IN ('posted', 'void') THEN
            RAISE(ABORT, 'posted journal entry cannot return to draft')
        WHEN NEW.entry_date != OLD.entry_date
          OR NEW.posting_date != OLD.posting_date
          OR COALESCE(NEW.reference, '') != COALESCE(OLD.reference, '')
          OR COALESCE(NEW.memo, '') != COALESCE(OLD.memo, '')
          OR NEW.source_type != OLD.source_type
          OR COALESCE(NEW.source_id, -1) != COALESCE(OLD.source_id, -1)
          OR COALESCE(NEW.reversal_of_id, -1) != COALESCE(OLD.reversal_of_id, -1)
        THEN
            RAISE(ABORT, 'posted journal entry is immutable except status')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_journal_entries_no_delete_posted
BEFORE DELETE ON journal_entries
FOR EACH ROW
WHEN OLD.status IN ('posted', 'void')
BEGIN
    SELECT RAISE(ABORT, 'posted or voided journal entries cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS trg_journal_lines_no_update_on_posted
BEFORE UPDATE ON journal_lines
FOR EACH ROW
WHEN (
    SELECT status FROM journal_entries
    WHERE id = OLD.journal_entry_id
) IN ('posted', 'void')
BEGIN
    SELECT RAISE(ABORT, 'cannot modify lines of a posted or voided entry');
END;

CREATE TRIGGER IF NOT EXISTS trg_journal_lines_no_delete_on_posted
BEFORE DELETE ON journal_lines
FOR EACH ROW
WHEN (
    SELECT status FROM journal_entries
    WHERE id = OLD.journal_entry_id
) IN ('posted', 'void')
BEGIN
    SELECT RAISE(ABORT, 'cannot delete lines of a posted or voided entry');
END;

CREATE TRIGGER IF NOT EXISTS trg_journal_lines_no_insert_on_posted
BEFORE INSERT ON journal_lines
FOR EACH ROW
WHEN (
    SELECT status FROM journal_entries
    WHERE id = NEW.journal_entry_id
) IN ('posted', 'void')
BEGIN
    SELECT RAISE(ABORT, 'cannot add lines to a posted or voided entry');
END;

CREATE TRIGGER IF NOT EXISTS trg_accounts_no_delete_with_lines
BEFORE DELETE ON accounts
FOR EACH ROW
WHEN EXISTS (
    SELECT 1 FROM journal_lines WHERE account_id = OLD.id LIMIT 1
)
BEGIN
    SELECT RAISE(ABORT, 'cannot delete an account referenced by journal lines');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log rows are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log rows are append-only; deletion forbidden');
END;
""".strip()


TRIGGER_NAMES: list[str] = [
    "trg_journal_entries_balance_on_post",
    "trg_journal_entries_immutable_posted",
    "trg_journal_entries_no_delete_posted",
    "trg_journal_lines_no_update_on_posted",
    "trg_journal_lines_no_delete_on_posted",
    "trg_journal_lines_no_insert_on_posted",
    "trg_accounts_no_delete_with_lines",
    "trg_audit_log_no_update",
    "trg_audit_log_no_delete",
]


def _apply_triggers() -> None:
    """Execute the trigger SQL block via the raw DBAPI.

    Alembic's ``op.execute`` runs through SQLAlchemy which doesn't handle
    SQLite's multi-statement CREATE TRIGGER blocks cleanly. SQLite's
    ``executescript`` does.
    """
    bind = op.get_bind()
    raw = bind.connection.driver_connection  # underlying sqlite3.Connection
    cursor = raw.cursor()
    try:
        cursor.executescript(TRIGGERS_SQL)
    finally:
        cursor.close()


def upgrade() -> None:
    # --- accounts -----------------------------------------------------------
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("subtype", sa.String(length=64), nullable=True),
        sa.Column(
            "parent_id",
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
        sa.Column("description", sa.String(length=512), nullable=True),
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
        sa.UniqueConstraint("code", name="uq_accounts_code"),
        sa.CheckConstraint(
            "type IN ('asset','liability','equity','income','expense')",
            name="ck_accounts_type_valid",
        ),
    )

    # --- journal_entries ---------------------------------------------------
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("posting_date", sa.Date, nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=True),
        sa.Column("memo", sa.String(length=1024), nullable=True),
        sa.Column(
            "source_type",
            sa.String(length=24),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("source_id", sa.Integer, nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column(
            "reversal_of_id",
            sa.Integer,
            sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"),
            nullable=True,
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
            "status IN ('draft','posted','void')",
            name="ck_journal_entries_status_valid",
        ),
    )
    op.create_index(
        "ix_journal_entries_entry_date",
        "journal_entries",
        ["entry_date"],
    )
    op.create_index(
        "ix_journal_entries_status",
        "journal_entries",
        ["status"],
    )

    # --- journal_lines -----------------------------------------------------
    op.create_table(
        "journal_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "journal_entry_id",
            sa.Integer,
            sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column(
            "account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("debit_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("credit_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("memo", sa.String(length=512), nullable=True),
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
            "debit_cents >= 0 AND credit_cents >= 0",
            name="ck_journal_lines_non_negative",
        ),
        sa.CheckConstraint(
            "(debit_cents = 0 AND credit_cents > 0) OR "
            "(credit_cents = 0 AND debit_cents > 0)",
            name="ck_journal_lines_exactly_one_side",
        ),
    )
    op.create_index(
        "ix_journal_lines_entry",
        "journal_lines",
        ["journal_entry_id"],
    )
    op.create_index(
        "ix_journal_lines_account",
        "journal_lines",
        ["account_id"],
    )

    # --- audit_log ---------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("before_json", sa.Text, nullable=True),
        sa.Column("after_json", sa.Text, nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
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
    )

    # --- triggers ----------------------------------------------------------
    _apply_triggers()


def downgrade() -> None:
    for name in TRIGGER_NAMES:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.drop_index("ix_journal_lines_account", table_name="journal_lines")
    op.drop_index("ix_journal_lines_entry", table_name="journal_lines")
    op.drop_table("journal_lines")
    op.drop_index("ix_journal_entries_status", table_name="journal_entries")
    op.drop_index("ix_journal_entries_entry_date", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_table("accounts")
    op.drop_table("audit_log")
