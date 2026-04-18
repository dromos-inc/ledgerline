// Overlay: press `?` to see every registered shortcut, grouped.

import { useEffect, useState } from "react";
import { listShortcuts, prettyKey, type ShortcutSummary } from "./registry";
import { useShortcut } from "./useShortcut";

export function ShortcutHelp() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ShortcutSummary[]>([]);

  useShortcut(
    { id: "shift+?", description: "Show keyboard shortcuts", group: "Help" },
    () => setOpen((o) => !o),
  );
  useShortcut(
    {
      id: "escape",
      description: "Close dialog",
      group: "Help",
      when: () => open,
    },
    () => setOpen(false),
  );

  useEffect(() => {
    if (open) setItems(listShortcuts());
  }, [open]);

  if (!open) return null;

  const groups: Record<string, ShortcutSummary[]> = {};
  for (const item of items) {
    (groups[item.group] ??= []).push(item);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50"
      onClick={() => setOpen(false)}
    >
      <div
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded border border-ink-200 bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Keyboard shortcuts</h2>
          <button
            type="button"
            className="text-xs text-ink-400 hover:text-ink-900"
            onClick={() => setOpen(false)}
          >
            Close (Esc)
          </button>
        </div>
        <div className="mt-4 space-y-5">
          {Object.entries(groups).map(([group, rows]) => (
            <section key={group}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-400">
                {group}
              </h3>
              <ul className="mt-2 divide-y divide-ink-100">
                {rows.map((r) => (
                  <li
                    key={r.id}
                    className="flex items-center justify-between py-1.5 text-sm"
                  >
                    <span>{r.description}</span>
                    <span className="kbd">{prettyKey(r.id)}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
