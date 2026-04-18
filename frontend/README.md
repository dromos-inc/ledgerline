# Ledgerline frontend

React + TypeScript + Vite + Tailwind. Talks to the FastAPI backend over HTTP.

## Develop

```bash
cd frontend
pnpm install
pnpm dev        # starts Vite on http://localhost:5173, proxies /api to 8787
pnpm typecheck  # tsc --noEmit
pnpm build      # compiled bundle in dist/
pnpm test       # vitest
```

The dev server proxies `/api/*` to the FastAPI backend on `127.0.0.1:8787`. Start the backend separately (`make dev` from the repo root).

## Design principles

Function over form (PRD §5). Dense information displays, keyboard shortcuts everywhere, no animation that costs more than 100ms. Editorial typography, restrained palette, tabular figures for money columns.

## Layout

```
frontend/
├── src/
│   ├── main.tsx         # Entry: QueryClient + StrictMode + App
│   ├── App.tsx          # Root layout
│   ├── components/      # UI
│   ├── api/             # Typed API client (later commits)
│   ├── routes/          # TanStack Router routes (later commits)
│   ├── hooks/           # React hooks
│   └── shortcuts/       # Keyboard-shortcut framework (later commits)
└── vite.config.ts       # Build + proxy config
```
