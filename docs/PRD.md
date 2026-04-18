# PRD: Double-entry accounting platform

**Author:** Matthew Walkup
**Last updated:** 04/18/2026
**Status:** Draft v0.1

---

## 1. Summary

This document specifies a double-entry accounting application built as a web app first, with Mac and Windows desktop clients to follow. The product is deliberately lean, fast, and keyboard-friendly. Function is prioritized over visual polish. Data is owned by the user and portable by design.

The build is phased. The MVP ships a small, sharp core: chart of accounts, manual journal entries, and the three primary financial reports. Each subsequent phase adds one coherent module (AR, AP, banking, Plaid, inventory, and so on). Payroll is a stretch goal, not a core deliverable.

## 2. Problem statement

Current accounting software falls into two camps, and both have drifted away from what bookkeepers and small business owners actually need:

1. **Cloud SaaS accounting platforms.** Slow, increasingly bloated, heavy on upsells, and the user does not own their data. Performance has regressed over the past decade. Data export is often intentionally painful. Recurring subscription costs add up over the life of a business.
2. **Consumer-grade tools and spreadsheets.** Fast to start with, but they break down at modest complexity. Reports are limited, audit trails are weak, and double-entry rigor is often absent or optional.

There is room for a product that behaves like desktop accounting software from the era when it was still built for the user: fast, dense, keyboard-driven, and respectful of the operator's time. The product should be web-accessible so it is not tied to a single machine, but should run locally when possible so it stays fast and works without a network connection.

## 3. Target users

Primary users for v1, in priority order:

1. **Small business owners doing their own books.** 1 to 20 employees. Service businesses, trades, small retail, small medical practices. They need AR, AP, banking, and basic reports. They do not need deep inventory, multi-currency, or payroll (initially).
2. **Freelancers and solopreneurs.** Single-user, cash or accrual basis, minimal AR/AP volume, but they need clean books for tax time and for submitting loan applications.

Deferred until post-MVP:

3. **Bookkeepers managing a small book of clients.** Power users and ideal long-term customers, but their workflow depends on payroll being present. Bookkeepers typically handle or coordinate payroll for their clients, and a product without it is a non-starter for most of them. Revisit once Phase 9 (or a payroll integration bridge) is on the table.

Non-targets (at least in v1):

- Mid-market companies with formal controls, multi-entity consolidation, or audit committee requirements
- Manufacturers with work-in-progress inventory
- Companies with commissioned sales teams
- Multi-country operations requiring statutory reporting

## 4. Goals and non-goals

### Goals

1. Ship a working MVP with rigorous double-entry integrity.
2. Sub-100ms interaction latency for common operations (opening a register, searching transactions, generating a P&L).
3. Full CSV and JSON export of every piece of data the user has entered. Always. No paywall.
4. Full import from common sources (CSV, OFX, QIF, IIF) by Phase 4.
5. Desktop parity with web by Phase 6. Same database format, same file layout, data portable between them.
6. Keyboard-first workflows for every high-volume task (data entry, reconciliation, reporting).
7. Audit trail: no hard deletes. Transactions are voided or reversed, never erased.

### Non-goals

1. Visual design that competes with consumer SaaS. Function over form.
2. Mobile-first experience. A responsive web view is acceptable; native mobile apps are not in scope.
3. Payroll. Complex, regulated, and a treadmill of tax table updates. Explicitly out of scope until the core product is stable and profitable.
4. Real-time collaborative editing across multiple users on the same transaction. Pessimistic locking or last-write-wins is acceptable.
5. Full ERP features (MRP, CRM, project management beyond basic job costing).

## 4.1 Commercial model

The product is sold under a hybrid model:

| Tier | Price | Includes |
|------|-------|----------|
| Local (one-time) | Flat purchase price | The app, local database, all core modules, 1 year of updates and support |
| Cloud (monthly) | Subscription | Hosting, sync across devices, multi-user, ongoing updates and support |
| Self-hosted | One-time setup fee | Install on customer infrastructure; updates and support require an ongoing maintenance plan |

Key principles:

