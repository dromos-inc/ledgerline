import { useCallback, useState } from "react";
import { Layout } from "./components/Layout";
import { useSelectedCompany } from "./hooks/useSelectedCompany";
import { ShortcutHelp, useShortcut } from "./shortcuts";
import { Accounts } from "./views/Accounts";
import { ArAging } from "./views/ArAging";
import { CompanyPicker } from "./views/CompanyPicker";
import { Customers } from "./views/Customers";
import { Invoices } from "./views/Invoices";
import { JournalEntries } from "./views/JournalEntries";
import { Register } from "./views/Register";
import { Reports } from "./views/Reports";

type View =
  | "accounts"
  | "customers"
  | "invoices"
  | "ar_aging"
  | "journal"
  | "register"
  | "reports";

export function App() {
  const [companyId, setCompanyId] = useSelectedCompany();
  const [view, setView] = useState<View>("accounts");

  const clearCompany = useCallback(() => setCompanyId(null), [setCompanyId]);
  const hasCompany = companyId != null;

  // Top-level navigation shortcuts when a company is open.
  const gotoAccounts = useCallback(() => setView("accounts"), []);
  const gotoCustomers = useCallback(() => setView("customers"), []);
  const gotoInvoices = useCallback(() => setView("invoices"), []);
  const gotoAging = useCallback(() => setView("ar_aging"), []);
  const gotoJournal = useCallback(() => setView("journal"), []);
  const gotoRegister = useCallback(() => setView("register"), []);
  const gotoReports = useCallback(() => setView("reports"), []);

  useShortcut(
    {
      id: "ctrl+1",
      description: "Go to Accounts",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoAccounts,
  );
  useShortcut(
    {
      id: "ctrl+2",
      description: "Go to Customers",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoCustomers,
  );
  useShortcut(
    {
      id: "ctrl+3",
      description: "Go to Invoices",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoInvoices,
  );
  useShortcut(
    {
      id: "ctrl+4",
      description: "Go to AR aging",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoAging,
  );
  useShortcut(
    {
      id: "ctrl+5",
      description: "Go to Journal",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoJournal,
  );
  useShortcut(
    {
      id: "ctrl+6",
      description: "Go to Register",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoRegister,
  );
  useShortcut(
    {
      id: "ctrl+7",
      description: "Go to Reports",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoReports,
  );
  useShortcut(
    {
      id: "ctrl+shift+c",
      description: "Switch company",
      group: "Navigation",
      when: () => hasCompany,
    },
    clearCompany,
  );

  if (!companyId) {
    return (
      <Layout
        companyId={null}
        view={view}
        onSwitchView={setView}
        onSwitchCompany={clearCompany}
      >
        <CompanyPicker onPick={(id) => setCompanyId(id)} />
        <ShortcutHelp />
      </Layout>
    );
  }

  return (
    <Layout
      companyId={companyId}
      view={view}
      onSwitchView={setView}
      onSwitchCompany={clearCompany}
    >
      {view === "accounts" && <Accounts companyId={companyId} />}
      {view === "customers" && <Customers companyId={companyId} />}
      {view === "invoices" && <Invoices companyId={companyId} />}
      {view === "ar_aging" && <ArAging companyId={companyId} />}
      {view === "journal" && <JournalEntries companyId={companyId} />}
      {view === "register" && <Register companyId={companyId} />}
      {view === "reports" && <Reports companyId={companyId} />}
      <ShortcutHelp />
    </Layout>
  );
}
