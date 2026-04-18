-- Integrity triggers for the company database.
--
-- These triggers provide the DB-layer guarantees called out in PRD §5
-- and §8.1: posted journal entries are immutable, they balance, and
-- they are never hard-deleted. The service layer enforces the same
-- rules for helpful error messages; these triggers are the safety net.
--
-- Applied by app.db.schema.ensure_company_schema() immediately after
-- create_all(). Idempotent via "IF NOT EXISTS".

-- ---------------------------------------------------------------------------
-- Journal-entry balance: sum(debits) = sum(credits) on every posted entry.
-- Fires on update-to-posted and on any change to lines of a posted entry.
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS trg_journal_entries_balance_on_post
BEFORE UPDATE OF status ON journal_entries
FOR EACH ROW
WHEN NEW.status = 'posted' AND OLD.status != 'posted'
BEGIN
    -- Line count first: a more actionable error for the single-line case.
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

-- ---------------------------------------------------------------------------
-- Posted-entry immutability: once status = 'posted', only the specific
-- transition to 'void' is allowed. No other columns can change.
-- ---------------------------------------------------------------------------

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

-- ---------------------------------------------------------------------------
-- Posted-entry no-delete. Once posted, an entry stays in the database.
-- Void it instead.
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS trg_journal_entries_no_delete_posted
BEFORE DELETE ON journal_entries
FOR EACH ROW
WHEN OLD.status IN ('posted', 'void')
BEGIN
    SELECT RAISE(ABORT, 'posted or voided journal entries cannot be deleted');
END;

-- ---------------------------------------------------------------------------
-- Line-level immutability when the parent entry is posted.
-- ---------------------------------------------------------------------------

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

-- ---------------------------------------------------------------------------
-- Account no-delete (deactivate instead).
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS trg_accounts_no_delete_with_lines
BEFORE DELETE ON accounts
FOR EACH ROW
WHEN EXISTS (
    SELECT 1 FROM journal_lines WHERE account_id = OLD.id LIMIT 1
)
BEGIN
    SELECT RAISE(ABORT, 'cannot delete an account referenced by journal lines');
END;

-- ---------------------------------------------------------------------------
-- Audit log append-only: rows may not be updated or deleted.
-- ---------------------------------------------------------------------------

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
