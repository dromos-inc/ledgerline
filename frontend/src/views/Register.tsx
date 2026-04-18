// Per-account register with running balance.

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  accounts as accountsApi,
  formatCents,
  register as registerApi,
  type Account,
  type Register as RegisterType,
} from "../api";

interface Props {
  companyId: string;
}

export function Register({ companyId }: Props) {
  const { data: accounts } = useQuery<Account[]>({
    queryKey: ["accounts", companyId, false],
    queryFn: () => accountsApi(companyId).list(),
  });
  const [accountId, setAccountId] = useState<number | null>(null);

  const { data, isLoading } = useQuery<RegisterType>({
    queryKey: ["register", companyId, accountId],
    enabled: accountId != null,
    queryFn: () => registerApi(companyId).get(accountId as number),
  });

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Register</h2>
          <p className="mt-1 text-sm text-ink-500">
            Per-account transaction list with running balance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm">
            <span className="mr-2 text-ink-500">Account:</span>
            <select
              className="input inline-block w-72"
              value={accountId ?? ""}
              onChange={(e) =>
                setAccountId(e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">Pick one…</option>
              {accounts?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} · {a.name}
                </option>
              ))}
            </select>
          </label>
          {accountId != null && (
            <a
              className="btn"
              href={`/api/v1/companies/${companyId}/export/register.csv?account_id=${accountId}`}
              target="_blank"
              rel="noreferrer"
            >
              Export CSV
            </a>
          )}
        </div>
      </div>

      {accountId == null ? (
        <p className="mt-10 text-center font-mono text-sm text-ink-400">
          Select an account above to view its register.
        </p>
      ) : isLoading ? (
        <p className="mt-6 font-mono text-sm text-ink-500">Loading…</p>
      ) : data ? (
        <div className="mt-5 rounded border border-ink-200 bg-white">
          <div className="flex items-center justify-between border-b border-ink-200 px-4 py-3">
            <div>
              <div className="font-mono text-sm">
                {data.account_code} · {data.account_name}
              </div>
              <div className="text-xs text-ink-400">
                Opening:{" "}
                <span className="tabular">
                  {formatCents(data.opening_balance_cents)}
                </span>{" "}
                · Closing:{" "}
                <span className="tabular font-semibold">
                  {formatCents(data.closing_balance_cents)}
                </span>
              </div>
            </div>
            <div className="text-xs text-ink-400">{data.rows.length} rows</div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th className="w-28">Date</th>
                <th className="w-24">Ref</th>
                <th>Memo</th>
                <th className="w-32 text-right">Debit</th>
                <th className="w-32 text-right">Credit</th>
                <th className="w-32 text-right">Balance</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.line_id}>
                  <td className="font-mono text-ink-500">{row.entry_date}</td>
                  <td className="font-mono text-ink-500">
                    {row.reference ?? "—"}
                  </td>
                  <td>{row.line_memo ?? row.memo ?? "—"}</td>
                  <td className="tabular text-right">
                    {row.debit_cents > 0 ? formatCents(row.debit_cents) : "—"}
                  </td>
                  <td className="tabular text-right">
                    {row.credit_cents > 0 ? formatCents(row.credit_cents) : "—"}
                  </td>
                  <td className="tabular text-right font-medium">
                    {formatCents(row.running_balance_cents)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
