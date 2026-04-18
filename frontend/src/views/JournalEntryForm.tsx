// New / draft journal entry form. Multi-line grid with live balance check.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import {
  accounts as accountsApi,
  ApiError,
  formatCents,
  journal as journalApi,
  parseDollars,
  type Account,
  type JournalEntry,
  type JournalLineCreate,
} from "../api";

interface Props {
  companyId: string;
  onPosted: (entry: JournalEntry) => void;
  onCancel: () => void;
}

interface LineDraft {
  accountId: number | null;
  debit: string; // string for input; parsed on submit
  credit: string;
  memo: string;
}

const EMPTY_LINE: LineDraft = {
  accountId: null,
  debit: "",
  credit: "",
  memo: "",
};

export function JournalEntryForm({ companyId, onPosted, onCancel }: Props) {
  const { data: accounts } = useQuery<Account[]>({
    queryKey: ["accounts", companyId, false],
    queryFn: () => accountsApi(companyId).list(),
  });
  const active = useMemo(
    () => accounts?.filter((a) => a.is_active) ?? [],
    [accounts],
  );

  const today = new Date().toISOString().slice(0, 10);
  const [entryDate, setEntryDate] = useState(today);
  const [reference, setReference] = useState("");
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([
    { ...EMPTY_LINE },
    { ...EMPTY_LINE },
  ]);
  const [error, setError] = useState<string | null>(null);

  function updateLine<K extends keyof LineDraft>(
    idx: number,
    key: K,
    value: LineDraft[K],
  ) {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, [key]: value } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { ...EMPTY_LINE }]);
  }

  function removeLine(idx: number) {
    setLines((prev) => (prev.length <= 2 ? prev : prev.filter((_, i) => i !== idx)));
  }

  const totals = useMemo(() => {
    let debit = 0;
    let credit = 0;
    for (const l of lines) {
      try {
        if (l.debit) debit += parseDollars(l.debit);
      } catch {
        /* ignore while typing */
      }
      try {
        if (l.credit) credit += parseDollars(l.credit);
      } catch {
        /* ignore */
      }
    }
    return { debit, credit, diff: debit - credit };
  }, [lines]);

  const qc = useQueryClient();
  const createAndPost = useMutation<JournalEntry, ApiError, JournalLineCreate[]>({
    mutationFn: async (payloadLines) => {
      const created = await journalApi(companyId).create({
        entry_date: entryDate,
        reference: reference || undefined,
        memo: memo || undefined,
        lines: payloadLines,
      });
      return await journalApi(companyId).post(created.id);
    },
    onSuccess: (entry) => {
      qc.invalidateQueries({ queryKey: ["journal", companyId] });
      qc.invalidateQueries({ queryKey: ["accounts", companyId] });
      onPosted(entry);
    },
    onError: (err) => setError(err.message),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const payload: JournalLineCreate[] = lines.map((l, i) => {
        if (l.accountId == null) {
          throw new Error(`Line ${i + 1}: pick an account`);
        }
        const d = l.debit ? parseDollars(l.debit) : 0;
        const c = l.credit ? parseDollars(l.credit) : 0;
        if ((d > 0) === (c > 0)) {
          throw new Error(
            `Line ${i + 1}: enter exactly one of debit or credit (> 0)`,
          );
        }
        return {
          account_id: l.accountId,
          debit_cents: d,
          credit_cents: c,
          memo: l.memo || undefined,
        };
      });
      createAndPost.mutate(payload);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const balanced = totals.diff === 0 && totals.debit > 0;

  return (
    <form
      onSubmit={submit}
      className="rounded border border-ink-200 bg-white p-5"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-400">
        New journal entry
      </h2>
      <div className="mt-4 grid grid-cols-3 gap-4">
        <label className="block">
          <span className="text-xs font-medium text-ink-500">Entry date</span>
          <input
            type="date"
            className="input mt-1"
            value={entryDate}
            onChange={(e) => setEntryDate(e.target.value)}
            required
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ink-500">Reference</span>
          <input
            className="input mt-1"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="INV-001"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ink-500">Memo</span>
          <input
            className="input mt-1"
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
          />
        </label>
      </div>

      <table className="table mt-6">
        <thead>
          <tr>
            <th className="w-10">#</th>
            <th>Account</th>
            <th className="w-32 text-right">Debit</th>
            <th className="w-32 text-right">Credit</th>
            <th>Memo</th>
            <th className="w-10" />
          </tr>
        </thead>
        <tbody>
          {lines.map((line, idx) => (
            <tr key={idx}>
              <td className="text-ink-400">{idx + 1}</td>
              <td>
                <select
                  className="input"
                  value={line.accountId ?? ""}
                  onChange={(e) =>
                    updateLine(
                      idx,
                      "accountId",
                      e.target.value ? Number(e.target.value) : null,
                    )
                  }
                >
                  <option value="">—</option>
                  {active.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} · {a.name}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  className="input tabular text-right"
                  value={line.debit}
                  onChange={(e) => {
                    updateLine(idx, "debit", e.target.value);
                    if (e.target.value) updateLine(idx, "credit", "");
                  }}
                  placeholder="0.00"
                  inputMode="decimal"
                />
              </td>
              <td>
                <input
                  className="input tabular text-right"
                  value={line.credit}
                  onChange={(e) => {
                    updateLine(idx, "credit", e.target.value);
                    if (e.target.value) updateLine(idx, "debit", "");
                  }}
                  placeholder="0.00"
                  inputMode="decimal"
                />
              </td>
              <td>
                <input
                  className="input"
                  value={line.memo}
                  onChange={(e) => updateLine(idx, "memo", e.target.value)}
                />
              </td>
              <td>
                {lines.length > 2 && (
                  <button
                    type="button"
                    className="text-xs text-ink-400 hover:text-danger"
                    onClick={() => removeLine(idx)}
                  >
                    ✕
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td />
            <td className="text-right text-xs uppercase tracking-wider text-ink-400">
              Totals
            </td>
            <td className="tabular text-right font-semibold">
              {formatCents(totals.debit)}
            </td>
            <td className="tabular text-right font-semibold">
              {formatCents(totals.credit)}
            </td>
            <td
              className={
                balanced
                  ? "text-xs text-success"
                  : totals.diff !== 0
                    ? "text-xs text-danger"
                    : "text-xs text-ink-400"
              }
            >
              {balanced
                ? "Balanced"
                : totals.diff !== 0
                  ? `Diff ${formatCents(Math.abs(totals.diff))}`
                  : "Start entering"}
            </td>
            <td />
          </tr>
        </tfoot>
      </table>

      <button
        type="button"
        className="btn mt-2 text-xs"
        onClick={addLine}
      >
        + Add line
      </button>

      {error && (
        <p className="mt-3 font-mono text-sm text-danger">{error}</p>
      )}

      <div className="mt-5 flex items-center gap-2">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!balanced || createAndPost.isPending}
        >
          {createAndPost.isPending ? "Posting…" : "Post entry"}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
        <span className="ml-auto text-xs text-ink-400">
          <span className="kbd">Ctrl</span>+<span className="kbd">Enter</span> to post
        </span>
      </div>
    </form>
  );
}
