# Phase 2 Design Document: AR / AP

**Status:** Draft · pending review
**Covers:** PRD v0.1 §9 Phase 2 ("AR and AP") plus the §10.4-10.6 module specs
**Prerequisite:** Phase 1 MVP, merged to main (commits through `98240b0`)
**Out of scope:** Banking (§10.7, Phase 3), Plaid (Phase 5), desktop packaging (Phase 6), inventory (Phase 8), payroll (deferred)

---

## 1. Context and goals

Phase 1 shipped the ledger itself: chart of accounts, manual journal entries, register, trial balance, P&L, balance sheet, CSV + JSON export. That gets a bookkeeper working books. What it does not get them is the single most common use case for small-business accounting software: **billing customers and paying vendors**.

Phase 2 exit criterion (verbatim from PRD §9): *"A small business owner can bill customers, record payments, enter vendor bills, pay them, and see who owes them money and who they owe."*

We translate that to five shippable slices, four of which are on the critical path for exit criterion and one (PDF + email) that unlocks the last yard of professional polish.

## 2. Slicing and order

We ship Phase 2 as **five independently mergeable slices**. Each slice ends with a running product; none requires the next one to be useful.

| Slice | Name | What lands | Phase 2 exit criterion? |
|-------|------|------------|:-:|
| **S1** | AR one-liner | Customers, invoices (post + void), payment application, AR aging | ✅ partial |
| **S2** | AP one-liner | Vendors, bills (post + void), bill payments, AP aging | ✅ partial |
| **S3** | Items + tax | Products/services with default accounts, tax codes with rates | ✅ full |
| **S5** | Statements | Customer and vendor statements (PRD §10.4) | ✅ full |
| **S4** | PDF + email | Invoice PDF rendering + SMTP/managed-provider email delivery | 🔶 polish |

### 2.1 Recommended shipping order: S1 → S2 → S3 → S5 → S4

**Why this order, not something else**:

1. **S1 first, alone.** Customer billing is the single feature that pays Ledgerline's rent. Getting it into Dromos's hands (the internal dogfood testbed, per PRD §15 Q5) inside the first week of Phase 2 shortens the feedback loop dramatically. The AR side also introduces more new concepts than AP does (status FSMs, payment application, aging buckets) — shipping it first absorbs the mental model cost once rather than twice.

2. **S2 second.** AP is structurally the mirror of AR: vendors instead of customers, bills instead of invoices, `Accounts Payable` control account instead of `Accounts Receivable`. Building it second means ~60% of the service/API/UI code from S1 becomes templated patterns to apply, not new problem-solving. We still want the two slices separate so each ships independently verifiable; combining them doubles the PR size with little learning upside.

3. **S3 third — and critical.** Without Items, every invoice line requires the user to pick an account and type a description by hand. That's fine for Dromos's S-corp with three services; it's a deal-breaker for a plumber with 40 SKUs. Tax codes are in the same slice because they attach to items (an item has a default tax code) and because the two concepts debut together in the invoice editor.

4. **S5 fourth.** Statements are a read-only rollup of already-posted data — no new domain modeling. Postponing them to fourth lets us wait and see which edge cases the PDF rendering in S4 should handle (for example, whether statements share the S4 template layer).

5. **S4 last.** PDF rendering plus transactional email is the slice with the most externalities: SMTP config surface area, deliverability monitoring, template design, and one physical artifact (the PDF) that users WILL complain about the typography of. All the other slices should work end-to-end without it (invoices can be copy-pasted, exported as CSV, or printed from the browser). Shipping last gives it the narrowest blast radius when things inevitably need iteration.

### 2.2 Alternative order considered: S1 + S2 in parallel

Two developers working two branches. Rejected for the Phase 2 solo-developer baseline (Matthew is the only committer today). Worth revisiting if a second contributor joins before S1 lands.

## 3. Data model additions

Eight new tables, all in the per-company database. The registry schema does not change. Every table inherits `created_at` / `updated_at` from `CompanyBase._TimestampMixin` (already on main).

### 3.1 Contacts

