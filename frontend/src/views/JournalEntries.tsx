// Journal entry list with void action.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  ApiError,
  formatCents,
  journal as journalApi,
  type JournalEntry,
  type JournalEntryList,
  type JournalStatus,
} from "../api";
import { JournalEntryForm } from "./JournalEntryForm";

interface Props {
  companyId: string;
  onViewRegister?: (accountId: number) => void;
}

const STATUS_CLASS: Record<JournalStatus, string> = {
  draft: "text-ink-500",
  posted: "text-success",
  void: "text-danger line-through",
};

export function JournalEntries({ companyId }: Props) {
  const svc = journalApi(companyId);
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);

  const { data, isLoading } = useQuery<JournalEntryList>({
    queryKey: ["journal", companyId],
    queryFn: () => svc.list(),
  });

  const voidEntry = useMutation<JournalEntry, ApiError, number>({
    mutationFn: (id) => svc.voidEntry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["journal", companyId] }),
  });

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">
            Journal entries
          </h2>
          <p className="mt-1 text-sm text-ink-500">
            {data?.total ?? 0} total · sorted newest first
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a
            className="btn"
            href={`/api/v1/companies/${companyId}/export/journal-entries.csv`}
            target="_blank"
            rel="noreferrer"
          >
            Export CSV
          </a>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowNew(true)}
          >
            + New entry
          </button>
        </div>
      </div>

      {showNew && (
        <div className="mt-5">
          <JournalEntryForm
            companyId={companyId}
            onPosted={() => setShowNew(false)}
            onCancel={() => setShowNew(false)}
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
                <th className="w-28">Date</th>
                <th className="w-24">Ref</th>
                <th>Memo</th>
                <th className="w-20">Lines</th>
                <th className="w-32 text-right">Amount</th>
                <th className="w-20">Status</th>
                <th className="w-28 text-right" />
              </tr>
            </thead>
            <tbody>
              {data?.entries.map((e) => (
                <tr key={e.id}>
                  <td className="font-mono text-ink-500">{e.entry_date}</td>
                  <td className="font-mono">{e.reference ?? "—"}</td>
                  <td>{e.memo ?? <span className="text-ink-300">—</span>}</td>
                  <td>{e.lines.length}</td>
                  <td className="tabular text-right">
                    {formatCents(
                      e.lines.reduce((s, l) => s + l.debit_cents, 0),
                    )}
                  </td>
                  <td className={STATUS_CLASS[e.status]}>{e.status}</td>
                  <td className="text-right">
                    {e.status === "posted" && (
                      <button
                        type="button"
                        className="text-xs text-ink-500 hover:text-danger"
                        onClick={() => {
                          if (confirm(`Void entry ${e.id}?`)) {
                            voidEntry.mutate(e.id);
                          }
                        }}
                      >
                        Void
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
