# Ledgerline Electron shell

A thin Electron wrapper that spawns the FastAPI backend on localhost and loads
the Ledgerline UI.

## Development

```bash
# Terminal 1 — frontend dev server
cd frontend && pnpm dev

# Terminal 2 — Electron shell
cd electron
pnpm install
NODE_ENV=development pnpm start
```

The shell looks for `backend/.venv/bin/python` (created by `make install`) and
falls back to `python3` on PATH. It starts `app.main` on `127.0.0.1:8787`,
polls `/health` until ready, then loads the UI.

## Production build

Production packaging (universal macOS binary, Windows signed installer,
auto-update) is Phase 6 scope. For Phase 1 this shell is the minimum viable
local tier; run it from source.

## What's deliberately NOT here

- Auto-update (electron-updater): Phase 6
- Native menus (File ▸ Open company, etc.): Phase 6
- File associations for `.ledgerline` files: Phase 6
- Windows signed installer, macOS notarization: Phase 6

The shell's job is only: "launch Python, wait for it, open a window."
