"""DB-layer integrity tests.

These tests deliberately bypass the service layer and try to cheat the
rules directly through the ORM / raw SQL. They prove the triggers
catch everything the service layer would, acting as the second line of
defense called out in PRD §5.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import DatabaseError, IntegrityError

from app.config import Settings
from app.db.engines import company_engine, dispose_company_engines
from app.db.schema import ensure_company_schema
from app.db.session import company_session
from app.models.account import Account, AccountType
from app.models.journal import JournalEntry, JournalLine, JournalSource, JournalStatus


@pytest.fixture(autouse=True)
def _dispose() -> None:
    dispose_company_engines()
    yield
    dispose_company_engines()


@pytest.fixture
def fresh_company(settings: Settings):
    """Bootstrap schema + triggers in a fresh per-test company DB."""
    engine = company_engine(settings, "testco")
    ensure_company_schema(engine)
    return "testco"


def _seed_accounts(settings: Settings, company: str) -> tuple[int, int]:
    with company_session(company, settings) as session:
        cash = Account(code="1000", name="Cash", type=AccountType.ASSET)
        revenue = Account(code="4000", name="Service Revenue", type=AccountType.INCOME)
        session.add_all([cash, revenue])
        session.flush()
        return cash.id, revenue.id


def test_cannot_insert_line_with_negative_amount(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    with (
        pytest.raises(IntegrityError),
        company_session(fresh_company, settings) as session,
    ):
        entry = JournalEntry(
            entry_date=date(2026, 1, 1),
            posting_date=date(2026, 1, 1),
            source_type=JournalSource.MANUAL,
        )
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=-100, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=100),
        ]
        session.add(entry)
        session.flush()


def test_cannot_insert_line_with_both_sides_zero(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, _ = _seed_accounts(settings, fresh_company)
    with (
        pytest.raises(IntegrityError),
        company_session(fresh_company, settings) as session,
    ):
        entry = JournalEntry(entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1))
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=0, credit_cents=0),
        ]
        session.add(entry)
        session.flush()


def test_cannot_insert_line_with_both_sides_positive(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, _ = _seed_accounts(settings, fresh_company)
    with (
        pytest.raises(IntegrityError),
        company_session(fresh_company, settings) as session,
    ):
        entry = JournalEntry(entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1))
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=50, credit_cents=50),
        ]
        session.add(entry)
        session.flush()


def test_cannot_post_entry_that_does_not_balance(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    # Create a draft with imbalanced lines (each line is legal on its own,
    # but the pair sums wrong).
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(
            entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1),
        )
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=100, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=90),
        ]
        session.add(entry)
        session.flush()
        entry_id = entry.id

    # Now try to post it.
    with (
        pytest.raises(DatabaseError, match="does not balance"),
        company_session(fresh_company, settings) as session,
    ):
        entry = session.get(JournalEntry, entry_id)
        assert entry is not None
        entry.status = JournalStatus.POSTED
        session.flush()


def test_cannot_post_entry_with_one_line(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, _ = _seed_accounts(settings, fresh_company)
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(
            entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1),
        )
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=100, credit_cents=0),
        ]
        session.add(entry)
        session.flush()
        entry_id = entry.id

    with (
        pytest.raises(DatabaseError, match="at least two lines"),
        company_session(fresh_company, settings) as session,
    ):
        entry = session.get(JournalEntry, entry_id)
        assert entry is not None
        entry.status = JournalStatus.POSTED
        session.flush()


def test_can_post_balanced_entry(settings: Settings, fresh_company: str) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(
            entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1),
        )
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=250, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=250),
        ]
        session.add(entry)
        session.flush()
        entry.status = JournalStatus.POSTED
        session.flush()
        assert entry.status == JournalStatus.POSTED


def test_posted_entry_cannot_be_edited(settings: Settings, fresh_company: str) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1))
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=100, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=100),
        ]
        session.add(entry)
        session.flush()
        entry.status = JournalStatus.POSTED
        session.flush()
        entry_id = entry.id

    with (
        pytest.raises(DatabaseError, match="immutable"),
        company_session(fresh_company, settings) as session,
    ):
        entry = session.get(JournalEntry, entry_id)
        assert entry is not None
        entry.memo = "sneaky edit"
        session.flush()


def test_posted_entry_can_transition_to_void(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1))
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=100, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=100),
        ]
        session.add(entry)
        session.flush()
        entry.status = JournalStatus.POSTED
        session.flush()
        entry.status = JournalStatus.VOID
        session.flush()
        assert entry.status == JournalStatus.VOID


def test_posted_entry_cannot_return_to_draft(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1))
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=100, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=100),
        ]
        session.add(entry)
        session.flush()
        entry.status = JournalStatus.POSTED
        session.flush()
        entry_id = entry.id

    with (
        pytest.raises(DatabaseError, match="return to draft"),
        company_session(fresh_company, settings) as session,
    ):
        entry = session.get(JournalEntry, entry_id)
        assert entry is not None
        entry.status = JournalStatus.DRAFT
        session.flush()


def test_posted_entry_cannot_be_deleted(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1))
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=100, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=100),
        ]
        session.add(entry)
        session.flush()
        entry.status = JournalStatus.POSTED
        session.flush()
        entry_id = entry.id

    # SQLAlchemy's delete cascades to lines first, so either trigger
    # (line-level or entry-level) may fire depending on ORM flush order.
    # Both block the delete, which is what we care about.
    with (
        pytest.raises(DatabaseError, match=r"cannot (delete|modify) lines|cannot be deleted"),
        company_session(fresh_company, settings) as session,
    ):
        entry = session.get(JournalEntry, entry_id)
        assert entry is not None
        session.delete(entry)
        session.flush()


def test_lines_of_posted_entry_cannot_be_changed(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1))
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=100, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=100),
        ]
        session.add(entry)
        session.flush()
        entry.status = JournalStatus.POSTED
        session.flush()
        line_id = entry.lines[0].id

    with (
        pytest.raises(DatabaseError, match="cannot modify lines"),
        company_session(fresh_company, settings) as session,
    ):
        line = session.get(JournalLine, line_id)
        assert line is not None
        line.memo = "after the fact"
        session.flush()


def test_account_cannot_be_deleted_with_lines(
    settings: Settings, fresh_company: str
) -> None:
    cash_id, rev_id = _seed_accounts(settings, fresh_company)
    with company_session(fresh_company, settings) as session:
        entry = JournalEntry(entry_date=date(2026, 1, 1), posting_date=date(2026, 1, 1))
        entry.lines = [
            JournalLine(line_number=1, account_id=cash_id, debit_cents=100, credit_cents=0),
            JournalLine(line_number=2, account_id=rev_id, debit_cents=0, credit_cents=100),
        ]
        session.add(entry)
        session.flush()
        # Still in draft; lines exist referencing cash_id.

    with (
        pytest.raises(DatabaseError, match="referenced by journal lines"),
        company_session(fresh_company, settings) as session,
    ):
        cash = session.get(Account, cash_id)
        assert cash is not None
        session.delete(cash)
        session.flush()


def test_audit_log_is_append_only(settings: Settings, fresh_company: str) -> None:
    from app.models.audit import AuditAction, AuditLog

    with company_session(fresh_company, settings) as session:
        entry = AuditLog(
            actor="tester",
            action=AuditAction.CREATE.value,
            entity_type="account",
            entity_id="1",
        )
        session.add(entry)
        session.flush()
        row_id = entry.id

    with (
        pytest.raises(DatabaseError, match="immutable"),
        company_session(fresh_company, settings) as session,
    ):
        row = session.get(AuditLog, row_id)
        assert row is not None
        row.note = "try to change"
        session.flush()

    with (
        pytest.raises(DatabaseError, match="append-only"),
        company_session(fresh_company, settings) as session,
    ):
        row = session.get(AuditLog, row_id)
        assert row is not None
        session.delete(row)
        session.flush()


def test_normal_balance_mapping() -> None:
    from app.models.account import AccountType, NormalBalance, normal_balance

    assert normal_balance(AccountType.ASSET) == NormalBalance.DEBIT
    assert normal_balance(AccountType.EXPENSE) == NormalBalance.DEBIT
    assert normal_balance(AccountType.LIABILITY) == NormalBalance.CREDIT
    assert normal_balance(AccountType.EQUITY) == NormalBalance.CREDIT
    assert normal_balance(AccountType.INCOME) == NormalBalance.CREDIT