```
customers
  id            INTEGER PK AUTOINCREMENT
  code          VARCHAR(32) UNIQUE NOT NULL
  name          VARCHAR(255) NOT NULL
  company       VARCHAR(255)
  email         VARCHAR(255)
  phone         VARCHAR(64)
  tax_id        VARCHAR(64)
  billing_address   VARCHAR(512)
  shipping_address  VARCHAR(512)
  default_terms     VARCHAR(32)   -- "net_15", "net_30", "due_on_receipt"
  default_income_account_id INTEGER FK accounts(id) ON DELETE RESTRICT
  default_tax_code_id       INTEGER FK tax_codes(id) ON DELETE RESTRICT, NULL
  is_active     BOOLEAN NOT NULL DEFAULT TRUE
  notes         TEXT
  CHECK (default_terms IN ('net_15','net_30','net_60','due_on_receipt','custom'))

vendors
  id            INTEGER PK AUTOINCREMENT
  code          VARCHAR(32) UNIQUE NOT NULL
  name          VARCHAR(255) NOT NULL
  company       VARCHAR(255)
  email         VARCHAR(255)
  phone         VARCHAR(64)
  tax_id        VARCHAR(64)
  billing_address   VARCHAR(512)
  default_terms     VARCHAR(32)
  default_expense_account_id INTEGER FK accounts(id) ON DELETE RESTRICT
  is_active     BOOLEAN NOT NULL DEFAULT TRUE
  is_1099       BOOLEAN NOT NULL DEFAULT FALSE   -- surfaces in tax-ready exports
  notes         TEXT
  CHECK (default_terms IN ('net_15','net_30','net_60','due_on_receipt','custom'))
```

Both contacts table share a `code` column (user-facing short id, like account codes) separate from the integer primary key. This lets users reference "CUST-0042" in imported CSVs without knowing internal ids.

### 3.2 Items and tax codes

```
items
  id            INTEGER PK AUTOINCREMENT
  code          VARCHAR(32) UNIQUE NOT NULL
  name          VARCHAR(255) NOT NULL
  description   VARCHAR(512)
  type          VARCHAR(16) NOT NULL        -- 'service','product','bundle'
  default_income_account_id  INTEGER FK accounts(id)
  default_expense_account_id INTEGER FK accounts(id)  -- for items we also buy
  default_tax_code_id        INTEGER FK tax_codes(id)
  unit_price_cents  INTEGER                 -- optional default price
  unit              VARCHAR(32)             -- 'hour', 'each', 'day'
  is_active     BOOLEAN NOT NULL DEFAULT TRUE
  CHECK (type IN ('service','product','bundle'))

tax_codes
  id            INTEGER PK AUTOINCREMENT
  code          VARCHAR(16) UNIQUE NOT NULL   -- 'TX-STATE', 'GST', 'NONE'
  name          VARCHAR(128) NOT NULL          -- 'Texas State Sales Tax'
  rate_bps      INTEGER NOT NULL               -- basis points: 625 = 6.25%
  payable_account_id INTEGER FK accounts(id) NOT NULL  -- where tax accumulates
  is_active     BOOLEAN NOT NULL DEFAULT TRUE
  CHECK (rate_bps >= 0 AND rate_bps < 10000)
```

Tax rates stored as **basis points** (10000 = 100%) for the same reason money is stored as cents: no floating point in the ledger. A 6.25% rate is `rate_bps = 625`. The UI presents it as `6.25%`.

A single company can define many tax codes. Users pick the code per invoice line. Phase 2 does not attempt jurisdiction lookup, zip-code matching, or rate updates — those are Phase 7+ concerns or a third-party integration (Avalara / TaxJar).

### 3.3 Invoices and bills

```
invoices
  id            INTEGER PK AUTOINCREMENT
  number        VARCHAR(32) UNIQUE NOT NULL     -- 'INV-0001'
  customer_id   INTEGER FK customers(id) ON DELETE RESTRICT NOT NULL
  invoice_date  DATE NOT NULL
  due_date      DATE NOT NULL
  terms         VARCHAR(32) NOT NULL
  reference     VARCHAR(64)
  memo          VARCHAR(1024)
  subtotal_cents       INTEGER NOT NULL
  tax_total_cents      INTEGER NOT NULL
  total_cents          INTEGER NOT NULL
  amount_paid_cents    INTEGER NOT NULL DEFAULT 0
  status        VARCHAR(16) NOT NULL
  journal_entry_id INTEGER FK journal_entries(id)  -- NULL until posted
  sent_at       DATETIME
  CHECK (status IN ('draft','sent','partial','paid','void'))
  CHECK (subtotal_cents >= 0 AND tax_total_cents >= 0 AND total_cents >= 0)
  CHECK (total_cents = subtotal_cents + tax_total_cents)
  CHECK (amount_paid_cents >= 0 AND amount_paid_cents <= total_cents)
  INDEX (customer_id), INDEX (status), INDEX (due_date)

invoice_lines
  id            INTEGER PK AUTOINCREMENT
  invoice_id    INTEGER FK invoices(id) ON DELETE RESTRICT NOT NULL
  line_number   INTEGER NOT NULL
  item_id       INTEGER FK items(id)           -- NULL allowed: freeform line
  account_id    INTEGER FK accounts(id) NOT NULL  -- resolved from item or picked
  description   VARCHAR(512)
  quantity_milli INTEGER NOT NULL              -- quantities in thousandths
  unit_price_cents   INTEGER NOT NULL
  tax_code_id   INTEGER FK tax_codes(id)
  tax_amount_cents INTEGER NOT NULL            -- pre-computed at post time
  amount_cents  INTEGER NOT NULL               -- qty * unit_price (pre-tax)
  INDEX (invoice_id)

bills  -- identical shape, vendor side
  id, number, vendor_id, bill_date, due_date, terms, reference, memo,
  subtotal_cents, tax_total_cents, total_cents, amount_paid_cents,
  status, journal_entry_id, approved_at, approved_by
  CHECK (status IN ('draft','open','partial','paid','void'))
  -- no 'sent' on bills; they transition draft -> open on approval

bill_lines  -- identical shape to invoice_lines, vendor side
  id, bill_id, line_number, item_id, account_id, description,
  quantity_milli, unit_price_cents, tax_code_id, tax_amount_cents, amount_cents
```

