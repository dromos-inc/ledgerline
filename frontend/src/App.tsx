import { useState } from "react";
import { Layout } from "./components/Layout";
import { useSelectedCompany } from "./hooks/useSelectedCompany";
import { Accounts } from "./views/Accounts";
import { CompanyPicker } from "./views/CompanyPicker";
import { JournalEntries } from "./views/JournalEntries";

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
      {view === "register" && (
        <Placeholder title="Register" subtitle="Lands in the next commit." />
      )}
      {view === "reports" && (
        <Placeholder title="Reports" subtitle="Lands in the next commit." />
      )}
    </Layout>
  );
}

function Placeholder({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16 text-center">
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-2 text-sm text-ink-500">{subtitle}</p>
    </div>
  );
}
