// Chart of accounts: list, create, deactivate.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import {
  accounts as accountsApi,
  ApiError,
  type Account,
  type AccountType,
} from "../api";

interface Props {
  companyId: string;
}

const ACCOUNT_TYPES: AccountType[] = [
  "asset",
  "liability",
  "equity",
  "income",
  "expense",
];

export function Accounts({ companyId }: Props) {
  const svc = accountsApi(companyId);
  const qc = useQueryClient();
  const [includeInactive, setIncludeInactive] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery<Account[]>({
    queryKey: ["accounts", companyId, includeInactive],
    queryFn: () => svc.list(includeInactive),
  });

  const deactivate = useMutation({
    mutationFn: (id: number) => svc.deactivate(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["accounts", companyId] }),
  });
  const reactivate = useMutation({
    mutationFn: (id: number) => svc.reactivate(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["accounts", companyId] }),
  });

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">
            Chart of accounts
          </h2>
          <p className="mt-1 text-sm text-ink-500">
            {data?.length ?? 0} accounts
          </p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
            />
            Include inactive
          </label>
          <a
            className="btn"
            href={`/api/v1/companies/${companyId}/export/accounts.csv`}
            target="_blank"
            rel="noreferrer"
          >
            Export CSV
          </a>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowCreate(true)}
          >
            + New account
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="mt-4">
          <NewAccountForm
            companyId={companyId}
            onDone={() => setShowCreate(false)}
          />
        </div>
      )}

      <div className="mt-6 rounded border border-ink-200 bg-white">
        {isLoading ? (
          <p className="p-4 font-mono text-sm text-ink-500">Loading…</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th className="w-24">Code</th>
                <th>Name</th>
                <th className="w-28">Type</th>
                <th className="w-28">Normal</th>
                <th className="w-20">Active</th>
                <th className="w-32" />
              </tr>
            </thead>
            <tbody>
              {data?.map((a) => (
                <tr key={a.id} className={!a.is_active ? "opacity-50" : ""}>
                  <td className="font-mono">{a.code}</td>
                  <td className="font-medium">{a.name}</td>
                  <td className="text-ink-500">{a.type}</td>
                  <td className="text-ink-500">{a.normal_balance}</td>
                  <td>{a.is_active ? "✓" : "—"}</td>
                  <td className="text-right">
                    {a.is_active ? (
                      <button
                        type="button"
                        className="text-xs text-ink-500 hover:text-danger"
                        onClick={() => deactivate.mutate(a.id)}
                      >
                        Deactivate
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="text-xs text-ink-500 hover:text-success"
                        onClick={() => reactivate.mutate(a.id)}
                      >
                        Reactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function NewAccountForm({
  companyId,
  onDone,
}: {
  companyId: string;
  onDone: () => void;
}) {
  const svc = accountsApi(companyId);
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("expense");
  const [error, setError] = useState<string | null>(null);

  const m = useMutation<Account, ApiError>({
    mutationFn: () => svc.create({ code, name, type }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts", companyId] });
      onDone();
    },
    onError: (err) => setError(err.message),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    m.mutate();
  }

  return (
    <form
      onSubmit={submit}
      className="rounded border border-ink-200 bg-white p-4"
    >
      <div className="grid grid-cols-4 gap-3">
        <label className="block">
          <span className="text-xs font-medium text-ink-500">Code</span>
          <input
            className="input mt-1 font-mono"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
            autoFocus
          />
        </label>
        <label className="col-span-2 block">
          <span className="text-xs font-medium text-ink-500">Name</span>
          <input
            className="input mt-1"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ink-500">Type</span>
          <select
            className="input mt-1"
            value={type}
            onChange={(e) => setType(e.target.value as AccountType)}
          >
            {ACCOUNT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <p className="mt-3 font-mono text-sm text-danger">{error}</p>}
      <div className="mt-4 flex gap-2">
        <button type="submit" className="btn btn-primary" disabled={m.isPending}>
          Save
        </button>
        <button type="button" className="btn" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}