- **Local tier is fully self-contained.** Native install (web app or Electron wrapper), single user, local SQLite storage, zero cloud dependency, zero Docker dependency, fully offline-capable for the life of the install. Users who never touch the network can still use the product.
- Users who buy the local tier and never renew still keep a working copy of the software forever. Updates and support are what lapse, not the license. All features remain functional.
- Self-hosting exists primarily as a data sovereignty option for users who cannot or will not put their books in someone else's cloud. The self-hosted tier runs the server stack (app + database) and requires container orchestration or equivalent; it is not the same as the local tier.
- Updates and support are bundled. There is no "pay for support but not updates" or vice versa.

### 4.1.1 Renewal economics (local tier)

There is no technical license enforcement. The renewal model uses price incentives, not DRM:

| Renewal timing | Price | Coverage period |
|----------------|-------|-----------------|
| Before 1-year expiry | Deep discount (target ~75% off list) | Starts at prior expiry date |
| Within 90 days after expiry | Same deep discount | Backdates to prior expiry date (no free gap) |
| More than 90 days after expiry | Full list price (re-purchase) | Starts at purchase date |

The backdating rule prevents users from letting coverage lapse intentionally to effectively skip a year. The 90-day grace window absorbs forgetful-but-willing customers without punishing them. Beyond 90 days, the user has signaled they are not a continuing customer and re-onboarding at full price is fair.

This approach assumes the target customer pays for value received and needs real support. Piracy is not a priority threat for this product category.

## 5. Product principles

These are the rules the project uses to settle disputes about scope, design, and prioritization.

1. **Function over form.** Dense information displays, minimal chrome, keyboard shortcuts for everything. The design system is plain and readable. No animations that cost more than 100ms.
2. **The user owns the data.** Export is a first-class feature, not an escape hatch. File format is documented. No lock-in.
3. **API-first, developer-friendly, no vendor lock-in.** Every feature is exposable via API, not UI-only. The cloud tier provides user-provisioned API keys. The self-hosted tier provides the same API by default. OpenAPI specification is a first-class deliverable. Third-party developers can build on the platform without begging for access.
4. **Local-first wherever practical.** The web app runs against a client-side database when it can. Sync is a feature, not a requirement. Offline work is a first-class mode.
5. **Double-entry is non-negotiable.** Every transaction balances. No "simplified" modes that let debits and credits drift apart. Integrity is enforced at the database layer, not the UI.
6. **No hard deletes.** Voiding, reversing, and reclassifying are the only edit paths for posted transactions. Every change leaves a trail.
7. **Small, complete modules.** A module is not shipped until it is fully usable for real-world work. No half-built features hidden behind flags.

## 6. Core accounting concepts

This section establishes the terminology and integrity rules the rest of the document relies on. Anyone contributing to the project should understand these.

### 6.1 The accounting equation

Assets = Liabilities + Equity. Every transaction preserves this. The sum of debits equals the sum of credits on every posted journal entry.

### 6.2 Account types

Five top-level account types, each with a normal balance side:

| Type | Normal balance | Examples |
|------|----------------|----------|
| Asset | Debit | Cash, AR, Inventory, Equipment |
| Liability | Credit | AP, Credit cards, Loans |
| Equity | Credit | Owner contributions, Retained earnings |
| Income | Credit | Sales, Service revenue, Interest income |
| Expense | Debit | Rent, Payroll, Utilities, COGS |

Account subtypes (Current Asset, Fixed Asset, etc.) are supported but not required for MVP reports.

### 6.3 Journal entries

The atomic unit of the general ledger. A journal entry has:

- A date (the effective date, which may differ from the entered date)
- A reference or memo
- Two or more lines, each with an account, a debit amount, and a credit amount (one of which is zero)
- A total debit equal to the total credit

Every feature in the product that records financial activity ultimately produces journal entries. An invoice is a journal entry. A bill is a journal entry. A bank transfer is a journal entry. The UI hides this from casual users, but power users can always see the underlying JE.

### 6.4 Sub-ledgers

AR and AP are sub-ledgers that roll up to control accounts in the GL. The AR sub-ledger tracks customer-level detail; the GL only sees a single Accounts Receivable total. Same for AP. This keeps the GL clean and makes customer-level aging reports tractable.

### 6.5 Period close

