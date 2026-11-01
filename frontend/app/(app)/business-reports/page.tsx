"use client";

import { useEffect, useState } from "react";
import { Download, FileBarChart, Printer } from "lucide-react";

import api from "@/lib/api";
import { categoryLabel, formatRand, getApiErrorMessage } from "@/lib/format";
import { inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";
import { esc, money, printHtml } from "@/lib/printDocument";

type Report = {
  date_from: string;
  date_to: string;
  income: number;
  expenses: number;
  profit: number;
  result: "profit" | "loss";
  income_by_category: { category: string; total: number }[];
  expenses_by_category: { category: string; total: number }[];
  trend: { month: string; income: number; expenses: number; profit: number }[];
  sales: { invoices_issued: number; invoiced: number; collected: number; tax_charged: number };
  top_customers: { customer_id: string; customer_name: string; invoiced: number; paid: number }[];
};

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function preset(name: string): [string, string] {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  switch (name) {
    case "last":
      return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))];
    case "quarter":
      return [iso(new Date(y, Math.floor(m / 3) * 3, 1)), iso(now)];
    case "year":
      return [iso(new Date(y, 0, 1)), iso(now)];
    default:
      return [iso(new Date(y, m, 1)), iso(now)];
  }
}

const monthName = (value: string) =>
  new Date(value).toLocaleDateString("en-ZA", { month: "short", year: "numeric" });