**Quantities as milli-units.** `quantity_milli = 1000` means one unit. This gives 3 decimal places of precision (0.001 billable hour = 3.6 seconds), which is enough for every use case a small-business product will ever serve. Unit amounts stay integer, no floats.

**Money math**: `amount_cents = round(quantity_milli * unit_price_cents / 1000)`. Rounding happens ONCE, per line, banker's rounding. `tax_amount_cents = round(amount_cents * tax_code.rate_bps / 10000)`. The invoice totals are sums of rounded line amounts — this means `total ≠ subtotal * (1 + rate)` in general, but it is consistent with how every accounting product computes totals and reliably round-trips.

### 3.4 Payments

Payments are separate objects from invoices/bills because one payment can apply to many invoices (a customer sends a single check for three outstanding invoices) and one invoice can accept many payments (partial payment over time). The join table does the work.

```
payments
  id            INTEGER PK AUTOINCREMENT
  customer_id   INTEGER FK customers(id) ON DELETE RESTRICT NOT NULL
  payment_date  DATE NOT NULL
  amount_cents  INTEGER NOT NULL              -- positive
  deposit_account_id INTEGER FK accounts(id) NOT NULL  -- usually a bank account
  method        VARCHAR(32)                   -- 'check','ach','card','wire','cash'
  reference     VARCHAR(64)                   -- check number, confirmation
  memo          VARCHAR(1024)
  journal_entry_id INTEGER FK journal_entries(id) NOT NULL
  status        VARCHAR(16) NOT NULL          -- 'posted','void'
  CHECK (amount_cents > 0)
  CHECK (status IN ('posted','void'))
  CHECK (method IN ('check','ach','card','wire','cash','other'))

payment_applications
  id            INTEGER PK AUTOINCREMENT
  payment_id    INTEGER FK payments(id) ON DELETE RESTRICT NOT NULL
  invoice_id    INTEGER FK invoices(id) ON DELETE RESTRICT NOT NULL
  amount_cents  INTEGER NOT NULL
  discount_cents INTEGER NOT NULL DEFAULT 0    -- early-pay discounts
  writeoff_cents INTEGER NOT NULL DEFAULT 0    -- small-amount write-offs
  CHECK (amount_cents > 0)
  CHECK (discount_cents >= 0 AND writeoff_cents >= 0)
  UNIQUE (payment_id, invoice_id)

bill_payments  -- vendor side, identical shape
bill_payment_applications
```

The **unapplied portion** of a payment = `amount_cents - SUM(payment_applications.amount_cents)`. A customer who prepays has an unapplied payment; the UI shows it so future invoices can consume it. Phase 2 does not auto-apply — users pick which invoices to settle.

## 4. Sub-ledger semantics

PRD §6.4 explicitly puts AR/AP in the sub-ledger category: **the GL sees one `Accounts Receivable` total; customer-level detail lives in the AR sub-ledger**. The sub-ledger must reconcile exactly to the control account.

### 4.1 Control accounts

Three new accounts seeded automatically into every company on Phase 2 upgrade (the migration will add them to companies that already exist):

- `1200 Accounts Receivable` — asset, debit normal. All open invoice balances roll up here.
- `2000 Accounts Payable` — liability, credit normal. All open bill balances roll up here.
- `2100 Sales Tax Payable` — liability, credit normal. Default tax payable account when a user creates a tax code without specifying one.

These accounts get a `role` metadata flag so the UI can:
- Refuse to delete or deactivate them
- Hide them from the JE account picker (direct posting to a control account bypasses the sub-ledger and causes reconciliation drift — a dangerous foot-gun we explicitly disallow)

Implementation: new `accounts.role` column (nullable VARCHAR), values like `'ar_control'`, `'ap_control'`, `'sales_tax_default'`. Each value is unique per company (a CHECK + partial index enforces that).

### 4.2 Auto-posted journal entries

Every invoice/bill/payment that lands in `posted` status creates a matching `journal_entry` row linked via `invoices.journal_entry_id`. The service layer owns this; the sub-ledger tables never drift from the GL because the link is a foreign key and writes happen in the same transaction.

