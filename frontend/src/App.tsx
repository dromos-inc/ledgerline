import { useCallback, useState } from "react";
import { Layout } from "./components/Layout";
import { useSelectedCompany } from "./hooks/useSelectedCompany";
import { ShortcutHelp, useShortcut } from "./shortcuts";
import { Accounts } from "./views/Accounts";
import { ApAging } from "./views/ApAging";
import { ArAging } from "./views/ArAging";
import { Bills } from "./views/Bills";
import { CompanyPicker } from "./views/CompanyPicker";
import { Customers } from "./views/Customers";
import { Invoices } from "./views/Invoices";
import { JournalEntries } from "./views/JournalEntries";
import { Register } from "./views/Register";
import { Reports } from "./views/Reports";
import { Vendors } from "./views/Vendors";

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

export function App() {
  const [companyId, setCompanyId] = useSelectedCompany();
  const [view, setView] = useState<View>("accounts");

  const clearCompany = useCallback(() => setCompanyId(null), [setCompanyId]);
  const hasCompany = companyId != null;

  // Top-level navigation shortcuts when a company is open.
  const gotoAccounts = useCallback(() => setView("accounts"), []);
  const gotoCustomers = useCallback(() => setView("customers"), []);
  const gotoInvoices = useCallback(() => setView("invoices"), []);
  const gotoArAging = useCallback(() => setView("ar_aging"), []);
  const gotoVendors = useCallback(() => setView("vendors"), []);
  const gotoBills = useCallback(() => setView("bills"), []);
  const gotoApAging = useCallback(() => setView("ap_aging"), []);
  const gotoJournal = useCallback(() => setView("journal"), []);
  const gotoRegister = useCallback(() => setView("register"), []);
  const gotoReports = useCallback(() => setView("reports"), []);

  // AR side: Ctrl+1..Ctrl+4
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
    gotoArAging,
  );
  // AP side: Ctrl+5..Ctrl+7
  useShortcut(
    {
      id: "ctrl+5",
      description: "Go to Vendors",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoVendors,
  );
  useShortcut(
    {
      id: "ctrl+6",
      description: "Go to Bills",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoBills,
  );
  useShortcut(
    {
      id: "ctrl+7",
      description: "Go to AP aging",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoApAging,
  );
  // General ledger: Ctrl+8..Ctrl+0
  useShortcut(
    {
      id: "ctrl+8",
      description: "Go to Journal",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoJournal,
  );
  useShortcut(
    {
      id: "ctrl+9",
      description: "Go to Register",
      group: "Navigation",
      when: () => hasCompany,
    },
    gotoRegister,
  );
  useShortcut(
    {
      id: "ctrl+0",
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
      {view === "vendors" && <Vendors companyId={companyId} />}
      {view === "bills" && <Bills companyId={companyId} />}
      {view === "ap_aging" && <ApAging companyId={companyId} />}
      {view === "journal" && <JournalEntries companyId={companyId} />}
      {view === "register" && <Register companyId={companyId} />}
      {view === "reports" && <Reports companyId={companyId} />}
      <ShortcutHelp />
    </Layout>
  );
}