Periods (typically months) can be closed. Closing a period locks it against further edits. Adjusting entries after close are only permitted via a formal "reopen period" action that is logged.

### 6.6 Audit trail

Every posted transaction has an immutable history. Voids and reversals create new entries; they do not modify or remove the original. The audit log records who did what and when for every entry, edit, void, reconciliation, and period action.

## 7. Architecture

### 7.1 High-level shape

```
Web browser (web app)     Electron (Mac/Windows)
       |                         |
       +------------+------------+
                    |
          Application layer
      (same code, same DB schema)
                    |
          Local database (SQLite)
                    |
          Sync service (optional)
                    |
           Remote server / backup
```

The same application runs in three environments: browser, macOS Electron app, Windows Electron app. All three use the same database schema. Desktop apps write to a local file. The web app writes to a client-side SQLite database (via WASM + OPFS) with optional sync to a cloud backup.

### 7.2 Local-first strategy

Local-first is a decision with significant downstream consequences. Making it from day one avoids a painful retrofit later. The approach:

1. **Client-side SQLite in the browser.** SQLite compiled to WASM, backed by the Origin Private File System (OPFS) for persistence. This gives the web app a real relational database that survives refreshes and works offline.
2. **Sync as an optional layer.** For the MVP, sync is not required. Users can export and manually move data between devices. In a later phase, add a sync server that handles conflict resolution (likely via a last-write-wins plus change-log approach, given that accounting data is mostly append-only once posted).
3. **Electron reuses the same layer.** The Electron app uses native SQLite instead of WASM, but the schema and query layer are identical. Data files are portable: a .db file from Electron opens in the browser, and vice versa.

The alternative (server-first with a Postgres backend, retrofit local later) was considered and rejected. Retrofitting local-first is expensive and tends to produce compromises. Committing now is the cheaper path.

### 7.3 Multi-company, multi-user

- **Multi-company:** Each company is its own SQLite database file. Switching companies means opening a different file. This is clean, portable, and maps to how bookkeepers think about client books.
- **Multi-user:** Not in MVP. When added, it is scoped per-company with role-based permissions (Owner, Bookkeeper, Read-only, etc.).

### 7.4 Technology stack (proposed)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Frontend framework | Svelte + SvelteKit | Smaller runtime than React, faster interactions, less ceremony. Aligns with "lean and fast." |
| UI approach | Minimal Tailwind plus custom components | Avoid heavy component libraries. Keyboard accessibility is easier with less abstraction. |
| Client database | SQLite via wa-sqlite or the official SQLite WASM build, backed by OPFS | Real SQL, real transactions, real FK constraints. No NoSQL compromises. |
| Desktop wrapper | Electron | Honest choice. Tauri is lighter but the SQLite plus native filesystem story is less mature. Revisit for v2. |
| Sync (Phase 4+) | Custom sync server, Go or Rust, Postgres on the backend | Defer this decision until it is actually needed. |
| Reports and PDF | Browser-native print-to-PDF plus explicit PDF export via pdf-lib or similar | No server-side rendering required. |
| Authentication (cloud) | Email plus password, passkey-ready; no OAuth on the core app | Defer complexity. |

Alternatives explicitly considered:

- **React instead of Svelte.** Bigger ecosystem, but heavier and not aligned with the speed principle.
- **Tauri instead of Electron.** Smaller binaries, but SQLite and filesystem maturity still lag. Revisit.
- **IndexedDB instead of SQLite.** Rejected. Double-entry integrity is much cleaner with real SQL transactions and foreign keys.
- **Postgres-first architecture.** Rejected as above; retrofit is painful.

## 8. Data model

The schema below is the MVP shape. It expands in later phases.

### 8.1 Core tables (MVP)

```
companies
  id, name, fiscal_year_start, base_currency, created_at, ...

accounts  (chart of accounts)
  id, company_id, code, name, type (asset|liability|equity|income|expense),
  subtype, parent_id (for hierarchy), is_active, description

journal_entries
  id, company_id, entry_date, posting_date, reference, memo,
  source_type (manual|invoice|bill|payment|...), source_id,
  status (draft|posted|void), created_by, created_at

journal_lines
  id, journal_entry_id, account_id, debit_cents, credit_cents,
  memo, line_number

audit_log
  id, company_id, actor, action, entity_type, entity_id,
  before_json, after_json, timestamp
```

