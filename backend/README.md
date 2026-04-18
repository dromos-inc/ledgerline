# Ledgerline backend

FastAPI + SQLAlchemy 2 + SQLite. Single source of truth for all three tiers (local, cloud, self-hosted).

## Develop

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Run the API server (reloads on changes in dev_mode)
LEDGERLINE_DEV_MODE=true python -m app.main

# Tests
pytest

# Lint
ruff check app tests
```

The server binds to `127.0.0.1:8787` by default. Data lives in `~/.ledgerline/` unless `LEDGERLINE_DATA_DIR` is set.

## Layout

```
backend/
├── app/
│   ├── main.py          FastAPI app factory + /health
│   ├── config.py        Settings (env-driven)
│   ├── db/              SQLAlchemy engines + session management
│   ├── models/          ORM models
│   ├── schemas/         Pydantic request/response models
│   ├── api/             FastAPI routers
│   ├── reports/         Trial balance, P&L, balance sheet queries
│   └── export/          CSV and JSON serializers
└── tests/               pytest
```

## Multi-company storage

Each company is a separate SQLite file under `~/.ledgerline/companies/<id>.db`.
A root `registry.db` tracks which companies exist. Switching companies means
opening a different file — same schema, portable between local and cloud.

## Settings (env vars)

| Variable                     | Default                              | Purpose                       |
| ---------------------------- | ------------------------------------ | ----------------------------- |
| `LEDGERLINE_HOST`            | `127.0.0.1`                          | Bind address                  |
| `LEDGERLINE_PORT`            | `8787`                               | HTTP port                     |
| `LEDGERLINE_DEV_MODE`        | `false`                              | Hot-reload, permissive CORS   |
| `LEDGERLINE_DATA_DIR`        | `~/.ledgerline`                      | Data root                     |
| `LEDGERLINE_API_PREFIX`      | `/api/v1`                            | API URL prefix                |
| `LEDGERLINE_CORS_ORIGINS`    | `http://localhost:5173,...`          | CORS allow-list               |
