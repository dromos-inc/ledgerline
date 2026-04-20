// Bill list with inline actions (post, void, delete) and a simple create form.
// AP mirror of Invoices.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState, type FormEvent } from "react";
import {
  accounts as accountsApi,
  ApiError,
  bills as billsApi,
  formatCents,
  parseDollars,
  vendors as vendorsApi,
  type Account,
  type Bill,
  type BillStatus,
  type Vendor,
} from "../api";
import { useShortcut } from "../shortcuts";

interface Props {
  companyId: string;
}

const STATUS_COLORS: Record<BillStatus, string> = {
  draft: "text-stone-500",
  open: "text-stone-900",
  partial: "text-amber-700",
  paid: "text-emerald-700",
  void: "text-rose-700 line-through",
};

export function Bills({ companyId }: Props) {
  const svc = billsApi(companyId);
  const vendSvc = vendorsApi(companyId);
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<BillStatus | "">("");
  const [showCreate, setShowCreate] = useState(false);

  const { data: billsList, isLoading } = useQuery<Bill[]>({
    queryKey: ["bills", companyId, statusFilter],
    queryFn: () =>
      svc.list(statusFilter ? { status: statusFilter } : undefined),
  });
  const { data: vendorsList } = useQuery<Vendor[]>({
    queryKey: ["vendors", companyId, false, ""],
    queryFn: () => vendSvc.list(false, undefined),
  });
  const vendorById = new Map((vendorsList ?? []).map((v) => [v.id, v]));

  const openNew = useCallback(() => setShowCreate(true), []);
  useShortcut(
    {
      id: "n",
      description: "New bill",
      group: "Bills",
      when: () => !showCreate,
    },
    openNew,
  );

  const post = useMutation({
    mutationFn: (id: number) => svc.post(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["bills", companyId] }),
  });
  const voidBill = useMutation({
    mutationFn: (id: number) => svc.voidBill(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["bills", companyId] }),
  });
  const deleteDraft = useMutation({
    mutationFn: (id: number) => svc.delete(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["bills", companyId] }),
  });

  return (
    <div className="p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Bills</h1>
          <p className="text-sm text-stone-500">
            Bills you owe vendors. Press{" "}
            <kbd className="rounded border bg-stone-100 px-1 text-xs">n</kbd>{" "}
            for a new bill.
          </p>
        </div>
        <button
          type="button"
          onClick={openNew}
          className="rounded bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700"
        >
          New bill
        </button>
      </header>

      <div className="mb-4 flex items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-stone-500">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as BillStatus | "")}
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="open">Open</option>
            <option value="partial">Partial</option>
            <option value="paid">Paid</option>
            <option value="void">Void</option>
          </select>
        </label>
      </div>

      {showCreate && (
        <CreateBillForm
          companyId={companyId}
          vendors={vendorsList ?? []}
          onClose={() => setShowCreate(false)}
        />
      )}

      {isLoading && <p className="text-sm text-stone-500">Loading&hellip;</p>}
      {billsList && (
        <table className="w-full text-sm">
          <thead className="border-b text-left text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="py-2 pr-3">Number</th>
              <th className="py-2 pr-3">Vendor</th>
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
            {billsList.map((bill) => (
              <tr key={bill.id} className="border-b">
                <td className="py-2 pr-3 font-mono text-xs">{bill.number}</td>
                <td className="py-2 pr-3">
                  {vendorById.get(bill.vendor_id)?.name ?? `#${bill.vendor_id}`}
                </td>
                <td className="py-2 pr-3 text-xs text-stone-600">
                  {bill.bill_date}
                </td>
                <td className="py-2 pr-3 text-xs text-stone-600">
                  {bill.due_date}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatCents(bill.total_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums text-stone-500">
                  {formatCents(bill.amount_paid_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-medium">
                  {formatCents(bill.balance_cents)}
                </td>
                <td className={`py-2 pr-3 text-xs ${STATUS_COLORS[bill.status]}`}>
                  {bill.status}
                </td>
                <td className="py-2 pr-3 text-right">
                  {bill.status === "draft" && (
                    <>
                      <button
                        type="button"
                        onClick={() => post.mutate(bill.id)}
                        className="mr-2 text-xs text-stone-900 underline hover:text-stone-700"
                      >
                        post
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (confirm(`Delete draft ${bill.number}?`)) {
                            deleteDraft.mutate(bill.id);
                          }
                        }}
                        className="text-xs text-stone-500 underline hover:text-stone-800"
                      >
                        delete
                      </button>
                    </>
                  )}
                  {(bill.status === "open" ||
                    bill.status === "partial" ||
                    bill.status === "paid") && (
                    <button
                      type="button"
                      onClick={() => {
                        if (confirm(`Void bill ${bill.number}?`)) {
                          voidBill.mutate(bill.id);
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
            {billsList.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  className="py-8 text-center text-stone-400"
                >
                  No bills yet. Press{" "}
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

function CreateBillForm({
  companyId,
  vendors,
  onClose,
}: {
  companyId: string;
  vendors: Vendor[];
  onClose: () => void;
}) {
  const svc = billsApi(companyId);
  const acctSvc = accountsApi(companyId);
  const qc = useQueryClient();

  const { data: accountsList } = useQuery<Account[]>({
    queryKey: ["accounts", companyId, false],
    queryFn: () => acctSvc.list(false),
  });
  // Bills debit expense (and sometimes asset, for capex). Offer both.
  const expenseOrAssetAccounts = (accountsList ?? []).filter(
    (a) => a.type === "expense" || a.type === "asset",
  );

  const today = new Date().toISOString().slice(0, 10);
  const in30 = new Date(Date.now() + 30 * 86400_000)
    .toISOString()
    .slice(0, 10);

  const [number, setNumber] = useState("BILL-");
  const [vendorId, setVendorId] = useState<number | "">("");
  const [billDate, setBillDate] = useState(today);
  const [dueDate, setDueDate] = useState(in30);
  const [description, setDescription] = useState("");
  const [accountId, setAccountId] = useState<number | "">("");
  const [quantity, setQuantity] = useState("1");
  const [price, setPrice] = useState("0.00");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => {
      if (!vendorId || !accountId) {
        throw new Error("vendor and account required");
      }
      const qtyMilli = Math.round(parseFloat(quantity || "0") * 1000);
      const priceCents = parseDollars(price);
      return svc.create({
        number,
        vendor_id: vendorId,
        bill_date: billDate,
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
      qc.invalidateQueries({ queryKey: ["bills", companyId] });
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
          <span className="text-xs text-stone-500">Vendor</span>
          <select
            value={vendorId}
            onChange={(e) =>
              setVendorId(e.target.value ? Number(e.target.value) : "")
            }
            required
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">Pick vendor&hellip;</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col">
          <span className="text-xs text-stone-500">Bill date</span>
          <input
            type="date"
            value={billDate}
            onChange={(e) => setBillDate(e.target.value)}
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
          <span className="text-xs text-stone-500">Account (expense/asset)</span>
          <select
            value={accountId}
            onChange={(e) =>
              setAccountId(e.target.value ? Number(e.target.value) : "")
            }
            required
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">Pick&hellip;</option>
            {expenseOrAssetAccounts.map((a) => (
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
          {create.isPending ? "Saving&hellip;" : "Save draft"}
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