Integrity rules enforced at the DB layer:

- Every `journal_entry` with status `posted` must have matching total debits and credits across its `journal_lines`. Enforced via a trigger that rejects inserts and updates that violate this.
- `journal_lines.debit_cents` and `journal_lines.credit_cents` are each non-negative; exactly one is zero per line.
- Amounts are stored in cents (integer) to avoid floating-point errors.
- Posted journal entries are immutable. Updates are rejected at the DB layer.

### 8.2 Tables added in Phase 2 (AR/AP)

```
customers
vendors
items          (products and services sold or purchased)
invoices       (with invoice_lines)
bills          (with bill_lines)
payments       (customer payments applied to invoices)
bill_payments  (payments applied to bills)
```

### 8.3 Tables added in Phase 3 (Banking)

```
bank_accounts
bank_transactions
reconciliations
reconciliation_items
```

### 8.4 Tables added in later phases

Inventory, classes and departments, jobs, recurring transactions, Plaid link metadata, multi-currency rates, and so on. Specified in the relevant phase sections below.

## 9. Phased roadmap

Each phase ships a complete, usable product. No phase is "half a feature."

### Phase 0: Foundation (4 to 6 weeks)

- Project setup, build pipeline, CI
- Database schema for Phase 1, with triggers for double-entry integrity
- Company creation and selection UI
- Base application shell (navigation, keyboard shortcut framework, toast system)
- Settings: company info, fiscal year, base currency

**Exit criteria:** A user can create a company, see the empty shell, and the schema passes integrity tests for double-entry.

### Phase 1: MVP core (8 to 12 weeks)

- Chart of accounts (default template plus full CRUD)
- Manual journal entry: create, post, void
- General ledger view (per account, with running balance)
- Trial balance report
- Profit and loss report (cash and accrual basis)
- Balance sheet report
- CSV export of every list view
- Full JSON export of the company database

**Exit criteria:** A bookkeeper can open the product, set up a chart of accounts, post a month of transactions manually, and produce a correct trial balance, P&L, and balance sheet. Export works for all three.

### Phase 2: AR and AP (8 to 10 weeks)

- Customers and vendors (CRUD, notes, contact info)
- Items (products and services) with default income and expense accounts
- Invoices: create, send (as PDF), record payment, void
- Bills: enter, approve, record payment, void
- AR aging report
- AP aging report
- Customer and vendor statements

**Exit criteria:** A small business owner can bill customers, record payments, enter vendor bills, pay them, and see who owes them money and who they owe.

### Phase 3: Banking and reconciliation (6 to 8 weeks)

- Bank and credit card accounts
- Manual transaction entry with transfer support
- CSV and OFX/QFX import
- Match imported transactions against existing entries
- Classify unmatched transactions (rules engine)
- Reconciliation workflow (statement balance, cleared items, end-of-statement confirmation)
- Bank reconciliation report

**Exit criteria:** A user can import a month of bank transactions, categorize them, match them against existing entries, and reconcile the account to a statement.

### Phase 4: Import and interoperability (4 to 6 weeks)

- QIF import
- IIF import and export
- Tax-ready exports (Schedule C categorization hints, 1099 reports)
- Document attachment to transactions (receipts, bills)
- Import wizards from common competing products via CSV intermediaries

**Exit criteria:** A user migrating from another product can bring their existing data in without manual re-entry for the vast majority of common cases.

### Phase 5: Plaid integration (4 to 6 weeks)

- Plaid Link flow
- Daily transaction sync
- Duplicate detection against manually imported data
- Automatic categorization rules based on merchant and prior classifications
- Failure and reauthentication handling

**Exit criteria:** A user can connect a bank account via Plaid, see transactions appear automatically, and have them categorized based on rules.

### Phase 6: Desktop apps (6 to 8 weeks)

- Electron wrapper for macOS (universal binary)
- Electron wrapper for Windows
- Native file picker for company database files
- Automatic updates
- Native menu integration
- Feature parity with web app

**Exit criteria:** A user can install the Mac or Windows app, open a database file, and have the identical experience they had in the browser.

