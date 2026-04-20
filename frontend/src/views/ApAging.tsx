// AP aging report + sub-ledger reconciliation canary banner (AP side).

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  formatCents,
  reports as reportsApi,
  type ApAgingReport,
  type ReconciliationReport,
} from "../api";

interface Props {
  companyId: string;
}

export function ApAging({ companyId }: Props) {
  const svc = reportsApi(companyId);
  const today = new Date().toISOString().slice(0, 10);
  const [asOfDate, setAsOfDate] = useState(today);

  const { data: aging, isLoading } = useQuery<ApAgingReport>({
    queryKey: ["ap-aging", companyId, asOfDate],
    queryFn: () => svc.apAging(asOfDate),
  });

  const { data: recon } = useQuery<ReconciliationReport>({
    queryKey: ["recon", companyId, asOfDate],
    queryFn: () => svc.reconciliation(asOfDate),
  });

  const drift = recon ? recon.ap_difference_cents : 0;

  return (
    <div className="p-6">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">AP aging</h1>
          <p className="text-sm text-stone-500">
            Outstanding bill balances by vendor and bucket.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-stone-500">As of:</span>
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="rounded border border-stone-300 px-2 py-1"
          />
        </label>
      </header>

      {recon && (
        <div
          className={`mb-4 rounded border p-3 text-xs ${
            drift === 0
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-rose-300 bg-rose-50 text-rose-800"
          }`}
        >
          {drift === 0 ? (
            <>
              Reconciliation OK. AP control{" "}
              <strong>{formatCents(recon.ap_control_balance_cents)}</strong>{" "}
              matches sub-ledger{" "}
              <strong>
                {formatCents(
                  recon.ap_sub_ledger_cents -
                    recon.ap_unapplied_credits_cents,
                )}
              </strong>{" "}
              (sub-ledger {formatCents(recon.ap_sub_ledger_cents)} &minus;
              unapplied credit{" "}
              {formatCents(recon.ap_unapplied_credits_cents)}).
            </>
          ) : (
            <>
              Reconciliation DRIFT: control ={" "}
              {formatCents(recon.ap_control_balance_cents)}, sub-ledger ={" "}
              {formatCents(recon.ap_sub_ledger_cents)}, unapplied ={" "}
              {formatCents(recon.ap_unapplied_credits_cents)}, difference ={" "}
              {formatCents(drift)}.
            </>
          )}
        </div>
      )}

      {isLoading && <p className="text-sm text-stone-500">Loading&hellip;</p>}

      {aging && (
        <table className="w-full text-sm">
          <thead className="border-b text-left text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="py-2 pr-3">Vendor</th>
              <th className="py-2 pr-3 text-right">Current</th>
              <th className="py-2 pr-3 text-right">1&ndash;30</th>
              <th className="py-2 pr-3 text-right">31&ndash;60</th>
              <th className="py-2 pr-3 text-right">61&ndash;90</th>
              <th className="py-2 pr-3 text-right">90+</th>
              <th className="py-2 pr-3 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {aging.rows.map((row) => (
              <tr key={row.vendor_id} className="border-b">
                <td className="py-2 pr-3">
                  <div>{row.vendor_name}</div>
                  <div className="font-mono text-xs text-stone-500">
                    {row.vendor_code}
                  </div>
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatCents(row.current_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatCents(row.d1_30_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatCents(row.d31_60_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatCents(row.d61_90_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums text-rose-700">
                  {formatCents(row.over_90_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-semibold">
                  {formatCents(row.total_cents)}
                </td>
              </tr>
            ))}
            {aging.rows.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="py-8 text-center text-stone-400"
                >
                  Nothing outstanding as of {aging.as_of_date}.
                </td>
              </tr>
            )}
            {aging.rows.length > 0 && (
              <tr className="border-t-2 border-stone-900 bg-stone-50">
                <td className="py-2 pr-3 font-semibold uppercase tracking-wide text-xs text-stone-600">
                  Total
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-semibold">
                  {formatCents(aging.totals.current_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-semibold">
                  {formatCents(aging.totals.d1_30_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-semibold">
                  {formatCents(aging.totals.d31_60_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-semibold">
                  {formatCents(aging.totals.d61_90_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-semibold">
                  {formatCents(aging.totals.over_90_cents)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums font-bold">
                  {formatCents(aging.totals.total_cents)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}