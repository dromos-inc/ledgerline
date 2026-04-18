// Trial balance, P&L, balance sheet — all three in one module so shared
// form state (date range, basis) stays co-located.

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  formatCents,
  reports as reportsApi,
  type BalanceSheetReport,
  type Basis,
  type ProfitLossReport,
  type TrialBalanceReport,
} from "../api";

interface Props {
  companyId: string;
}

type ReportKind = "trial-balance" | "profit-loss" | "balance-sheet";

const KINDS: { key: ReportKind; label: string }[] = [
  { key: "trial-balance", label: "Trial Balance" },
  { key: "profit-loss", label: "Profit & Loss" },
  { key: "balance-sheet", label: "Balance Sheet" },
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function yearStart(): string {
  const now = new Date();
  return `${now.getFullYear()}-01-01`;
}

export function Reports({ companyId }: Props) {
  const [kind, setKind] = useState<ReportKind>("trial-balance");
  const [asOfDate, setAsOfDate] = useState(today());
  const [startDate, setStartDate] = useState(yearStart());
  const [endDate, setEndDate] = useState(today());
  const [basis, setBasis] = useState<Basis>("accrual");
  const [comparePrior, setComparePrior] = useState(false);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Reports</h2>
          <p className="mt-1 text-sm text-ink-500">
            Double-entry verification, income statement, position.
          </p>
        </div>
        <nav className="flex items-center gap-2">
          {KINDS.map((k) => (
            <button
              key={k.key}
              type="button"
              onClick={() => setKind(k.key)}
              className={
                kind === k.key
                  ? "btn btn-primary"
                  : "btn"
              }
            >
              {k.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="mt-5 flex flex-wrap items-end gap-4 rounded border border-ink-200 bg-white p-4">
        {kind === "profit-loss" ? (
          <>
            <DateInput label="Start" value={startDate} onChange={setStartDate} />
            <DateInput label="End" value={endDate} onChange={setEndDate} />
            <label className="text-sm">
              <span className="mr-2 text-ink-500">Basis:</span>
              <select
                className="input inline-block w-28"
                value={basis}
                onChange={(e) => setBasis(e.target.value as Basis)}
              >
                <option value="accrual">Accrual</option>
                <option value="cash">Cash</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={comparePrior}
                onChange={(e) => setComparePrior(e.target.checked)}
              />
              Compare prior period
            </label>
            <a
              className="btn ml-auto"
              href={`/api/v1/companies/${companyId}/export/reports/profit-loss.csv?start_date=${startDate}&end_date=${endDate}&basis=${basis}`}
              target="_blank"
              rel="noreferrer"
            >
              Export CSV
            </a>
          </>
        ) : (
          <>
            <DateInput label="As of" value={asOfDate} onChange={setAsOfDate} />
            <label className="text-sm">
              <span className="mr-2 text-ink-500">Basis:</span>
              <select
                className="input inline-block w-28"
                value={basis}
                onChange={(e) => setBasis(e.target.value as Basis)}
              >
                <option value="accrual">Accrual</option>
                <option value="cash">Cash</option>
              </select>
            </label>
            <a
              className="btn ml-auto"
              href={`/api/v1/companies/${companyId}/export/reports/${kind}.csv?as_of_date=${asOfDate}&basis=${basis}`}
              target="_blank"
              rel="noreferrer"
            >
              Export CSV
            </a>
          </>
        )}
      </div>

      <div className="mt-5">
        {kind === "trial-balance" && (
          <TrialBalance
            companyId={companyId}
            asOfDate={asOfDate}
            basis={basis}
          />
        )}
        {kind === "profit-loss" && (
          <ProfitLoss
            companyId={companyId}
            startDate={startDate}
            endDate={endDate}
            basis={basis}
            comparePrior={comparePrior}
          />
        )}
        {kind === "balance-sheet" && (
          <BalanceSheet
            companyId={companyId}
            asOfDate={asOfDate}
            basis={basis}
          />
        )}
      </div>
    </div>
  );
}

function DateInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="text-sm">
      <span className="mr-2 text-ink-500">{label}:</span>
      <input
        type="date"
        className="input inline-block w-40"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

// --- Trial balance ---------------------------------------------------------

function TrialBalance({
  companyId,
  asOfDate,
  basis,
}: {
  companyId: string;
  asOfDate: string;
  basis: Basis;
}) {
  const { data, isLoading } = useQuery<TrialBalanceReport>({
    queryKey: ["tb", companyId, asOfDate, basis],
    queryFn: () => reportsApi(companyId).trialBalance(asOfDate, basis),
  });
  if (isLoading) return <Spinner />;
  if (!data) return null;
  return (
    <div className="rounded border border-ink-200 bg-white">
      <Banner
        balanced={data.balanced}
        asOf={data.as_of_date}
        basis={data.basis}
      />
      <table className="table">
        <thead>
          <tr>
            <th className="w-28">Code</th>
            <th>Account</th>
            <th className="w-24">Type</th>
            <th className="w-36 text-right">Debit</th>
            <th className="w-36 text-right">Credit</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.account_id}>
              <td className="font-mono">{r.account_code}</td>
              <td className="font-medium">{r.account_name}</td>
              <td className="text-ink-500">{r.account_type}</td>
              <td className="tabular text-right">
                {r.debit_cents > 0 ? formatCents(r.debit_cents) : "—"}
              </td>
              <td className="tabular text-right">
                {r.credit_cents > 0 ? formatCents(r.credit_cents) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td />
            <td className="text-right font-semibold">TOTAL</td>
            <td />
            <td className="tabular text-right font-semibold">
              {formatCents(data.total_debit_cents)}
            </td>
            <td className="tabular text-right font-semibold">
              {formatCents(data.total_credit_cents)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// --- P&L -------------------------------------------------------------------

function ProfitLoss({
  companyId,
  startDate,
  endDate,
  basis,
  comparePrior,
}: {
  companyId: string;
  startDate: string;
  endDate: string;
  basis: Basis;
  comparePrior: boolean;
}) {
  const { data, isLoading } = useQuery<ProfitLossReport>({
    queryKey: ["pl", companyId, startDate, endDate, basis, comparePrior],
    queryFn: () =>
      reportsApi(companyId).profitLoss(startDate, endDate, basis, comparePrior),
  });
  if (isLoading) return <Spinner />;
  if (!data) return null;
  return (
    <div className="rounded border border-ink-200 bg-white">
      <div className="border-b border-ink-200 px-4 py-2 text-xs text-ink-500">
        {data.start_date} → {data.end_date} · {data.basis}
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Account</th>
            <th className="w-40 text-right">Amount</th>
            {comparePrior && <th className="w-40 text-right">Prior</th>}
          </tr>
        </thead>
        <tbody>
          <SectionHeader label={data.income.label} />
          {data.income.rows.map((r) => (
            <tr key={r.account_id}>
              <td>
                <span className="font-mono text-ink-500">
                  {r.account_code}
                </span>{" "}
                {r.account_name}
              </td>
              <td className="tabular text-right">
                {formatCents(r.amount_cents)}
              </td>
              {comparePrior && (
                <td className="tabular text-right text-ink-500">
                  {r.prior_amount_cents != null
                    ? formatCents(r.prior_amount_cents)
                    : "—"}
                </td>
              )}
            </tr>
          ))}
          <Subtotal
            label={`Total ${data.income.label}`}
            amount={data.income.subtotal_cents}
            prior={data.income.prior_subtotal_cents}
            showPrior={comparePrior}
          />
          <SectionHeader label={data.expenses.label} />
          {data.expenses.rows.map((r) => (
            <tr key={r.account_id}>
              <td>
                <span className="font-mono text-ink-500">
                  {r.account_code}
                </span>{" "}
                {r.account_name}
              </td>
              <td className="tabular text-right">
                {formatCents(r.amount_cents)}
              </td>
              {comparePrior && (
                <td className="tabular text-right text-ink-500">
                  {r.prior_amount_cents != null
                    ? formatCents(r.prior_amount_cents)
                    : "—"}
                </td>
              )}
            </tr>
          ))}
          <Subtotal
            label={`Total ${data.expenses.label}`}
            amount={data.expenses.subtotal_cents}
            prior={data.expenses.prior_subtotal_cents}
            showPrior={comparePrior}
          />
          <tr className="border-t-2 border-ink-300">
            <td className="py-3 font-semibold uppercase tracking-wider">
              Net income
            </td>
            <td className="tabular py-3 text-right text-lg font-semibold">
              {formatCents(data.net_income_cents)}
            </td>
            {comparePrior && (
              <td className="tabular py-3 text-right text-ink-500">
                {data.prior_net_income_cents != null
                  ? formatCents(data.prior_net_income_cents)
                  : "—"}
              </td>
            )}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// --- Balance sheet ---------------------------------------------------------

function BalanceSheet({
  companyId,
  asOfDate,
  basis,
}: {
  companyId: string;
  asOfDate: string;
  basis: Basis;
}) {
  const { data, isLoading } = useQuery<BalanceSheetReport>({
    queryKey: ["bs", companyId, asOfDate, basis],
    queryFn: () => reportsApi(companyId).balanceSheet(asOfDate, basis),
  });
  if (isLoading) return <Spinner />;
  if (!data) return null;
  return (
    <div className="rounded border border-ink-200 bg-white">
      <Banner
        balanced={data.balanced}
        asOf={data.as_of_date}
        basis={data.basis}
      />
      {!data.balanced && (
        <div className="border-b border-danger bg-red-50 px-4 py-2 text-sm text-danger">
          Equation does not balance. Difference:{" "}
          <span className="tabular font-semibold">
            {formatCents(data.equation_difference_cents)}
          </span>
          . Likely a missing closing entry.
        </div>
      )}
      <table className="table">
        <tbody>
          <BSSectionView label={data.assets.label} section={data.assets} />
          <BSSectionView
            label={data.liabilities.label}
            section={data.liabilities}
          />
          <BSSectionView label={data.equity.label} section={data.equity} />
          <tr className="border-t-2 border-ink-300">
            <td className="py-3 font-semibold uppercase tracking-wider">
              Liabilities + Equity
            </td>
            <td className="tabular py-3 text-right text-lg font-semibold">
              {formatCents(
                data.liabilities.subtotal_cents + data.equity.subtotal_cents,
              )}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function BSSectionView({
  label,
  section,
}: {
  label: string;
  section: { rows: { account_id: number; account_code: string; account_name: string; balance_cents: number }[]; subtotal_cents: number };
}) {
  return (
    <>
      <SectionHeader label={label} />
      {section.rows.map((r) => (
        <tr key={r.account_id}>
          <td>
            <span className="font-mono text-ink-500">{r.account_code}</span>{" "}
            {r.account_name}
          </td>
          <td className="tabular text-right">{formatCents(r.balance_cents)}</td>
        </tr>
      ))}
      <tr>
        <td className="font-medium">Total {label}</td>
        <td className="tabular border-t border-ink-300 text-right font-semibold">
          {formatCents(section.subtotal_cents)}
        </td>
      </tr>
    </>
  );
}

function SectionHeader({ label }: { label: string }) {
  return (
    <tr>
      <td
        colSpan={3}
        className="bg-ink-50 text-xs font-semibold uppercase tracking-wider text-ink-500"
      >
        {label}
      </td>
    </tr>
  );
}

function Subtotal({
  label,
  amount,
  prior,
  showPrior,
}: {
  label: string;
  amount: number;
  prior: number | null | undefined;
  showPrior: boolean;
}) {
  return (
    <tr>
      <td className="font-medium">{label}</td>
      <td className="tabular border-t border-ink-300 text-right font-semibold">
        {formatCents(amount)}
      </td>
      {showPrior && (
        <td className="tabular border-t border-ink-300 text-right text-ink-500">
          {prior != null ? formatCents(prior) : "—"}
        </td>
      )}
    </tr>
  );
}

function Banner({
  balanced,
  asOf,
  basis,
}: {
  balanced: boolean;
  asOf: string;
  basis: Basis;
}) {
  return (
    <div className="flex items-center justify-between border-b border-ink-200 px-4 py-2 text-xs text-ink-500">
      <span>
        As of <span className="font-mono text-ink-700">{asOf}</span> · {basis}
      </span>
      <span
        className={
          balanced
            ? "font-mono text-xs text-success"
            : "font-mono text-xs text-danger"
        }
      >
        {balanced ? "✓ Balanced" : "✕ Not balanced"}
      </span>
    </div>
  );
}

function Spinner() {
  return (
    <p className="p-4 font-mono text-sm text-ink-500">Loading…</p>
  );
}