### Phase 7: Reporting and power features (ongoing)

- Custom report builder
- Classes and departments (tracking categories)
- Jobs and basic job costing
- Budgeting and budget vs. actual reports
- Recurring transactions
- Bulk edit tools

### Phase 8: Inventory (8 to 10 weeks, if pursued)

- Inventory items with cost methods (FIFO, average cost)
- Purchase orders
- Inventory adjustments
- Cost of goods sold automation

### Phase 9: Payroll (explicitly deferred, possibly never)

Ongoing tax table maintenance makes this a significant ongoing commitment. Third-party integration (Gusto, Rippling, or similar) via an import bridge is a lighter alternative and should be evaluated before considering native payroll.

## 10. Module specifications

This section expands the MVP and Phase 2 modules in more detail. Later phases will be specified in follow-on documents once Phase 1 is shipped and the product has real users.

### 10.1 Chart of accounts

**Views:**
- List view: tree or flat, with account code, name, type, balance, and active flag
- Detail view: account properties, register (list of transactions affecting the account), running balance

**Operations:**
- Create, edit (name, subtype, description only), deactivate
- Accounts with posted transactions cannot be deleted, only deactivated
- Default templates per business type (service, retail, trades, medical) loadable at company creation

**Keyboard:**
- New account: N
- Search: / or Ctrl+F
- Open register for selected: Enter

### 10.2 Journal entries

**Views:**
- List: recent entries, filterable by date, account, memo, reference
- Detail: header, lines, audit info, source (if generated by another module)

**Operations:**
- Create, edit (drafts only), post, void
- Voiding creates a reversing entry; the original is preserved
- Posted entries cannot be edited, only voided
- Adjusting entries flagged with a special type for period-end

**Keyboard:**
- New entry: Ctrl+J
- Post: Ctrl+Enter
- Void: Ctrl+Shift+V
- Next line: Tab; previous: Shift+Tab

### 10.3 Reports (MVP set)

All reports support:

- Date range picker with standard presets (This Month, Last Month, YTD, Last Year, etc.)
- Cash or accrual basis toggle
- Drill-down from any total to the underlying transactions
- Export to CSV and PDF
- Comparison column (prior period, prior year)

**Trial balance:** All accounts with non-zero balances as of a date. Debit and credit columns. Totals balance.

**Profit and loss:** Income and expense sections, net income at the bottom. Groups by account type and subtype. Supports filter by class or department in later phases.

**Balance sheet:** Assets, Liabilities, Equity. The balance sheet equation holds; if not, surface a clear warning with a one-click fix (typically a missing closing entry).

### 10.4 Customers and vendors (Phase 2)

- Standard contact fields (name, company, billing address, shipping address, email, phone, tax ID)
- Default terms (Net 30, etc.)
- Default income account (customers) or expense account (vendors)
- Transaction history per contact
- Statement generation
- Inactive flag (preserves history, removes from dropdowns)

### 10.5 Invoices (Phase 2)

- Header: customer, invoice date, due date, terms, reference
- Line items: item, description, quantity, rate, amount, tax code, class (when enabled)
- Sub-totals, tax totals, grand total
- Email as PDF directly from the app (SMTP config at the company level)
- Payment application: partial payments, early payment discounts, write-offs
- Status: Draft, Sent, Partial, Paid, Void, Overdue

### 10.6 Bills (Phase 2)

- Header: vendor, bill date, due date, terms, reference
- Line items: expense account or item, description, amount, class (when enabled), billable flag
- Attachments: scanned bill, receipt
- Approval workflow (optional): Draft to Approved to Paid
- Status: Draft, Open, Partial, Paid, Void, Overdue

### 10.7 Banking (Phase 3)

Discussed in Phase 3 above. Key point: the bank register is a first-class view, not buried in a menu. Power users live in the register.

## 11. Import and export

This section exists because import and export is often an afterthought in accounting products, and that is the exact failure mode this product avoids.

### 11.1 Export (MVP, mandatory)

- CSV export from every list view, using the exact filters currently applied
- Full company backup as a JSON file (complete schema dump, round-trip safe)
- Full company backup as a zipped SQLite file (portable to the desktop app)
- PDF export for all reports

