"""Chart-of-accounts templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.account import AccountType


@dataclass(frozen=True)
class SeedAccount:
    code: str
    name: str
    type: AccountType
    subtype: Optional[str] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class Template:
    key: str
    label: str
    description: str
    accounts: tuple[SeedAccount, ...]


# ---------------------------------------------------------------------------
# Schedule C — service business
# ---------------------------------------------------------------------------

_SCHED_C_SERVICE = Template(
    key="sched_c_service",
    label="Schedule C — Service business",
    description=(
        "Minimal chart of accounts for a sole proprietor service business. "
        "No inventory, no payroll."
    ),
    accounts=(
        # Assets
        SeedAccount("1000", "Cash", AccountType.ASSET, "current_asset"),
        SeedAccount("1010", "Checking Account", AccountType.ASSET, "bank"),
        SeedAccount("1020", "Savings Account", AccountType.ASSET, "bank"),
        SeedAccount("1200", "Accounts Receivable", AccountType.ASSET, "current_asset"),
        SeedAccount("1500", "Equipment", AccountType.ASSET, "fixed_asset"),
        SeedAccount(
            "1510", "Accumulated Depreciation", AccountType.ASSET, "fixed_asset"
        ),
        # Liabilities
        SeedAccount(
            "2000", "Accounts Payable", AccountType.LIABILITY, "current_liability"
        ),
        SeedAccount(
            "2100", "Credit Card Payable", AccountType.LIABILITY, "current_liability"
        ),
        SeedAccount(
            "2200", "Sales Tax Payable", AccountType.LIABILITY, "current_liability"
        ),
        # Equity
        SeedAccount("3000", "Owner's Equity", AccountType.EQUITY),
        SeedAccount("3100", "Owner's Draw", AccountType.EQUITY),
        SeedAccount("3900", "Retained Earnings", AccountType.EQUITY),
        # Income
        SeedAccount("4000", "Service Revenue", AccountType.INCOME),
        SeedAccount("4100", "Interest Income", AccountType.INCOME),
        # Expenses
        SeedAccount("5000", "Rent Expense", AccountType.EXPENSE),
        SeedAccount("5010", "Utilities Expense", AccountType.EXPENSE),
        SeedAccount("5020", "Insurance Expense", AccountType.EXPENSE),
        SeedAccount("5030", "Office Supplies", AccountType.EXPENSE),
        SeedAccount("5040", "Professional Fees", AccountType.EXPENSE),
        SeedAccount("5050", "Software & Subscriptions", AccountType.EXPENSE),
        SeedAccount("5060", "Travel", AccountType.EXPENSE),
        SeedAccount("5070", "Meals", AccountType.EXPENSE),
        SeedAccount("5080", "Marketing & Advertising", AccountType.EXPENSE),
        SeedAccount("5090", "Bank Fees", AccountType.EXPENSE),
        SeedAccount("5900", "Depreciation Expense", AccountType.EXPENSE),
    ),
)


# ---------------------------------------------------------------------------
# Schedule C — retail business
# ---------------------------------------------------------------------------

_SCHED_C_RETAIL = Template(
    key="sched_c_retail",
    label="Schedule C — Retail business",
    description=(
        "Service template plus inventory, cost of goods sold, and sales tax "
        "accounts for a small retail operation."
    ),
    accounts=(
        # Assets
        SeedAccount("1000", "Cash", AccountType.ASSET, "current_asset"),
        SeedAccount("1010", "Checking Account", AccountType.ASSET, "bank"),
        SeedAccount("1020", "Savings Account", AccountType.ASSET, "bank"),
        SeedAccount("1200", "Accounts Receivable", AccountType.ASSET, "current_asset"),
        SeedAccount("1300", "Inventory", AccountType.ASSET, "current_asset"),
        SeedAccount("1500", "Equipment", AccountType.ASSET, "fixed_asset"),
        SeedAccount(
            "1510", "Accumulated Depreciation", AccountType.ASSET, "fixed_asset"
        ),
        # Liabilities
        SeedAccount(
            "2000", "Accounts Payable", AccountType.LIABILITY, "current_liability"
        ),
        SeedAccount(
            "2100", "Credit Card Payable", AccountType.LIABILITY, "current_liability"
        ),
        SeedAccount(
            "2200", "Sales Tax Payable", AccountType.LIABILITY, "current_liability"
        ),
        # Equity
        SeedAccount("3000", "Owner's Equity", AccountType.EQUITY),
        SeedAccount("3100", "Owner's Draw", AccountType.EQUITY),
        SeedAccount("3900", "Retained Earnings", AccountType.EQUITY),
        # Income
        SeedAccount("4000", "Sales Revenue", AccountType.INCOME),
        SeedAccount("4100", "Interest Income", AccountType.INCOME),
        # Expenses / COGS
        SeedAccount("5000", "Cost of Goods Sold", AccountType.EXPENSE),
        SeedAccount("5100", "Rent Expense", AccountType.EXPENSE),
        SeedAccount("5110", "Utilities Expense", AccountType.EXPENSE),
        SeedAccount("5120", "Insurance Expense", AccountType.EXPENSE),
        SeedAccount("5130", "Office Supplies", AccountType.EXPENSE),
        SeedAccount("5140", "Professional Fees", AccountType.EXPENSE),
        SeedAccount("5150", "Marketing & Advertising", AccountType.EXPENSE),
        SeedAccount("5160", "Bank & Credit Card Fees", AccountType.EXPENSE),
        SeedAccount("5900", "Depreciation Expense", AccountType.EXPENSE),
    ),
)


# ---------------------------------------------------------------------------
# S-corp — general
# ---------------------------------------------------------------------------

_S_CORP_GENERAL = Template(
    key="s_corp_general",
    label="S-corp — General",
    description=(
        "Chart of accounts for an S-corp: common stock, APIC, shareholder "
        "distributions, retained earnings. Per PRD §15 Q5 — Dromos Inc.'s "
        "template."
    ),
    accounts=(
        # Assets
        SeedAccount("1000", "Cash", AccountType.ASSET, "current_asset"),
        SeedAccount("1010", "Checking Account", AccountType.ASSET, "bank"),
        SeedAccount("1020", "Savings Account", AccountType.ASSET, "bank"),
        SeedAccount("1200", "Accounts Receivable", AccountType.ASSET, "current_asset"),
        SeedAccount("1500", "Equipment", AccountType.ASSET, "fixed_asset"),
        SeedAccount(
            "1510", "Accumulated Depreciation", AccountType.ASSET, "fixed_asset"
        ),
        # Liabilities
        SeedAccount(
            "2000", "Accounts Payable", AccountType.LIABILITY, "current_liability"
        ),
        SeedAccount(
            "2100", "Credit Card Payable", AccountType.LIABILITY, "current_liability"
        ),
        SeedAccount(
            "2200", "Sales Tax Payable", AccountType.LIABILITY, "current_liability"
        ),
        SeedAccount(
            "2300", "Accrued Liabilities", AccountType.LIABILITY, "current_liability"
        ),
        # Equity — S-corp specific
        SeedAccount("3000", "Common Stock", AccountType.EQUITY),
        SeedAccount("3100", "Additional Paid-In Capital", AccountType.EQUITY),
        SeedAccount("3500", "Shareholder Distributions", AccountType.EQUITY),
        SeedAccount("3900", "Retained Earnings", AccountType.EQUITY),
        # Income
        SeedAccount("4000", "Service Revenue", AccountType.INCOME),
        SeedAccount("4010", "Product Revenue", AccountType.INCOME),
        SeedAccount("4100", "Interest Income", AccountType.INCOME),
        # Expenses
        SeedAccount("5000", "Rent Expense", AccountType.EXPENSE),
        SeedAccount("5010", "Utilities Expense", AccountType.EXPENSE),
        SeedAccount("5020", "Insurance Expense", AccountType.EXPENSE),
        SeedAccount("5030", "Office Supplies", AccountType.EXPENSE),
        SeedAccount("5040", "Professional Fees", AccountType.EXPENSE),
        SeedAccount("5050", "Software & Subscriptions", AccountType.EXPENSE),
        SeedAccount("5060", "Travel", AccountType.EXPENSE),
        SeedAccount("5070", "Meals", AccountType.EXPENSE),
        SeedAccount("5080", "Marketing & Advertising", AccountType.EXPENSE),
        SeedAccount("5090", "Bank Fees", AccountType.EXPENSE),
        SeedAccount("5900", "Depreciation Expense", AccountType.EXPENSE),
    ),
)


TEMPLATES: dict[str, Template] = {
    t.key: t for t in (_SCHED_C_SERVICE, _SCHED_C_RETAIL, _S_CORP_GENERAL)
}


def get_template(key: str) -> Template:
    try:
        return TEMPLATES[key]
    except KeyError as e:
        available = ", ".join(sorted(TEMPLATES))
        raise KeyError(
            f"unknown template {key!r}; available: {available}"
        ) from e
