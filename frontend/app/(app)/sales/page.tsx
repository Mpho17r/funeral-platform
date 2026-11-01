"use client";

import { useEffect, useState } from "react";
import { Plus, ReceiptText } from "lucide-react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
import { formatRand, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";
import { docStatusLabel, docStatusTone, type SalesDoc } from "@/lib/sales";

export default function SalesPage() {
  const router = useRouter();
  const { can } = useCurrentUser();
  const [items, setItems] = useState<SalesDoc[]>([]);
  const [type, setType] = useState("");
  const [state, setState] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    api
      .get<{ total: number; items: SalesDoc[] }>("/sales/documents", {
        params: { ...(type && { document_type: type }), ...(state && { state }) },
      })
      .then((r) => {
        if (!live) return;
        setItems(r.data.items);
        setError("");
      })
      .catch((err) => live && setError(getApiErrorMessage(err, "Could not load.")))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [type, state]);

  return (
    <main className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <ReceiptText size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Quotes &amp; invoices</h1>
            <p className="text-sm text-slate-500">Bill your customers, print, and record payments.</p>
          </div>
        </div>
        {can("sales.manage") && (
          <button
            type="button"
            onClick={() => router.push("/sales/new")}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"
          >
            <Plus size={16} /> New
          </button>
        )}
      </header>

      <div className="flex flex-wrap gap-3">
        <select className={`${inputClass} !w-auto`} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">Quotes and invoices</option>
          <option value="invoice">Invoices</option>
          <option value="quote">Quotes</option>
        </select>
        <select className={`${inputClass} !w-auto`} value={state} onChange={(e) => setState(e.target.value)}>
          <option value="">Any payment status</option>
          <option value="unpaid">Unpaid</option>
          <option value="partial">Part paid</option>
          <option value="paid">Paid</option>
          <option value="overdue">Overdue</option>
        </select>
      </div>

      {error && <ErrorNote message={error} />}

      <div className="overflow-x-auto rounded-2xl border bg-white">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Number</th>
              <th className="px-4 py-3">Customer</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Total</th>
              <th className="px-4 py-3 text-right">Balance</th>
            </tr>
          </thead>
          <tbody>
            {items.map((d) => (
              <tr
                key={d.id}
                tabIndex={0}
                onClick={() => router.push(`/sales/${d.id}`)}
                onKeyDown={(e) => e.key === "Enter" && router.push(`/sales/${d.id}`)}
                className="cursor-pointer border-t hover:bg-slate-50"
              >
                <td className="px-4 py-3 font-medium">
                  {d.number ?? "Draft"}
                  <span className="ml-2 text-xs uppercase text-slate-400">{d.document_type}</span>
                </td>
                <td className="px-4 py-3">{d.customer_name}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${docStatusTone(d)}`}>
                    {docStatusLabel(d)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">{formatRand(d.total)}</td>
                <td className="px-4 py-3 text-right">
                  {d.document_type === "invoice" && d.status === "issued" ? formatRand(d.balance) : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && items.length === 0 && (
          <p className="px-6 py-12 text-center text-sm text-slate-500">Nothing here yet.</p>
        )}
      </div>
    </main>
  );
}