### 11.2 Import (phased)

| Format | Phase | Notes |
|--------|-------|-------|
| CSV (bank transactions) | 3 | Mapped to bank register |
| OFX / QFX | 3 | Bank and credit card imports |
| QIF | 4 | Older format, still common |
| IIF | 4 | Round-trip for legacy exports |
| JSON (this product's own format) | 1 | For restores and migration between companies |

## 12. Security and compliance

- At-rest encryption for the local database (user-controlled password for the company file)
- In-transit encryption for sync and any cloud features (TLS)
- Audit log is append-only and exportable
- No cloud storage of company data by default; cloud sync is opt-in
- Plaid credentials stored only on the sync server when that feature is active; never on the client
- Regular third-party security review before the product handles real Plaid data or cloud sync

## 13. Desktop strategy

- Electron wrapper shares 100% of the web app code
- macOS: universal binary, notarized, distributed outside the App Store initially to avoid sandboxing friction
- Windows: signed installer
- Auto-update via electron-updater, with explicit user opt-out
- Database file lives wherever the user wants. Default location is sensible per OS.
- File associations: double-clicking a company database file opens the app

The desktop app is not a separate product; it is the web app with native packaging and filesystem access.

## 14. Success metrics

Early-stage metrics (first 12 months):

- Time to first posted journal entry after signup: under 10 minutes
- MVP user retention at 90 days: 40% or higher
- Report generation time for a 1-year dataset: under 1 second
- CSV export of a 10,000-row register: under 3 seconds
- Support ticket volume per active user per month: fewer than 0.2

Product-market fit signal: bookkeepers managing multiple client books adopt the product for at least one client voluntarily.

## 15. Open questions

Questions raised during scoping. Each was either resolved in discussion or remains open as a deliberate deferral.

### Resolved

1. ~~**Pricing model.**~~ Resolved 04/18/2026: hybrid. Local = one-time purchase with 1 year of updates and support. Cloud (hosting, sync, multi-user) = monthly subscription. Self-hosted = one-time setup fee with ongoing maintenance plan for updates and support. See section 4.1.
2. ~~**Go-to-market.**~~ Resolved 04/18/2026: SMB owners and freelancers for v1. Bookkeepers are deferred until payroll (or a payroll integration bridge) is available.
3. ~~**Cloud sync timing.**~~ Resolved 04/18/2026: defer to post-Phase 4. Launch local-only, add cloud sync and multi-user as a new phase (tentatively Phase 5) between import/interop and Plaid. Plaid needs a backend anyway, so sync infrastructure compounds. Full roadmap renumber in v0.2.
4. ~~**Default accounting basis.**~~ Resolved 04/18/2026: accrual-underneath, with both views available. Specifics:
   - All transactions are stored on an accrual basis. AR/AP transactions carry both an invoice/bill date and a payment date; the data model preserves both.
   - Every financial report (P&L, balance sheet, general ledger) has a basis toggle (cash or accrual). Users can flip freely for ad-hoc viewing and what-if analysis. No change to company settings required.
   - The company record holds a "tax basis" metadata field that labels the user's official filing basis. It controls defaults for exports and tagged reports, but does not restrict which views a user can run.
   - Changing the tax basis setting requires an explicit confirmation flow with warnings: (a) the software change does not constitute an IRS-recognized change, (b) the user is responsible for filing Form 3115 or equivalent, (c) prior period reports continue to reflect the prior basis. The change is logged in the audit trail.
   - In Phase 1 (manual JEs only), the distinction is moot because invoice and payment dates collapse to the same date. The toggle becomes meaningful starting Phase 2.
5. ~~**Entity and tax support.**~~ Resolved 04/18/2026: Schedule C and S-corp for v1. Both entity types get proper default chart of accounts, equity handling, and year-end close flows:
   - **Schedule C:** Owner's Equity, Owner's Draw, Retained Earnings. Close flow rolls Net Income to Retained Earnings and closes Owner's Draw to Owner's Equity.
   - **S-corp:** Common Stock, Additional Paid-In Capital (APIC), Shareholder Distributions, Retained Earnings. Close flow handles distributions separately. Accumulated Adjustments Account (AAA) supported as optional memo-tracking in MVP; formal AAA ledger comes later.
   - Dromos Inc. (S-corp) is the internal testbed. Dogfooding starts at Phase 1 exit.
   - C-corp and partnership are deferred to Phase 7+.
6. ~~**Multi-currency.**~~ Resolved 04/18/2026: USD only for MVP. Multi-currency is explicitly out of scope until Phase 7 or later. The data model stores amounts in the company's base currency; adding multi-currency later requires migration work, acknowledged as technical debt.
7. ~~**API strategy.**~~ Resolved 04/18/2026 (raised by Matthew during multi-currency discussion): the product is API-first by design. Now a core product principle (section 5). Specifics:
   - Every feature in the product is exposable via a documented API. No feature exists that is UI-only.
   - The cloud tier allows users to provision and manage their own API keys with scoped permissions.
   - Self-hosted deployments expose the same API by default. Users control authentication.
   - OpenAPI 3.x specification is published and versioned alongside the product.
   - Webhooks for significant events (transaction posted, reconciliation completed, invoice paid, etc.) are a Phase 5 deliverable alongside the cloud backend.
   - The local-only tier does not expose an external API (no server), but the client-side query layer is documented for anyone building their own tooling against the SQLite file.
8. ~~**License enforcement.**~~ Resolved 04/18/2026: honor system, no technical DRM. Renewal economics handle retention (see section 4.1.1). Deep discount for on-time and within-grace renewals; backdating prevents gaming; lapsed >90 days requires full re-purchase.
9. ~~**Self-host distribution format.**~~ Resolved 04/18/2026: Docker Compose bundle at launch. Bare installer considered only if demand proves it out. Self-host audience is technically capable by definition; bare installers for multi-component servers (app + Postgres + reverse proxy) are a disproportionate support burden.
10. ~~**File format stability.**~~ Resolved 04/18/2026: schema locks at public MVP release (end of Phase 1). From Phase 0 onward, every schema change ships with an automated migration script. Pre-public, Matthew (Dromos) is the sole real user and eats the migration dogfood, which surfaces pain early. Export/import remains a first-class feature as a safety net, not the migration path.
11. ~~**Attachment storage.**~~ Resolved 04/18/2026: metadata in the database (hash, filename, size, mime type, pointer), bytes in storage. Storage backend is pluggable:
    - Phase 1 to 4 (local tier): filesystem folder beside the DB file. Pointer format `file://./attachments/...`
    - Phase 5 (cloud and self-hosted tiers): object storage with a pluggable provider. Native support for AWS S3, Google Cloud Storage, Azure Blob Storage, MinIO, Cloudflare R2, Backblaze B2, and local filesystem. Implementation via a provider-agnostic abstraction (e.g., Apache Arrow's `object_store` for Rust, or equivalent in the chosen backend language). Dromos deploys against GCS natively; self-hosters choose their own backend.
    - The DB pointer field evolves across phases (`file://` to `s3://` or `gs://`) but the metadata schema does not. Phase 5 is a storage-backend swap, not a schema migration.
    - This design matches product principle 3 (no vendor lock-in): the product does not mandate a specific cloud storage provider.

### Open

12. **Naming and branding.** Product name is TBD. Domain, trademark search, and positioning are prerequisites before public launch. Not blocking on technical work; can be resolved anytime before Phase 1 exit.

## 16. Glossary

| Term | Definition |
|------|------------|
| Journal entry (JE) | A single balanced accounting transaction, composed of two or more lines |
| General ledger (GL) | The master record of all posted journal entries |
| Sub-ledger | A detailed ledger (AR, AP, inventory) that rolls up to a control account in the GL |
| Chart of accounts (CoA) | The structured list of all accounts in use for a company |
| Trial balance | A report listing every account with its debit or credit balance as of a date |
| Reconciliation | The process of matching recorded transactions against an external statement (typically a bank statement) |
| Posting | The act of committing a journal entry to the ledger, making it permanent |
| Void | Marking a posted entry as invalid via a reversing entry; the original is preserved |
| Period close | Locking a date range against further edits |
| Local-first | An architectural approach where the local client holds the primary copy of the data and sync is optional |

---

*End of PRD v0.1.*
