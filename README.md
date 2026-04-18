# Ledgerline

A lean, keyboard-first double-entry accounting platform. Fast, portable, and respectful of the operator's time.

## What it is

Ledgerline is a double-entry accounting application built for small business owners, freelancers, and — eventually — bookkeepers. It ships as:

| Tier          | Runtime                                                                     |
| ------------- | --------------------------------------------------------------------------- |
| Local         | Electron bundles FastAPI on localhost. SQLite file-per-company. Offline.    |
| Cloud         | Same FastAPI, hosted. Sync, multi-user.                                     |
| Self-hosted   | Same FastAPI, Docker Compose bundle. Your infrastructure.                   |

The Python backend is the single source of truth across all three tiers. The UI is a React + TypeScript app that talks to the API over HTTP — whether that API is running on localhost inside Electron, on our cloud, or inside a customer's Docker host.

## Principles

1. **Function over form.** Dense information displays, keyboard shortcuts, no animation that costs more than 100ms.
2. **The user owns the data.** CSV and JSON export are first-class. File format is documented. No lock-in.
3. **API-first.** Every feature is exposable via a documented API. OpenAPI spec ships with the product.
4. **Double-entry is non-negotiable.** Integrity is enforced at the database layer, not the UI.
5. **No hard deletes.** Voids and reversals only. Every change leaves a trail.

See [docs/PRD.md](docs/PRD.md) for the full product specification.

## Repository layout

```
ledgerline/
├── backend/         FastAPI + SQLAlchemy 2 + SQLite
├── frontend/        React + TypeScript + Vite + Tailwind
├── electron/        Minimal Electron shell (spawns FastAPI locally)
├── docs/            PRD and architecture notes
└── .github/         CI workflows
```

## Status

This repo tracks the MVP build described in the PRD: Phase 0 (foundation) + Phase 1 (MVP core). Later phases — AR/AP, banking, Plaid, desktop polish, inventory — are deferred.

## Local development

Prerequisites: Python 3.11+ (3.9 also works), Node 20+, `make`.

```bash
make install    # install backend + frontend deps
make dev        # run backend + frontend together
make test       # run backend tests + frontend typecheck
```

The backend starts on `http://localhost:8787` with OpenAPI docs at `/docs`. The frontend starts on `http://localhost:5173` and proxies API calls to the backend.

## License

MIT — see [LICENSE](LICENSE).
