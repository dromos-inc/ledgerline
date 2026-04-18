// Keyboard-shortcut registry.
//
// Lives outside React so multiple components can register and unregister
// bindings without prop-drilling. A single global `keydown` listener
// dispatches to handlers by normalized key id (e.g. "ctrl+enter", "n",
// "shift+/").

type Handler = (event: KeyboardEvent) => void;

interface Registration {
  id: string; // normalized combo id
  description: string;
  group: string; // used for the help dialog
  handler: Handler;
  when?: () => boolean; // optional gate
}

const registry: Map<string, Registration> = new Map();
let listenerAttached = false;

function normalizeKey(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.ctrlKey || e.metaKey) parts.push("ctrl");
  if (e.altKey) parts.push("alt");
  if (e.shiftKey) parts.push("shift");
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase();
  parts.push(key);
  return parts.join("+");
}

function shouldIgnore(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
    // Let Ctrl/Meta combos through even in inputs — that's how Ctrl+Enter
    // to post is supposed to work from the memo field.
    return false;
  }
  if (target.isContentEditable) return false;
  return false;
}

function dispatch(e: KeyboardEvent): void {
  // Skip when typing in a plain input unless a modifier is held.
  if (!e.ctrlKey && !e.metaKey && !e.altKey) {
    const target = e.target;
    if (target instanceof HTMLElement) {
      const tag = target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (target.isContentEditable) return;
    }
  }
  if (shouldIgnore(e.target)) return;

  const id = normalizeKey(e);
  const reg = registry.get(id);
  if (!reg) return;
  if (reg.when && !reg.when()) return;
  e.preventDefault();
  reg.handler(e);
}

function ensureListener(): void {
  if (listenerAttached) return;
  window.addEventListener("keydown", dispatch);
  listenerAttached = true;
}

export function registerShortcut(reg: Registration): () => void {
  ensureListener();
  registry.set(reg.id, reg);
  return () => {
    if (registry.get(reg.id) === reg) registry.delete(reg.id);
  };
}

export interface ShortcutSummary {
  id: string;
  description: string;
  group: string;
}

export function listShortcuts(): ShortcutSummary[] {
  return Array.from(registry.values()).map(({ id, description, group }) => ({
    id,
    description,
    group,
  }));
}

export function prettyKey(id: string): string {
  return id
    .split("+")
    .map((part) => {
      if (part === "ctrl") return isMac() ? "⌘" : "Ctrl";
      if (part === "shift") return isMac() ? "⇧" : "Shift";
      if (part === "alt") return isMac() ? "⌥" : "Alt";
      if (part === "enter") return "↵";
      if (part === "escape") return "Esc";
      if (part === "arrowup") return "↑";
      if (part === "arrowdown") return "↓";
      if (part === "arrowleft") return "←";
      if (part === "arrowright") return "→";
      return part.length === 1 ? part.toUpperCase() : part;
    })
    .join(isMac() ? "" : "+");
}

function isMac(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Mac|iPhone|iPad/.test(navigator.platform);
}
