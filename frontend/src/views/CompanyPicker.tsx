// First screen: pick a company or create one.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import {
  ApiError,
  companies,
  type Company,
  type EntityType,
  type TemplateInfo,
} from "../api";

interface Props {
  onPick: (id: string) => void;
}

export function CompanyPicker({ onPick }: Props) {
  const { data, isLoading } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: companies.list,
  });
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Your companies</h1>
      <p className="mt-2 text-sm text-ink-500">
        Each company has its own SQLite file. Pick one to open its books.
      </p>

      <div className="mt-8">
        {isLoading ? (
          <p className="font-mono text-sm text-ink-500">Loading…</p>
        ) : data && data.length > 0 ? (
          <ul className="divide-y divide-ink-200 rounded border border-ink-200 bg-white">
            {data.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onPick(c.id)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-ink-50"
                >
                  <div>
                    <div className="font-semibold">{c.name}</div>
                    <div className="font-mono text-xs text-ink-400">
                      {c.id} · {c.entity_type.replace("_", "-")} · {c.tax_basis}
                    </div>
                  </div>
                  <span className="text-xs text-ink-400">Open →</span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="font-mono text-sm text-ink-500">No companies yet.</p>
        )}
      </div>

      <div className="mt-8">
        {showCreate ? (
          <CreateCompanyForm
            onCreated={(c) => {
              setShowCreate(false);
              onPick(c.id);
            }}
            onCancel={() => setShowCreate(false)}
          />
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowCreate(true)}
          >
            + Create company
          </button>
        )}
      </div>
    </div>
  );
}

function CreateCompanyForm({
  onCreated,
  onCancel,
}: {
  onCreated: (c: Company) => void;
  onCancel: () => void;
}) {
  const qc = useQueryClient();
  const { data: templates } = useQuery<TemplateInfo[]>({
    queryKey: ["company-templates"],
    queryFn: companies.templates,
  });

  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState<EntityType>("schedule_c");
  const [template, setTemplate] = useState<string>("sched_c_service");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation<Company, ApiError>({
    mutationFn: () =>
      companies.create({ id, name, entity_type: entityType }, template || undefined),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      onCreated(c);
    },
    onError: (err) => setError(err.message),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <form
      onSubmit={submit}
      className="rounded border border-ink-200 bg-white p-5"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-400">
        New company
      </h2>
      <div className="mt-4 grid grid-cols-2 gap-4">
        <label className="block">
          <span className="text-xs font-medium text-ink-500">
            ID (slug, becomes filename)
          </span>
          <input
            className="input mt-1 font-mono"
            value={id}
            onChange={(e) => setId(e.target.value)}
            placeholder="dromos-inc"
            required
            pattern="[a-z0-9][a-z0-9_-]*"
            autoFocus
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ink-500">Name</span>
          <input
            className="input mt-1"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Dromos Inc."
            required
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ink-500">Entity type</span>
          <select
            className="input mt-1"
            value={entityType}
            onChange={(e) => setEntityType(e.target.value as EntityType)}
          >
            <option value="schedule_c">Schedule C</option>
            <option value="s_corp">S-corp</option>
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ink-500">
            Chart of accounts
          </span>
          <select
            className="input mt-1"
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
          >
            <option value="">Empty (I'll build my own)</option>
            {templates?.map((t) => (
              <option key={t.key} value={t.key}>
                {t.label} ({t.account_count} accounts)
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && (
        <p className="mt-3 font-mono text-sm text-danger">{error}</p>
      )}
      <div className="mt-5 flex gap-2">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? "Creating…" : "Create"}
        </button>
        <button
          type="button"
          className="btn"
          onClick={onCancel}
          disabled={mutation.isPending}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