**Invoice post** (status `draft` → `sent`):
```
  Dr Accounts Receivable    total_cents
    Cr Revenue (per line account) subtotal_cents
    Cr Sales Tax Payable (per line tax_code.payable_account) tax_total_cents
```

**Customer payment post**:
```
  Dr Cash (or chosen deposit account) amount_cents
    Cr Accounts Receivable             amount_cents
  -- discounts/writeoffs are additional lines:
  Dr Discount Taken (expense)          discount_cents
  Dr Bad Debt Expense                  writeoff_cents
    Cr Accounts Receivable (additional) discount_cents + writeoff_cents
```

**Bill post** (mirror, vendor side):
```
  Dr Expense (per line account)        subtotal_cents
  Dr Input Tax (if applicable)         tax_total_cents
    Cr Accounts Payable                total_cents
```

**Bill payment post**:
```
  Dr Accounts Payable                  amount_cents
    Cr Cash (or chosen payout account) amount_cents
```

**Void** (the existing pattern): produces a reversing journal entry and flips the source record's `status` to `void`. The sub-ledger row stays for history; the reversal is what keeps the GL correct. This reuses the Phase 1 `void_entry` mechanics verbatim.

### 4.3 Reconciliation invariant

At any point: `SUM(open_invoice_balances) = AR_control_account_balance`. Same for AP.

Two safety nets:
1. **Tests** (Section 12): every slice's test suite includes a `reconcile_sub_ledger()` assertion after every state transition.
2. **Reconciliation report** (new): `GET /companies/{id}/reports/sub-ledger-reconciliation` returns `{ar_difference_cents, ap_difference_cents, ...}`. Non-zero means the invariant broke. In normal operation this should always be zero; the report exists as a canary.

We deliberately do NOT add a SQL trigger that enforces the invariant, because the reconciliation requires summing two different tables and triggers run per-row — this would be both slow and hard to reason about. The test suite and the canary report cover it.

## 5. Status machines

Invoice status transitions:

```
  draft ─┬─► sent ─┬─► partial ─► paid
         │         │                 │
         │         └───────────────► paid
         │
         └─► void (from any state)
```

- `draft` → `sent`: user clicks "Post" / "Send". Auto-JE fires. A posted/unpaid invoice shows `sent` until a payment applies.
- `sent` → `partial`: a payment covers some but not all of `total_cents`.
- `sent` | `partial` → `paid`: cumulative applied payments equal `total_cents`.
- Any → `void`: reverses the JE, keeps history. Payments that were applied to the voided invoice need their applications deleted or reassigned first — we refuse to void an invoice with applied payments and surface a clear 409 with the attached payment ids.

Bill status transitions:

```
  draft ─┬─► open ─┬─► partial ─► paid
         │         │                 │
         │         └───────────────► paid
         │
         └─► void (from any state)
```

- `draft` → `open`: the approval step. For companies without approval workflow enabled, posting a bill transitions directly; for those with approval, `approved_by` and `approved_at` populate on transition. The approval workflow is controlled by a new `companies.require_bill_approval` boolean (defaulting to FALSE for Dromos-scale users).
- `open` → `partial`, `open` | `partial` → `paid`: same mechanic as invoices.
- Any → `void`: same mechanic. Again, voiding a bill with applied payments requires explicit payment reassignment.

Database enforcement mirrors Phase 1 patterns: CHECK constraint on `status IN (...)`, trigger that rejects illegal transitions (e.g., `paid` → `draft`), trigger that rejects post-commit edits to key fields (customer_id, invoice_date, line amounts) on a non-draft invoice.

## 6. Basis toggle — where it finally bites

Phase 1 had a `basis=cash|accrual` query parameter on every report, with a no-op implementation (§10.3). Phase 2 is where that parameter becomes meaningful.

- **Accrual basis** (default in MVP, unchanged from Phase 1): income is recognized when the invoice posts; expenses when the bill posts. The JE dates drive everything. Reports filter on `journal_entries.entry_date`.

- **Cash basis**: income is recognized when the *payment* is received; expenses when the bill is *paid*. The JE created at invoice post doesn't count yet — only the payment's JE does.

Implementation: each of the three reports (trial balance, P&L, balance sheet) and the two aging reports learns a new "cash-basis window" path. For cash basis:
- Lines hitting Revenue or Expense accounts count only if their journal entry's `source_type IN ('payment','bill_payment')`
- Lines hitting AR or AP are zero'd out (they don't exist in cash books)
- AR/AP control balances are reported as zero on cash basis

This is a per-report SQL branch, not a schema change. Adds ~50 lines per report.

Migration `0005_basis_plumbing.py` adds a `journal_entries.basis_relevant` materialized flag (generated from source_type at write time) purely for query efficiency; the semantics live in the report code.

## 7. API surface (additive)

No breaking changes to the Phase 1 API. Everything below is new.

