// Minimal Electron shell for the local tier.
//
// 1. Spawn the Python FastAPI backend as a subprocess bound to 127.0.0.1:8787.
// 2. Poll /health until it returns 200.
// 3. Load the Ledgerline UI in a BrowserWindow pointed at the dev server
//    (development) or the file:// bundle (production).
// 4. On app quit, terminate the backend cleanly.
//
// Future Phase 6 concerns deliberately NOT handled here:
// - Auto-update
// - Native menus (File open / save-as)
// - File associations (double-click .ledgerline)
// - Windows/macOS code signing
// - Universal macOS binary, Windows signed installer
//
// This shell is the minimum needed to deliver the local commercial tier.

const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = 8787;
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const READINESS_TIMEOUT_MS = 30_000;
const DEV = process.env.NODE_ENV === "development";

/** @type {import('child_process').ChildProcess | null} */
let backend = null;

function startBackend() {
  // In production (Electron bundled), Python is packaged alongside the app.
  // For MVP we assume a venv at backend/.venv/bin/python is available.
  const repoRoot = path.resolve(__dirname, "..");
  const pythonPath = path.join(repoRoot, "backend", ".venv", "bin", "python");
  const cmd = require("fs").existsSync(pythonPath) ? pythonPath : "python3";
  backend = spawn(cmd, ["-m", "app.main"], {
    cwd: path.join(repoRoot, "backend"),
    env: {
      ...process.env,
      LEDGERLINE_HOST: BACKEND_HOST,
      LEDGERLINE_PORT: String(BACKEND_PORT),
      LEDGERLINE_DEV_MODE: DEV ? "true" : "false",
      PYTHONUNBUFFERED: "1",
    },
    stdio: "inherit",
  });
  backend.on("exit", (code) => {
    console.log(`[ledgerline] backend exited with code ${code}`);
    if (!app.isQuitting) {
      app.quit();
    }
  });
}

function waitForHealth(timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tick = () => {
      http
        .get(`${BACKEND_URL}/health`, (resp) => {
          if (resp.statusCode === 200) {
            resolve(undefined);
          } else {
            retry();
          }
          resp.resume();
        })
        .on("error", retry);
    };
    const retry = () => {
      if (Date.now() > deadline) {
        reject(new Error("backend did not become ready"));
      } else {
        setTimeout(tick, 250);
      }
    };
    tick();
  });
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "Ledgerline",
    backgroundColor: "#f8f8f7",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (DEV) {
    // Vite dev server proxies /api to the backend.
    await win.loadURL("http://localhost:5173");
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    // Load the built UI bundle from disk.
    const indexPath = path.join(
      __dirname,
      "..",
      "frontend",
      "dist",
      "index.html",
    );
    await win.loadFile(indexPath);
  }
}

app.on("before-quit", () => {
  app.isQuitting = true;
  if (backend && !backend.killed) {
    backend.kill("SIGTERM");
  }
});

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForHealth(READINESS_TIMEOUT_MS);
  } catch (err) {
    console.error(`[ledgerline] ${err.message}`);
    app.quit();
    return;
  }
  await createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
