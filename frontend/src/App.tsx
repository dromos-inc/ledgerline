import { useState } from "react";
import { Layout } from "./components/Layout";
import { useSelectedCompany } from "./hooks/useSelectedCompany";
import { Accounts } from "./views/Accounts";
import { CompanyPicker } from "./views/CompanyPicker";
import { JournalEntries } from "./views/JournalEntries";
import { Register } from "./views/Register";
import { Reports } from "./views/Reports";

type View = "accounts" | "journal" | "register" | "reports";

export function App() {
  const [companyId, setCompanyId] = useSelectedCompany();
  const [view, setView] = useState<View>("accounts");

  if (!companyId) {
    return (
      <Layout
        companyId={null}
        view={view}
        onSwitchView={setView}
        onSwitchCompany={() => setCompanyId(null)}
      >
        <CompanyPicker onPick={(id) => setCompanyId(id)} />
      </Layout>
    );
  }

  return (
    <Layout
      companyId={companyId}
      view={view}
      onSwitchView={setView}
      onSwitchCompany={() => setCompanyId(null)}
    >
      {view === "accounts" && <Accounts companyId={companyId} />}
      {view === "journal" && <JournalEntries companyId={companyId} />}
      {view === "register" && <Register companyId={companyId} />}
      {view === "reports" && <Reports companyId={companyId} />}
    </Layout>
  );
}
