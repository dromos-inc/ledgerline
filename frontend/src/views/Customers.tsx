// Customer list + inline create form.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState, type FormEvent } from "react";
import {
  ApiError,
  customers as customersApi,
  type Customer,
  type Terms,
} from "../api";
import { useShortcut } from "../shortcuts";

interface Props {
  companyId: string;
}

const TERMS: Terms[] = ["net_15", "net_30", "net_60", "due_on_receipt", "custom"];

export function Customers({ companyId }: Props) {
  const svc = customersApi(companyId);
  const qc = useQueryClient();
  const [includeInactive, setIncludeInactive] = useState(false);
  const [query, setQuery] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery<Customer[]>({
    queryKey: ["customers", companyId, includeInactive, query],
    queryFn: () => svc.list(includeInactive, query || undefined),
  });

  const openNew = useCallback(() => setShowCreate(true), []);
  useShortcut(
    {
      id: "n",
      description: "New customer",
      group: "Customers",
      when: () => !showCreate,
    },
    openNew,
  );

  const deactivate = useMutation({
    mutationFn: (id: number) => svc.deactivate(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["customers", companyId] }),
  });
  const reactivate = useMutation({
    mutationFn: (id: number) => svc.reactivate(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["customers", companyId] }),
  });

  return (
    <div className="p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Customers</h1>
          <p className="text-sm text-stone-500">
            People and companies you invoice. Press{" "}
            <kbd className="rounded border bg-stone-100 px-1 text-xs">n</kbd>{" "}
            for a new customer.
          </p>
        </div>
        <button
          type="button"
          onClick={openNew}
          className="rounded bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700"
        >
          New customer
        </button>
      </header>

      <div className="mb-4 flex items-center gap-3 text-sm">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name, code, company, email\u2026"
          className="w-64 rounded border border-stone-300 px-2 py-1"
        />
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
          />
          Show inactive
        </label>
      </div>

      {showCreate && (
        <CreateForm companyId={companyId} onClose={() => setShowCreate(false)} />
      )}

      {isLoading && <p className="text-sm text-stone-500">Loading\u2026</p>}
      {data && (
        <table className="w-full text-sm">
          <thead className="border-b text-left text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="py-2 pr-3">Code</th>
              <th className="py-2 pr-3">Name</th>
              <th className="py-2 pr-3">Company</th>
              <th className="py-2 pr-3">Email</th>
              <th className="py-2 pr-3">Terms</th>
              <th className="py-2 pr-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.map((c) => (
              <tr key={c.id} className="border-b">
                <td className="py-2 pr-3 font-mono text-xs">{c.code}</td>
                <td className="py-2 pr-3">{c.name}</td>
                <td className="py-2 pr-3 text-stone-600">{c.company ?? ""}</td>
                <td className="py-2 pr-3 text-stone-600">{c.email ?? ""}</td>
                <td className="py-2 pr-3 text-xs text-stone-500">
                  {c.default_terms}
                </td>
                <td className="py-2 pr-3">
                  {c.is_active ? (
                    <span className="text-emerald-700">active</span>
                  ) : (
                    <span className="text-stone-400">inactive</span>
                  )}
                </td>
                <td className="py-2 pr-3 text-right">
                  {c.is_active ? (
                    <button
                      type="button"
                      onClick={() => deactivate.mutate(c.id)}
                      className="text-xs text-stone-500 underline hover:text-stone-800"
                    >
                      deactivate
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => reactivate.mutate(c.id)}
                      className="text-xs text-emerald-600 underline hover:text-emerald-800"
                    >
                      reactivate
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="py-8 text-center text-stone-400"
                >
                  No customers yet. Press{" "}
                  <kbd className="rounded border bg-stone-100 px-1 text-xs">
                    n
                  </kbd>{" "}
                  to add one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

function CreateForm({
  companyId,
  onClose,
}: {
  companyId: string;
  onClose: () => void;
}) {
  const svc = customersApi(companyId);
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [terms, setTerms] = useState<Terms>("net_30");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      svc.create({
        code,
        name,
        company: company || undefined,
        email: email || undefined,
        default_terms: terms,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers", companyId] });
      onClose();
    },
    onError: (e: unknown) => {
      if (e instanceof ApiError) {
        setError(typeof e.detail === "string" ? e.detail : e.message);
      } else {
        setError(String(e));
      }
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    create.mutate();
  };

  return (
    <form
      onSubmit={submit}
      className="mb-6 grid grid-cols-5 gap-3 rounded border border-stone-200 bg-stone-50 p-4 text-sm"
    >
      <label className="flex flex-col">
        <span className="text-xs text-stone-500">Code</span>
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
          placeholder="CUST-001"
          className="rounded border border-stone-300 px-2 py-1"
        />
      </label>
      <label className="flex flex-col">
        <span className="text-xs text-stone-500">Name</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="rounded border border-stone-300 px-2 py-1"
        />
      </label>
      <label className="flex flex-col">
        <span className="text-xs text-stone-500">Company (optional)</span>
        <input
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          className="rounded border border-stone-300 px-2 py-1"
        />
      </label>
      <label className="flex flex-col">
        <span className="text-xs text-stone-500">Email (optional)</span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded border border-stone-300 px-2 py-1"
        />
      </label>
      <label className="flex flex-col">
        <span className="text-xs text-stone-500">Terms</span>
        <select
          value={terms}
          onChange={(e) => setTerms(e.target.value as Terms)}
          className="rounded border border-stone-300 px-2 py-1"
        >
          {TERMS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      {error && (
        <p className="col-span-5 text-xs text-rose-700">Error: {error}</p>
      )}

      <div className="col-span-5 flex gap-2">
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded bg-stone-900 px-3 py-1 text-white hover:bg-stone-700 disabled:opacity-50"
        >
          {create.isPending ? "Saving\u2026" : "Save"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-stone-300 px-3 py-1 hover:bg-stone-100"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