### Customers
```
GET    /api/v1/companies/{id}/customers?q=&include_inactive=
POST   /api/v1/companies/{id}/customers
GET    /api/v1/companies/{id}/customers/{cid}
PATCH  /api/v1/companies/{id}/customers/{cid}
POST   /api/v1/companies/{id}/customers/{cid}/deactivate
POST   /api/v1/companies/{id}/customers/{cid}/reactivate
GET    /api/v1/companies/{id}/customers/{cid}/statement?start_date=&end_date=
```

### Vendors — same shape, swap `customers` for `vendors` and `cid` for `vid`.

### Items + tax codes (S3)
```
GET    /api/v1/companies/{id}/items
POST   /api/v1/companies/{id}/items
PATCH  /api/v1/companies/{id}/items/{iid}
POST   /api/v1/companies/{id}/items/{iid}/deactivate

GET    /api/v1/companies/{id}/tax-codes
POST   /api/v1/companies/{id}/tax-codes
PATCH  /api/v1/companies/{id}/tax-codes/{tid}
```

Tax rates are never mutable once any invoice has used them — we handle rate changes by deactivating the old code and creating a new one (mirror of how real tax authorities handle rate changes). `PATCH tax-codes/{tid}` rejects `rate_bps` changes with 409; `name` is editable.

### Invoices
```
GET    /api/v1/companies/{id}/invoices?customer_id=&status=&start_date=&end_date=
POST   /api/v1/companies/{id}/invoices              -- create draft
GET    /api/v1/companies/{id}/invoices/{iid}
PATCH  /api/v1/companies/{id}/invoices/{iid}        -- drafts only
POST   /api/v1/companies/{id}/invoices/{iid}/post   -- draft -> sent
POST   /api/v1/companies/{id}/invoices/{iid}/void
DELETE /api/v1/companies/{id}/invoices/{iid}        -- drafts only

POST   /api/v1/companies/{id}/invoices/{iid}/send-pdf   -- S4 only: renders + emails
GET    /api/v1/companies/{id}/invoices/{iid}/pdf        -- S4 only: raw PDF download
```

### Payments
```
GET    /api/v1/companies/{id}/payments?customer_id=&start_date=&end_date=
POST   /api/v1/companies/{id}/payments              -- body: amount, deposit account, method, applications[]
GET    /api/v1/companies/{id}/payments/{pid}
POST   /api/v1/companies/{id}/payments/{pid}/void
POST   /api/v1/companies/{id}/payments/{pid}/applications     -- add applications
DELETE /api/v1/companies/{id}/payments/{pid}/applications/{aid}
```

### Bills + bill payments — same shape, vendor side.

### Reports (new)
```
GET    /api/v1/companies/{id}/reports/ar-aging?as_of_date=&buckets=current,1_30,31_60,61_90,over_90
GET    /api/v1/companies/{id}/reports/ap-aging?as_of_date=&buckets=...
GET    /api/v1/companies/{id}/reports/sub-ledger-reconciliation?as_of_date=
```

### Export (new)
```
GET    /api/v1/companies/{id}/export/customers.csv
GET    /api/v1/companies/{id}/export/vendors.csv
GET    /api/v1/companies/{id}/export/invoices.csv
GET    /api/v1/companies/{id}/export/bills.csv
GET    /api/v1/companies/{id}/export/reports/ar-aging.csv
GET    /api/v1/companies/{id}/export/reports/ap-aging.csv
```