export default function BusinessReportsPage() {
  const [[from, to], setRange] = useState<[string, string]>(preset("month"));
  const [data, setData] = useState<Report | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    api
      .get<Report>("/business-reports/overview", { params: { date_from: from, date_to: to } })
      .then((r) => {
        if (!live) return;
        setData(r.data);
        setError("");
      })
      .catch((err) => live && setError(getApiErrorMessage(err, "Could not load the report.")));
    return () => {
      live = false;
    };
  }, [from, to]);

  async function download() {
    try {
      const r = await api.get("/business-reports/export", {
        params: { date_from: from, date_to: to },
        responseType: "blob",
      });
      const url = URL.createObjectURL(r.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${from}-to-${to}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not download the report."));
    }
  }

  function print() {
    if (!data) return;
    const rows = (list: { category: string; total: number }[]) =>
      list.map((r) => `<tr><td>${esc(categoryLabel(r.category))}</td><td class="n">${money(r.total)}</td></tr>`).join("");
    printHtml(`<!doctype html><html><head><meta charset="utf-8"><title>Profit and loss</title>
<style>body{font-family:Arial,sans-serif;margin:32px;font-size:13px;color:#111}h1{margin:0 0 4px}
table{width:100%;border-collapse:collapse;margin:8px 0 20px}td,th{border-bottom:1px solid #ddd;padding:6px;text-align:left}
.n{text-align:right}.big{font-size:16px;font-weight:bold}</style></head><body>
<h1>Profit and loss</h1><p>${esc(data.date_from)} to ${esc(data.date_to)}</p>
<h3>Money received: ${money(data.income)}</h3><table>${rows(data.income_by_category)}</table>
<h3>Money spent: ${money(data.expenses)}</h3><table>${rows(data.expenses_by_category)}</table>
<p class="big">${data.result === "profit" ? "Profit" : "Loss"}: ${money(Math.abs(data.profit))}</p>
<h3>Sales</h3><p>Invoiced ${money(data.sales.invoiced)} · Collected ${money(data.sales.collected)} · Tax charged ${money(data.sales.tax_charged)}</p>
<table><tr><th>Customer</th><th class="n">Invoiced</th><th class="n">Paid</th></tr>
${data.top_customers.map((c) => `<tr><td>${esc(c.customer_name)}</td><td class="n">${money(c.invoiced)}</td><td class="n">${money(c.paid)}</td></tr>`).join("")}</table>
</body></html>`);
  }

  return (
    <main className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <FileBarChart size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Reports</h1>
            <p className="text-sm text-slate-500">Profit and loss, sales and tax for any period.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={print} disabled={!data} className="flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-50">
            <Printer size={16} /> Print
          </button>
          <button type="button" onClick={download} className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white">
            <Download size={16} /> Excel (CSV)
          </button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {[
          ["month", "This month"],
          ["last", "Last month"],
          ["quarter", "This quarter"],
          ["year", "This year"],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setRange(preset(key))}
            className="rounded-full border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
          >
            {label}
          </button>
        ))}
        <input type="date" className={`${inputClass} !w-auto`} value={from} onChange={(e) => e.target.value && setRange([e.target.value, to])} />
        <span className="text-sm text-slate-500">to</span>
        <input type="date" className={`${inputClass} !w-auto`} value={to} onChange={(e) => e.target.value && setRange([from, e.target.value])} />
      </div>

      {error && <ErrorNote message={error} />}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Card label="Money received" value={formatRand(data.income)} />
            <Card label="Money spent" value={formatRand(data.expenses)} />
            <Card
              label={data.result === "profit" ? "Profit" : "Loss"}
              value={formatRand(Math.abs(data.profit))}
              tone={data.result === "profit" ? "text-emerald-700" : "text-red-700"}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Breakdown title="Where money came from" rows={data.income_by_category} />
            <Breakdown title="Where money went" rows={data.expenses_by_category} />
          </div>

          <section className="rounded-2xl border bg-white p-5">
            <h2 className="font-semibold">Sales</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-4">
              <Mini label="Invoices issued" value={String(data.sales.invoices_issued)} />
              <Mini label="Invoiced" value={formatRand(data.sales.invoiced)} />
              <Mini label="Collected" value={formatRand(data.sales.collected)} />
              <Mini label="Tax charged" value={formatRand(data.sales.tax_charged)} />
            </div>
          </section>

          {data.trend.length > 0 && (
            <section className="overflow-x-auto rounded-2xl border bg-white">
              <h2 className="px-5 pt-5 font-semibold">Month by month</h2>
              <table className="mt-2 w-full min-w-[28rem] text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-5 py-2">Month</th>
                    <th className="px-5 py-2 text-right">Received</th>
                    <th className="px-5 py-2 text-right">Spent</th>
                    <th className="px-5 py-2 text-right">Profit</th>
                  </tr>
                </thead>
                <tbody>
                  {data.trend.map((t) => (
                    <tr key={t.month} className="border-t">
                      <td className="px-5 py-2">{monthName(t.month)}</td>
                      <td className="px-5 py-2 text-right">{formatRand(t.income)}</td>
                      <td className="px-5 py-2 text-right">{formatRand(t.expenses)}</td>
                      <td className={`px-5 py-2 text-right font-medium ${t.profit < 0 ? "text-red-700" : ""}`}>
                        {formatRand(t.profit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section className="overflow-x-auto rounded-2xl border bg-white">
            <h2 className="px-5 pt-5 font-semibold">Sales by customer</h2>
            <table className="mt-2 w-full min-w-[28rem] text-left text-sm">
              <tbody>
                {data.top_customers.map((c) => (
                  <tr key={c.customer_id} className="border-t">
                    <td className="px-5 py-2 font-medium">{c.customer_name}</td>
                    <td className="px-5 py-2 text-right">{formatRand(c.invoiced)} invoiced</td>
                    <td className="px-5 py-2 text-right">{formatRand(c.paid)} paid</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.top_customers.length === 0 && (
              <p className="px-5 py-8 text-center text-sm text-slate-500">No sales in this period.</p>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function Card({ label, value, tone = "" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-2xl border bg-white p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 text-xl font-bold ${tone}`}>{value}</p>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  );
}

function Breakdown({ title, rows }: { title: string; rows: { category: string; total: number }[] }) {
  return (
    <section className="rounded-2xl border bg-white p-5">
      <h2 className="font-semibold">{title}</h2>
      <ul className="mt-2 divide-y text-sm">
        {rows.map((r) => (
          <li key={r.category} className="flex justify-between py-2">
            <span>{categoryLabel(r.category)}</span>
            <span>{formatRand(r.total)}</span>
          </li>
        ))}
        {rows.length === 0 && <li className="py-4 text-slate-500">Nothing in this period.</li>}
      </ul>
    </section>
  );
}
