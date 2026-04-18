# Ledgerline

A lean, keyboard-first double-entry accounting platform. Fast, portable, and respectful of the operator's time.

## What's here

This repo tracks the **Phase 0 + Phase 1 MVP** from the PRD:

- Chart of accounts (CRUD, deactivate, templates for Schedule C service/retail and S-corp)
- Manual journal entries (create → post → void-via-reversal)
- Per-account register with running balance
- Trial balance, Profit & Loss, Balance Sheet (with basis toggle and prior-period comparison)
- CSV export of every list and report
- Full-company JSON export + round-trip-safe import
- FastAPI + SQLAlchemy 2 + SQLite backend, React + TypeScript + Vite + Tailwind frontend
- Minimal Electron shell that spawns the backend and loads the UI
- Double-entry integrity enforced at the **database layer** via SQL triggers — posted entries are immutable, balances are checked on transition, no hard deletes.

See [docs/PRD.md](docs/PRD.md) for the full product specification.

## Architecture

The Python backend is the single source of truth across all three tiers:

| Tier         | Runtime                                                                        |
| ------------ | ------------------------------------------------------------------------------ |
| Local        | Electron spawns FastAPI on localhost. SQLite file per company. Fully offline.  |
| Cloud        | Same FastAPI, hosted. Multi-user, sync (Phase 5+).                             |
| Self-hosted  | Same FastAPI, Docker Compose bundle. Your infrastructure.                      |

```
┌─────────────────────────┐        ┌─────────────────────────┐
│  React + TS UI          │  HTTP  │  FastAPI                │
│  Vite + Tailwind        │◄──────►│  SQLAlchemy 2           │
│  TanStack Query         │        │  Pydantic 2             │
└─────────────────────────┘        └───────────┬─────────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │  SQLite (per        │
                                    │  company file)      │
                                    │  + triggers enforce │
                                    │  double-entry       │
                                    └─────────────────────┘
```

- **Multi-company**: each company is its own SQLite file. Switching companies means opening a different file. Files are portable between tiers.
- **Integrity**: per-line CHECK constraints (non-negative, exactly-one-side), plus triggers that enforce debits = credits on post, reject edits to posted entries, reject hard deletes, and make the audit log append-only.
- **API-first**: every feature is exposed by a documented HTTP endpoint. OpenAPI spec at `/openapi.json`, Swagger UI at `/docs`.

## Repository layout

```
ledgerline/
├── backend/         FastAPI + SQLAlchemy 2 + SQLite
│   ├── app/
│   │   ├── main.py          App factory, /health, OpenAPI
│   │   ├── config.py        Settings (env-driven)
│   │   ├── db/              Engines, sessions, schema bootstrap, triggers
│   │   ├── models/          ORM models (Company, Account, JournalEntry, AuditLog)
│   │   ├── schemas/         Pydantic request/response
│   │   ├── services/        Business logic (post/void, CoA seeding, import/export)
│   │   ├── api/             FastAPI routers
│   │   ├── reports/         Trial balance, P&L, balance sheet
│   │   ├── export/          CSV and JSON exporters
│   │   └── seed/            Default chart-of-accounts templates
│   ├── tests/               pytest (56 tests, all green)
│   └── Dockerfile           Multi-stage build for self-hosted/cloud tiers
├── frontend/        React + TS + Vite + Tailwind
│   ├── src/
│   │   ├── api/             Typed API client + money helpers
│   │   ├── views/            Companies, Accounts, Journal, Register, Reports
│   │   ├── components/      Layout shell
│   │   └── hooks/            useSelectedCompany
│   └── vite.config.ts       Dev server + /api proxy
├── electron/        Minimal shell: spawn FastAPI + load UI
├── docs/            PRD
├── docker-compose.yml    Self-hosted bundle
├── Makefile              `make install`, `make dev-*`, `make test`, `make lint`
└── .github/workflows/    CI (pytest matrix + frontend typecheck + build)
```

## Quick start

Prerequisites: Python 3.9+, Node 20+, pnpm, make.

```bash
# Install everything (creates backend/.venv and frontend/node_modules)
make install

# Run the three processes in three terminals
make dev-backend        # FastAPI on http://localhost:8787
make dev-frontend       # Vite on http://localhost:5173 (proxies /api to 8787)
make dev-electron       # Electron window loading the Vite dev server

# Tests + lint
make test
make lint
```

The frontend opens on `http://localhost:5173`. Swagger UI is at `http://localhost:8787/docs`.

## Self-host

```bash
docker compose up -d
# Ledgerline runs on :8787. Mount your own reverse proxy with TLS in front.
# Data persists in the `ledgerline_data` named volume.
```

See `docker-compose.yml` for configuration knobs (`LEDGERLINE_CORS_ORIGINS` is the one you'll want to set for your domain).

## Design principles

(Verbatim from [docs/PRD.md](docs/PRD.md) §5.)

1. **Function over form.** Dense information displays, keyboard shortcuts, no animation that costs more than 100ms.
2. **The user owns the data.** CSV and JSON export are first-class. File format is documented. No lock-in.
3. **API-first.** Every feature is exposable via a documented API. OpenAPI spec ships with the product.
4. **Double-entry is non-negotiable.** Integrity is enforced at the database layer, not the UI.
5. **No hard deletes.** Voids and reversals only. Every change leaves a trail.

## Phase 1 status

**Shipped** (what's in this repo):

- ✅ Company creation with CoA template selection
- ✅ Chart of accounts (CRUD, deactivate, activate)
- ✅ Journal entries (create draft, post, void via reversal)
- ✅ Per-account register with running balance
- ✅ Trial Balance, P&L, Balance Sheet reports
- ✅ CSV export for every list view and every report
- ✅ Full-company JSON export + round-trip-safe import
- ✅ Double-entry integrity enforced at DB layer (SQL triggers + CHECK constraints)
- ✅ Append-only audit log
- ✅ OpenAPI 3 spec auto-generated at `/openapi.json`
- ✅ Electron shell for the local tier
- ✅ Docker Compose bundle for self-hosting
- ✅ CI: pytest matrix (Py 3.9, 3.11, 3.12), ruff, frontend typecheck + build

**Deferred**:

- Alembic migrations (currently `create_all` with a `schema_version` table — retrofit scheduled for Phase 1 exit per PRD §15 Q10)
- Keyboard-shortcut framework (stubs present in the UI; global bindings land in a follow-on)
- AR/AP, banking, Plaid, desktop polish, inventory, payroll — PRD Phases 2–9

## License

MIT — see [LICENSE](LICENSE).
