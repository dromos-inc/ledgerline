// React hook: register a keyboard shortcut for the lifetime of a component.

import { useEffect } from "react";
import { registerShortcut } from "./registry";

interface Options {
  id: string; // normalized combo, e.g. "ctrl+enter"
  description: string;
  group?: string;
  when?: () => boolean;
}

export function useShortcut(
  options: Options,
  handler: (event: KeyboardEvent) => void,
): void {
  useEffect(() => {
    return registerShortcut({
      id: options.id,
      description: options.description,
      group: options.group ?? "Global",
      handler,
      when: options.when,
    });
    // Re-register if any of these change. The handler is referenced by
    // identity, so callers should memoize if they want to avoid churn.
  }, [options.id, options.description, options.group, options.when, handler]);
}
