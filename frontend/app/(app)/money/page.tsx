"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, PiggyBank, Plus, TrendingDown, TrendingUp } from "lucide-react";

import api from "@/lib/api";
import { formatRand, getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";
import { Dialog } from "@/components/Dialog";
import { useCurrentUser } from "@/components/CurrentUserProvider";

type Summary = {
  month: string;
  income: number;
  expenses: number;
  profit: number;
  result: "profit" | "loss";
  income_by_category: { category: string; total: number }[];
  expenses_by_category: { category: string; total: number }[];
  trend: { month: string; income: number; expenses: number; profit: number }[];
};
type Entry = {
  id: string;
  category: string;
  description: string;
  amount: number;
  income_date: string;
  reference: string | null;
  status: string;
  void_reason: string | null;
};

const monthName = (iso: string) =>
  new Date(iso).toLocaleDateString("en-ZA", { month: "short", year: "2-digit" });

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function MoneyPage() {
  const { can } = useCurrentUser();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    Promise.all([
      api.get<Summary>("/money/summary"),
      api.get<Entry[]>("/money/income", { params: { include_voided: true } }),
      api.get<{ income: string[] }>("/money/categories"),
    ])
      .then(([s, e, c]) => {
        setSummary(s.data);
        setEntries(e.data);
        setCategories(c.data.income);
      })
      .catch((err) => setError(getApiErrorMessage(err, "Could not load your money.")));
  }, [version]);

  async function voidEntry(entry: Entry) {
    const reason = window.prompt(`Why cancel "${entry.description}"? (It stays on record, marked cancelled.)`);
    if (!reason || reason.trim().length < 3) return;
    try {
      await api.post(`/money/income/${entry.id}/void`, { reason: reason.trim() });
      setVersion((v) => v + 1);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not cancel that entry."));
    }
  }

  const biggest = Math.max(1, ...(summary?.trend ?? []).flatMap((t) => [t.income, t.expenses]));

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <PiggyBank size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Money</h1>
            <p className="text-sm text-slate-500">What came in, what went out, and what is left.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Link href="/expenses" className="rounded-lg border px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
            Record an expense
          </Link>
          {can("income.manage") && (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="flex items-center gap-1 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white"
            >
              <Plus size={15} /> Money received
            </button>
          )}
        </div>
      </header>

      {error && <ErrorNote message={error} />}

      {!summary ? (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </p>
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border bg-white p-4">
              <p className="text-xs text-slate-500">Received this month</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">{formatRand(summary.income)}</p>
            </div>
            <div className="rounded-xl border bg-white p-4">
              <p className="text-xs text-slate-500">Spent this month</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">{formatRand(summary.expenses)}</p>
            </div>
            <div
              className={`rounded-xl border p-4 ${summary.result === "profit" ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}
            >
              <p className="flex items-center gap-1 text-xs text-slate-600">
                {summary.result === "profit" ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {summary.result === "profit" ? "Profit" : "Loss"} this month
              </p>
              <p
                className={`mt-1 text-2xl font-bold ${summary.result === "profit" ? "text-emerald-800" : "text-red-800"}`}
              >
                {formatRand(Math.abs(summary.profit))}
              </p>
            </div>
          </section>

          <section className="rounded-xl border bg-white p-4">
            <h2 className="mb-3 font-semibold text-slate-900">Month by month</h2>
            <div className="flex items-end gap-3 overflow-x-auto pb-1" role="img" aria-label="Income and expenses by month">
              {summary.trend.map((t) => (
                <div key={t.month} className="flex min-w-14 flex-1 flex-col items-center gap-1">
                  <div className="flex h-32 items-end gap-1">
                    <div
                      className="w-4 rounded-t bg-emerald-600"
                      style={{ height: `${(t.income / biggest) * 100}%` }}
                      title={`Received ${formatRand(t.income)}`}
                    />
                    <div
                      className="w-4 rounded-t bg-slate-400"
                      style={{ height: `${(t.expenses / biggest) * 100}%` }}
                      title={`Spent ${formatRand(t.expenses)}`}
                    />
                  </div>
                  <p className="text-xs text-slate-500">{monthName(t.month)}</p>
                  <p className={`text-xs font-medium ${t.profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                    {t.profit >= 0 ? "+" : "−"}
                    {formatRand(Math.abs(t.profit))}
                  </p>
                </div>
              ))}
            </div>
            <p className="mt-2 flex gap-4 text-xs text-slate-500">
              <span>
                <span className="mr-1 inline-block h-2 w-2 rounded bg-emerald-600" />
                Received
              </span>
              <span>
                <span className="mr-1 inline-block h-2 w-2 rounded bg-slate-400" />
                Spent
              </span>
            </p>
          </section>

          <section className="grid gap-3 sm:grid-cols-2">
            {[
              ["Where the money came from", summary.income_by_category],
              ["Where the money went", summary.expenses_by_category],
            ].map(([title, rows]) => (
              <div key={title as string} className="rounded-xl border bg-white p-4">
                <h2 className="mb-2 font-semibold text-slate-900">{title as string}</h2>
                {(rows as Summary["income_by_category"]).length === 0 ? (
                  <p className="text-sm text-slate-500">Nothing recorded this month.</p>
                ) : (
                  <ul className="space-y-1 text-sm">
                    {(rows as Summary["income_by_category"]).map((r) => (
                      <li key={r.category} className="flex justify-between">
                        <span className="text-slate-700">{r.category}</span>
                        <span className="font-medium tabular-nums">{formatRand(r.total)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </section>
        </>
      )}

      <section className="rounded-xl border bg-white">
        <h2 className="border-b p-4 font-semibold text-slate-900">Money received</h2>
        {entries === null ? null : entries.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500">Nothing recorded yet.</p>
        ) : (
          <ul className="divide-y">
            {entries.map((e) => (
              <li key={e.id} className="flex flex-wrap items-center gap-3 p-3 text-sm">
                <div className="min-w-0 flex-1">
                  <p className={`truncate font-medium ${e.status === "voided" ? "text-slate-400 line-through" : "text-slate-900"}`}>
                    {e.description}
                  </p>
                  <p className="text-xs text-slate-500">
                    {e.category} · {new Date(e.income_date).toLocaleDateString("en-ZA")}
                    {e.reference ? ` · ${e.reference}` : ""}
                    {e.status === "voided" ? ` · cancelled: ${e.void_reason}` : ""}
                  </p>
                </div>
                <span className="font-semibold tabular-nums">{formatRand(e.amount)}</span>
                {e.status !== "voided" && can("income.manage") && (
                  <button type="button" onClick={() => void voidEntry(e)} className="text-xs text-red-700 hover:underline">
                    Cancel
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {adding && (
        <AddIncome
          categories={categories}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            setVersion((v) => v + 1);
          }}
        />
      )}
    </main>
  );
}

function AddIncome({
  categories,
  onClose,
  onSaved,
}: {
  categories: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [category, setCategory] = useState(categories[0] ?? "");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setBusy(true);
      setError("");
      await api.post("/money/income", {
        category,
        description,
        amount: Number(amount).toFixed(2),
        income_date: date,
        reference: reference.trim() || null,
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save that."));
      setBusy(false);
    }
  }

  const input = "w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-slate-900";
  return (
    <Dialog title="Money received" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <label className="block text-sm">
          What was it for?
          <input className={input} value={description} onChange={(e) => setDescription(e.target.value)} required maxLength={500} />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            Amount (R)
            <input className={input} type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} required />
          </label>
          <label className="block text-sm">
            Date
            <input className={input} type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </label>
        </div>
        <label className="block text-sm">
          Category
          <select className={input} value={category} onChange={(e) => setCategory(e.target.value)}>
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Reference (optional)
          <input className={input} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={255} />
        </label>
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">
            Cancel
          </button>
          <button type="submit" disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
