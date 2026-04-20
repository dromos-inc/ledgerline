import type { ReactNode } from "react";

type View =
  | "accounts"
  | "customers"
  | "invoices"
  | "ar_aging"
  | "vendors"
  | "bills"
  | "ap_aging"
  | "journal"
  | "register"
  | "reports";

interface Props {
  children: ReactNode;
  companyId: string | null;
  view: View;
  onSwitchView: (view: View) => void;
  onSwitchCompany: () => void;
}

const NAV: { key: View; label: string }[] = [
  { key: "accounts", label: "Accounts" },
  { key: "customers", label: "Customers" },
  { key: "invoices", label: "Invoices" },
  { key: "ar_aging", label: "AR aging" },
  { key: "vendors", label: "Vendors" },
  { key: "bills", label: "Bills" },
  { key: "ap_aging", label: "AP aging" },
  { key: "journal", label: "Journal" },
  { key: "register", label: "Register" },
  { key: "reports", label: "Reports" },
];

export function Layout({
  children,
  companyId,
  view,
  onSwitchView,
  onSwitchCompany,
}: Props) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-ink-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-semibold tracking-tight">
              ledgerline
            </span>
            {companyId && (
              <>
                <span className="text-ink-300">/</span>
                <button
                  type="button"
                  onClick={onSwitchCompany}
                  className="font-mono text-sm text-ink-700 hover:text-accent"
                  title="Switch company"
                >
                  {companyId}
                </button>
              </>
            )}
          </div>
          {companyId && (
            <nav className="flex flex-wrap items-center gap-4 text-sm">
              {NAV.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => onSwitchView(item.key)}
                  className={
                    view === item.key
                      ? "font-semibold text-ink-900"
                      : "text-ink-500 hover:text-ink-900"
                  }
                >
                  {item.label}
                </button>
              ))}
            </nav>
          )}
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}