JSON round-trip export gains five new top-level keys (customers, vendors, items, tax_codes, invoices, invoice_lines, payments, payment_applications, bills, bill_lines, bill_payments, bill_payment_applications). The import path grows symmetrically. Version bumps to `ledgerline_export_version: 2`; imports of v1 documents upgrade transparently (they just don't populate the new tables).

## 8. UI surface

New sidebar entries, in the order they'd appear:

- **Customers** — list + detail
- **Invoices** — list + editor + register per-invoice
- **Vendors** — list + detail
- **Bills** — list + editor
- (existing: Accounts, Journal, Register, Reports)
- **Items** — list + modal (new in S3)
- **Tax codes** — list + modal (new in S3)

### Invoice editor (core S1 surface)

The editor reuses the journal entry form's multi-line grid pattern with adaptations:

| Column | Notes |
|---|---|
| # | Line number |
| Item | Autocomplete over active items. Picking an item populates account, description, unit price, and tax code defaults. Leaving blank = freeform line. |
| Description | Freeform text; prepopulated from item |
| Qty | 3-decimal input, right-aligned, tabular |
| Rate | Dollar input, right-aligned, tabular |
| Amount | Computed read-only: qty * rate |
| Tax | Tax code dropdown. "None" is a first-class option. |
| Tax $ | Computed read-only: amount * tax rate |

Totals footer: subtotal, tax total, grand total, amount due (grand total minus any applied prepayments). Post button grays until header fields are valid (customer picked, invoice date set, due date ≥ invoice date, at least one line with positive amount).

Keyboard shortcuts within the editor (extending the Phase 1 framework):
- `Ctrl+Enter` — post invoice
- `Esc` — cancel
- `Ctrl+D` — duplicate current line
- `Alt+↑` / `Alt+↓` — reorder lines

### Invoice list

Columns: Number, Customer, Date, Due, Total, Paid, Balance, Status. Filters for customer, status, date range. Click row for detail. Export CSV link on the toolbar.

Status column coloring uses existing Phase 1 palette: `draft` muted, `sent` terracotta accent, `partial` orange, `paid` green, `void` red with strikethrough.

### Payment modal

Triggered from a customer's detail screen ("Record payment") or from an invoice ("Record payment for this invoice"). Shows:
- Amount and date + deposit account + method
- List of the customer's open invoices with their balances and an "Apply" column (sum-to-amount validation)
- Discount and write-off fields collapsed under an "Adjustments" disclosure

On submit: creates the payment, applications, JE in one atomic server call. Errors (like trying to over-apply) surface inline.

### AR aging screen

Table of customers with five bucket columns (Current / 1–30 / 31–60 / 61–90 / 90+ / Total). Rows sort by total descending by default. Click a cell to drill into the specific invoices. Cash basis / accrual toggle in the header. Export CSV button.

## 9. Migrations

Phase 2 ships **four** Alembic migrations (under `backend/alembic_company/versions/`), in numerical order. Each migration is atomic per the Devin-corrected pattern — tables and triggers in one transaction via per-trigger `op.execute(sa.text(stmt))`.

```
0002_contacts_and_tax_codes.py      (S1 & S3 prerequisite)
  + customers, vendors tables
  + tax_codes table (present but unused until S3)
  + accounts.role column (nullable)
  + accounts 1200/2000/2100 auto-seeded via data migration
  + triggers:
     - trg_accounts_control_no_delete
     - trg_accounts_control_no_direct_je
     - trg_customers_no_hard_delete_with_invoices   (deferred wiring until
       invoices table exists; see 0003)

0003_invoices_and_payments.py       (S1)
  + items table (but no service layer yet; added here so FK to it can land
    with invoices; S3 enables creation + UI)
  + invoices, invoice_lines
  + payments, payment_applications
  + triggers:
     - trg_invoices_post_auto_je                    (fires status draft->sent)
     - trg_invoices_immutable_posted                (mirror of journal_entries)
     - trg_invoice_lines_immutable_posted           (ditto line-level)
     - trg_invoices_no_delete_posted
     - trg_invoices_status_fsm                      (rejects illegal transitions)
     - trg_customers_no_delete_with_invoices        (now wired)

0004_bills_and_bill_payments.py     (S2)
  + bills, bill_lines
  + bill_payments, bill_payment_applications
  + approval columns on bills (approved_by, approved_at, companies.require_bill_approval)
  + triggers mirror of 0003, AP side

0005_basis_plumbing.py              (concurrent with any slice, pragmatic)
  + journal_entries.basis_relevant generated column / indexed flag
  + used by cash-basis report branches
```

### 9.1 Seeding the control accounts on existing companies

The 0002 migration's upgrade() runs a data migration **after** the schema changes: for every existing company database, INSERT the three control accounts if they don't already exist (keyed by code). This is idempotent — a Phase 2 upgrade on a company already using code `1200` for "Accounts Receivable" is a no-op for that row; other codes are seeded fresh.

The data migration uses Alembic's `op.get_bind()` connection and a direct INSERT with `ON CONFLICT DO NOTHING` (SQLite supports this as of 3.24).

## 10. Integrity triggers summary

Compiled list of the new triggers. All follow the Phase 1 "DB-layer is the source of truth" pattern.

| Name | Fires on | Rejects |
|---|---|---|
| `trg_accounts_control_no_delete` | DELETE accounts | Deleting any account with `role IN ('ar_control','ap_control','sales_tax_default')` |
| `trg_accounts_control_no_direct_je` | INSERT journal_lines | Inserting a line on a control-role account from a journal entry whose `source_type='manual'` |
| `trg_invoices_post_auto_je` | UPDATE OF status on invoices | Transition to `sent`/`partial`/`paid` without a non-NULL `journal_entry_id` |
| `trg_invoices_immutable_posted` | UPDATE invoices | Any column change on a non-draft invoice except allowed state transitions and `amount_paid_cents` |
| `trg_invoice_lines_immutable_posted` | UPDATE/DELETE/INSERT invoice_lines | Any modification when parent invoice is non-draft |
| `trg_invoices_no_delete_posted` | DELETE invoices | Deleting any invoice with `status != 'draft'` |
| `trg_invoices_status_fsm` | UPDATE OF status on invoices | Illegal transitions: `paid→draft`, `void→anything`, `draft→paid` without pass-through |
| `trg_customers_no_delete_with_invoices` | DELETE customers | Deleting a customer that has any invoice row |
| `trg_tax_codes_rate_immutable` | UPDATE tax_codes | Changing `rate_bps` on a tax code referenced by any posted invoice_line |
| (mirrors for bills / vendors / bill_payments on the AP side) | | |

All trigger names follow the `trg_<table>_<assertion>` convention from Phase 1. Each is created via `op.execute(sa.text(...))` in its slice's migration. No `executescript()`.

## 11. Email and PDF delivery — S4

Per the user's call: **adapter pattern**, configurable per install. Two concrete drivers ship.

### 11.1 Adapter interface

```python
class EmailDriver(Protocol):
    def send(
        self,
        *,
        to: str,
        from_address: str,
        subject: str,
        body_text: str,
        body_html: str | None,
        attachments: list[Attachment],
    ) -> EmailResult: ...
```

`Attachment` is `{filename, mime_type, bytes}`. `EmailResult` is `{id, delivered_at, driver}` where `id` is the provider's message id (SMTP has no such concept — we generate a UUID).

The adapter is selected at startup from env/config:
```
LEDGERLINE_EMAIL_DRIVER = "smtp" | "postmark" | "resend" | "disabled"
LEDGERLINE_EMAIL_FROM   = "ar@dromos.com"
# SMTP driver:
LEDGERLINE_SMTP_HOST = ...
LEDGERLINE_SMTP_PORT = 587
LEDGERLINE_SMTP_USER = ...
LEDGERLINE_SMTP_PASSWORD = ...
# Managed driver:
LEDGERLINE_POSTMARK_TOKEN = ...    # or LEDGERLINE_RESEND_TOKEN
```

`disabled` is the default — no email driver wired until the operator opts in. Phase 2 behavior when disabled: `POST .../invoices/{id}/send-pdf` returns 501 with a clear "email not configured" message. The PDF download endpoint still works regardless.

### 11.2 PDF rendering

Not a fresh dependency decision — Phase 1 has `pdf-lib`-equivalent expectations in the PRD (§7.4: "Reports and PDF → browser-native print-to-PDF plus explicit PDF export"). For invoices we take the server-side path: `weasyprint` (Python, HTML-to-PDF via Chromium-free Cairo/Pango). Template is a Jinja2 file, editable per-company in a later phase.

Single template for Phase 2: a clean, dense layout matching the Ledgerline editorial aesthetic. Line items as a proper table, totals right-aligned with tabular figures, remit-to block at the bottom.

## 12. Test strategy

Each slice gets its own test file in `backend/tests/`. Existing 56 tests stay green.

### Invariants to verify
- **Sub-ledger reconciliation**: after every state transition in every slice's tests, assert AR control balance equals sum of open invoice balances (and AP analog).
- **Status FSM**: every illegal transition test attempts it and asserts the trigger rejects with the expected message.
- **Void cascade**: voiding a paid invoice without first unapplying the payment returns 409 with the payment ids in the response.
- **Rate immutability**: changing `rate_bps` on a tax code that's been used in an invoice returns 409. Changing it on an unused code succeeds.
- **Basis toggle correctness**: a scenario with an outstanding invoice + a partial payment produces different P&L and balance-sheet totals on cash vs. accrual. Both sets of totals are verified against hand-computed expected values.

### Coverage targets per slice
- S1 (AR): 20–25 new tests (contact CRUD, invoice CRUD + post + void, payment application, AR aging correctness, sub-ledger reconciliation, cash-basis branch)
- S2 (AP): 12–15 new tests (mirror of S1; less net-new because the patterns repeat)
- S3 (items + tax): 10–12 tests (item-default propagation, tax math correctness including rounding edge cases, tax-on-zero-rate code, void cascades with tax)
- S5 (statements): 4–6 tests (statement window correctness, PDF snapshot)
- S4 (PDF + email): 6–8 tests (PDF rendering smoke, email-disabled returns 501, adapter routing, fake-driver capture)

Total Phase 2: ~55–70 new backend tests. Frontend Vitest coverage for the new forms and grids: ~15–20 tests.

### What we deliberately DON'T test at the unit level
- Specific PDF pixel layout. We snapshot byte length and assert the PDF is well-formed (pdf-reader opens it, has the expected number of pages) but not rendering fidelity.
- Real SMTP delivery. The email driver has a `fake` mode for tests that captures sent mail into an in-memory list.

## 13. Commit plan (atomic, per slice)

Following the Phase 1 commit cadence (one atomic commit per coherent unit; each commit leaves the tree green):

| Slice | Commits (approx.) |
|---|---:|
| S1 — AR one-liner | 12–15 |
| S2 — AP one-liner | 10–12 |
| S3 — Items + tax | 6–8 |
| S5 — Statements | 4–6 |
| S4 — PDF + email | 4–6 |
| **Total Phase 2** | **36–47** |

Each slice opens its own PR. The five PRs merge independently. Main stays releasable after every merge.

Suggested atomic commits for S1:

```
1.  docs: Phase 2 plan landed                              (this doc, closes #N)
2.  feat(backend): alembic 0002 contacts + tax_codes + accounts.role
3.  feat(backend): customer model + service + schemas
4.  feat(backend): customer API + CSV export
5.  feat(backend): alembic 0003 invoices + payments + triggers
6.  feat(backend): invoice model + service (create, post, void)
7.  feat(backend): payment model + service (apply, unapply, void)
8.  feat(backend): invoice API (CRUD, post, void)
9.  feat(backend): payment API (CRUD, apply, unapply)
10. feat(backend): AR aging report + endpoint
11. feat(backend): sub-ledger reconciliation canary report
12. test(backend): S1 end-to-end tests + fixtures
13. feat(frontend): customers view (list, detail, create, edit)
14. feat(frontend): invoice editor + list + detail views
15. feat(frontend): payment modal + AR aging screen
```

The estimate floats depending on whether we split editor and list (12-commit track) or combine them (10-commit track). At Phase 1 cadence either works.

## 14. Deferred to Phase 2.5+

Called out here so nobody mistakes a "not in Phase 2" item for an oversight:

- **Recurring invoices** — different data model, separate migration. PRD §10.7 lumps under "power features" / Phase 7.
- **Credit notes** — related to void but distinct (void is the whole invoice; credit note is a partial adjustment). Defer to Phase 2.5 after S1 is in users' hands.
- **Multi-currency** — PRD §15 Q6: USD-only for MVP, Phase 7+.
- **Sales-tax jurisdiction logic** — Phase 7 or an integration.
- **Inventory tracking on items** — Phase 8. Phase 2 items have an optional unit price but no quantity-on-hand. Items of type `product` can be sold but their inventory is not tracked.
- **Attachments on invoices/bills** — the attachment subsystem is scoped for Phase 1 local tier per PRD §15 Q11. Phase 2 lists a `file_attachments` nullable FK on invoices/bills but doesn't ship the UI. Receipts on bills come in Phase 3 (Banking, §9 Phase 3).
- **1099 report generation** — `vendors.is_1099` is populated in S2 but the actual 1099-NEC / 1099-MISC PDF generation is Phase 4 (Import and interop, §9 Phase 4).

## 15. Known risks and tradeoffs

- **`quantity_milli` vs. `quantity_cents`-style naming.** I picked milli (3 decimals) because a plumber quoting in half-hours never needs 4-decimal precision but often wants 0.25 hour. If Dromos's dogfooding shows 3 decimals is wasteful, drop to 2 at a future migration — cheap change.
- **Tax code immutability is strict.** Users will want to "just update the rate for 2027." We'll teach them to deactivate + create-new. If the friction is too high, add an `effective_from` / `effective_to` range to tax codes in Phase 2.5.
- **Control-account role column.** Strictly a new pattern that the Phase 1 accounts table doesn't have. The migration introduces it; all existing accounts get NULL role (fine, they're not controls). Future phases will want a `classes`/`departments` column of similar shape; we'll extend the pattern then.
- **Basis-toggle cash mode hides AR/AP entirely.** This is correct per GAAP but surprises users who expect to see their outstanding receivables on a cash-basis balance sheet. Solution: a clear banner on the report saying "Cash basis — AR and AP are not displayed." Implement once, reuse on all three basis-aware reports.
- **Invoice → JE foreign key is a strong coupling.** Alternative considered: store only the side of the invoice that's needed (the journal entry) and let the invoice be a reporting view. Rejected: user-facing UI needs the invoice as a first-class object (status, paid amount, terms) that lives longer than the JE and has its own lifecycle (edit in draft, void with reversal).

## 16. Exit criteria for Phase 2

Matches PRD §9 verbatim plus the explicit additions this plan locks in.

- ✅ A small business owner can **bill customers** (S1 + S3).
- ✅ …**record payments**, with partial, discount, and write-off handling (S1).
- ✅ …**enter vendor bills**, with optional approval (S2).
- ✅ …**pay them** (S2).
- ✅ …**see who owes them money and who they owe** (AR/AP aging, S1 + S2).
- ✅ Customer and vendor **statements** generate and download (S5).
- ✅ Invoices **render as PDF** and optionally **email** to the customer (S4).
- ✅ **Sub-ledger reconciliation invariant** holds at all times, enforced by test suite + canary report.
- ✅ **Cash vs. accrual toggle** works correctly on all three financial reports.
- ✅ CI passes on every slice's PR before merge.
- ✅ Alembic migrations for Phase 2 are clean upgrades on an existing Phase 1 company database (no data loss, control accounts auto-seeded).

Phase 2 exit unlocks Phase 3 (Banking and reconciliation) as the next chapter.

---

*End of Phase 2 plan v0.1. Update as slices ship and reality pushes back.*
