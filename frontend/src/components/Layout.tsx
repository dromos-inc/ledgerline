import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export function Layout({ children }: Props) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-ink-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-semibold tracking-tight">
              ledgerline
            </span>
            <span className="text-xs text-ink-400">v0.1.0</span>
          </div>
          <nav className="flex items-center gap-5 text-sm">
            <a href="#" className="text-ink-500 hover:text-ink-900">
              Companies
            </a>
            <a href="#" className="text-ink-500 hover:text-ink-900">
              Accounts
            </a>
            <a href="#" className="text-ink-500 hover:text-ink-900">
              Journal
            </a>
            <a href="#" className="text-ink-500 hover:text-ink-900">
              Reports
            </a>
          </nav>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
