// Invoice list with inline actions (post, void) and a simple create form.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState, type FormEvent } from "react";
import {
  accounts as accountsApi,
  ApiError,
  customers as customersApi,
  formatCents,
  invoices as invoicesApi,
  parseDollars,
  type Account,
  type Customer,
  type Invoice,
  type InvoiceStatus,
} from "../api";
import { useShortcut } from "../shortcuts";

interface Props {
  companyId: string;
}

const STATUS_COLORS: Record<InvoiceStatus, string> = {
  draft: "text-stone-500",
  sent: "text-stone-900",
  partial: "text-amber-700",
  paid: "text-emerald-700",
  void: "text-rose-700 line-through",
};

export function Invoices({ companyId }: Props) {
  const svc = invoicesApi(companyId);
  const custSvc = customersApi(companyId);
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "">("");
  const [showCreate, setShowCreate] = useState(false);

  const { data: invoicesList, isLoading } = useQuery<Invoice[]>({
    queryKey: ["invoices", companyId, statusFilter],
    queryFn: () =>
      svc.list(statusFilter ? { status: statusFilter } : undefined),
  });
  const { data: customersList } = useQuery<Customer[]>({
    queryKey: ["customers", companyId, false, ""],
    queryFn: () => custSvc.list(false, undefined),
  });
  const customerById = new Map((customersList ?? []).map((c) => [c.id, c]));

  const openNew = useCallback(() => setShowCreate(true), []);
  useShortcut(
    {
      id: "n",
      description: "New invoice",
      group: "Invoices",
      when: () => !showCreate,
    },
    openNew,
  );

  const post = useMutation({
    mutationFn: (id: number) => svc.post(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["invoices", companyId] }),
  });
  const voidInvoice = useMutation({
    mutationFn: (id: number) => svc.voidInvoice(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["invoices", companyId] }),
  });
  const deleteDraft = useMutation({
    mutationFn: (id: number) => svc.delete(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["invoices", companyId] }),
  });

  return (
    <div className="p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Invoices</h1>
          <p className="text-sm text-stone-500">
            Bills you send to customers. Press{" "}
            <kbd className="rounded border bg-stone-100 px-1 text-xs">n</kbd>{" "}
            for a new invoice.
          </p>
        </div>
        <button
          type="button"
          onClick={openNew}
          className="rounded bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700"
        >
          New invoice
        </button>
      </header>

      <div className="mb-4 flex items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-stone-500">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as InvoiceStatus | "")}
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="sent">Sent</option>
            <option value="partial">Partial</option>
            <option value="paid">Paid</option>
            <option value="void">Void</option>
          </select>
        </label>
      </div>

      {showCreate && (
        <CreateInvoiceForm
          companyId={companyId}
          customers={customersList ?? []}
          onClose={() => setShowCreate(false)}
        />
      )}

      {isLoading && <p className="text-sm text-stone-500">Loading\u2026</p>}
      {invoicesList && (
        <table className="w-full text-sm">
          <thead className="border-b text-left text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="py-2 pr-3">Number</th>
              <th className="py-2 pr-3">Customer</th>
              <th className="py-2 pr-3">Date</th>
              <th className="py-2 pr-3">Due</th>
              <th className="py-2 pr-3 text-right">Total</th>
              <th className="py-2 pr-3 text-right">Paid</th>
              <th className="py-2 pr-3 text-right">Balance</th>
              <th className="py-2 pr-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {invoicesList.map((inv) => (
              <tr key={inv.id} className="border-b">
                <td className="py-2 pr-3 font-mono text-xs">{inv.number}</td>
                <td className="py-2 pr-3">
                  {customerById.get(inv.customer_id)?.name ?? `#${inv.customer_id}`}
                </td>
                <td className="py-2 pr-3 text-xs text-stone-600">
                  {inv.invoice_date}
                </td>
                <td className="py-2 pr-3 text-xs text-stone-600">
                  {inv.due_date}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatCents(inv.total_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums text-stone-500">
                  {formatCents(inv.amount_paid_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-medium">
                  {formatCents(inv.balance_cents)}
                </td>
                <td className={`py-2 pr-3 text-xs ${STATUS_COLORS[inv.status]}`}>
                  {inv.status}
                </td>
                <td className="py-2 pr-3 text-right">
                  {inv.status === "draft" && (
                    <>
                      <button
                        type="button"
                        onClick={() => post.mutate(inv.id)}
                        className="mr-2 text-xs text-stone-900 underline hover:text-stone-700"
                      >
                        post
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (confirm(`Delete draft ${inv.number}?`)) {
                            deleteDraft.mutate(inv.id);
                          }
                        }}
                        className="text-xs text-stone-500 underline hover:text-stone-800"
                      >
                        delete
                      </button>
                    </>
                  )}
                  {(inv.status === "sent" ||
                    inv.status === "partial" ||
                    inv.status === "paid") && (
                    <button
                      type="button"
                      onClick={() => {
                        if (confirm(`Void invoice ${inv.number}?`)) {
                          voidInvoice.mutate(inv.id);
                        }
                      }}
                      className="text-xs text-rose-600 underline hover:text-rose-800"
                    >
                      void
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {invoicesList.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  className="py-8 text-center text-stone-400"
                >
                  No invoices yet. Press{" "}
                  <kbd className="rounded border bg-stone-100 px-1 text-xs">
                    n
                  </kbd>{" "}
                  to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

function CreateInvoiceForm({
  companyId,
  customers,
  onClose,
}: {
  companyId: string;
  customers: Customer[];
  onClose: () => void;
}) {
  const svc = invoicesApi(companyId);
  const acctSvc = accountsApi(companyId);
  const qc = useQueryClient();

  const { data: accountsList } = useQuery<Account[]>({
    queryKey: ["accounts", companyId, false],
    queryFn: () => acctSvc.list(false),
  });
  const incomeAccounts = (accountsList ?? []).filter((a) => a.type === "income");

  const today = new Date().toISOString().slice(0, 10);
  const in30 = new Date(Date.now() + 30 * 86400_000)
    .toISOString()
    .slice(0, 10);

  const [number, setNumber] = useState("INV-");
  const [customerId, setCustomerId] = useState<number | "">("");
  const [invoiceDate, setInvoiceDate] = useState(today);
  const [dueDate, setDueDate] = useState(in30);
  const [description, setDescription] = useState("");
  const [accountId, setAccountId] = useState<number | "">("");
  const [quantity, setQuantity] = useState("1");
  const [price, setPrice] = useState("0.00");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => {
      if (!customerId || !accountId) {
        throw new Error("customer and account required");
      }
      const qtyMilli = Math.round(parseFloat(quantity || "0") * 1000);
      const priceCents = parseDollars(price);
      return svc.create({
        number,
        customer_id: customerId,
        invoice_date: invoiceDate,
        due_date: dueDate,
        terms: "net_30",
        lines: [
          {
            account_id: accountId,
            description: description || undefined,
            quantity_milli: qtyMilli,
            unit_price_cents: priceCents,
          },
        ],
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices", companyId] });
      onClose();
    },
    onError: (e: unknown) => {
      if (e instanceof ApiError) {
        setError(typeof e.detail === "string" ? e.detail : e.message);
      } else if (e instanceof Error) {
        setError(e.message);
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
      className="mb-6 space-y-3 rounded border border-stone-200 bg-stone-50 p-4 text-sm"
    >
      <div className="grid grid-cols-4 gap-3">
        <label className="flex flex-col">
          <span className="text-xs text-stone-500">Number</span>
          <input
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            required
            className="rounded border border-stone-300 px-2 py-1"
          />
        </label>
        <label className="flex flex-col">
          <span className="text-xs text-stone-500">Customer</span>
          <select
            value={customerId}
            onChange={(e) =>
              setCustomerId(e.target.value ? Number(e.target.value) : "")
            }
            required
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">Pick customer\u2026</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col">
          <span className="text-xs text-stone-500">Invoice date</span>
          <input
            type="date"
            value={invoiceDate}
            onChange={(e) => setInvoiceDate(e.target.value)}
            required
            className="rounded border border-stone-300 px-2 py-1"
          />
        </label>
        <label className="flex flex-col">
          <span className="text-xs text-stone-500">Due date</span>
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            required
            className="rounded border border-stone-300 px-2 py-1"
          />
        </label>
      </div>

      <div className="grid grid-cols-5 gap-3 border-t border-stone-200 pt-3">
        <label className="col-span-2 flex flex-col">
          <span className="text-xs text-stone-500">Line description</span>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="rounded border border-stone-300 px-2 py-1"
          />
        </label>
        <label className="flex flex-col">
          <span className="text-xs text-stone-500">Account (income)</span>
          <select
            value={accountId}
            onChange={(e) =>
              setAccountId(e.target.value ? Number(e.target.value) : "")
            }
            required
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">Pick\u2026</option>
            {incomeAccounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} {a.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col">
          <span className="text-xs text-stone-500">Quantity</span>
          <input
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="rounded border border-stone-300 px-2 py-1 text-right tabular-nums"
          />
        </label>
        <label className="flex flex-col">
          <span className="text-xs text-stone-500">Rate ($)</span>
          <input
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="rounded border border-stone-300 px-2 py-1 text-right tabular-nums"
          />
        </label>
      </div>

      {error && <p className="text-xs text-rose-700">Error: {error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded bg-stone-900 px-3 py-1 text-white hover:bg-stone-700 disabled:opacity-50"
        >
          {create.isPending ? "Saving\u2026" : "Save draft"}
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
