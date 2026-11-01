"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { CalendarClock, Plus } from "lucide-react";

import api from "@/lib/api";
import { categoryLabel, formatRand, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Recurring = {
  id: string;
  kind: "income" | "expense";
  category: string;
  description: string;
  amount: number;
  frequency: "weekly" | "monthly" | "yearly";
  next_date: string;
  end_date: string | null;
  active: boolean;
};

type BudgetRow = {
  category: string;
  budget: number;
  spent: number;
  left: number;
  percent: number;
  state: "ok" | "warning" | "over";
};

const INCOME = ["sales", "services", "deposits", "interest", "grants", "other"];
const today = () => new Date().toISOString().slice(0, 10);
const FREQ: Record<string, string> = { weekly: "Every week", monthly: "Every month", yearly: "Every year" };

export default function PlanningPage() {
  const { can } = useCurrentUser();
  const manage = can("income.manage");
  const [items, setItems] = useState<Recurring[]>([]);
  const [budgets, setBudgets] = useState<BudgetRow[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [setting, setSetting] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [r, b] = await Promise.all([
        api.get<{ total: number; items: Recurring[] }>("/planning/recurring"),
        api.get<{ categories: string[]; items: BudgetRow[] }>("/planning/budgets"),
      ]);
      setItems(r.data.items);
      setBudgets(b.data.items);
      setCategories(b.data.categories);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(i: Recurring) {
    try {
      await api.patch(`/planning/recurring/${i.id}`, { active: !i.active });
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not change it."));
    }
  }

  const budgeted = new Set(budgets.map((b) => b.category));

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
      <header className="flex items-center gap-3">
        <div className="rounded-xl bg-slate-900 p-3 text-white">
          <CalendarClock size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Recurring &amp; budgets</h1>
          <p className="text-sm text-slate-500">
            Enter rent or salaries once and they record themselves. Set a monthly budget and get warned.
          </p>
        </div>
      </header>

      {error && <ErrorNote message={error} />}

      <section className="rounded-2xl border bg-white p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Monthly budgets</h2>
          {manage && (
            <select
              className={`${inputClass} !w-auto`}
              value=""
              onChange={(e) => e.target.value && setSetting(e.target.value)}
            >
              <option value="">Set a budget…</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {categoryLabel(c)}
                  {budgeted.has(c) ? " (change)" : ""}
                </option>
              ))}
            </select>
          )}
        </div>

        <ul className="mt-4 space-y-4">
          {budgets.map((b) => (
            <li key={b.category}>
              <div className="flex justify-between text-sm">
                <button
                  type="button"
                  disabled={!manage}
                  onClick={() => setSetting(b.category)}
                  className="font-medium hover:underline disabled:no-underline"
                >
                  {categoryLabel(b.category)}
                </button>
                <span className={b.state === "over" ? "font-semibold text-red-700" : ""}>
                  {formatRand(b.spent)} of {formatRand(b.budget)}
                </span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full ${
                    b.state === "over" ? "bg-red-600" : b.state === "warning" ? "bg-amber-500" : "bg-emerald-600"
                  }`}
                  style={{ width: `${Math.min(b.percent, 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {b.state === "over"
                  ? `Over by ${formatRand(-b.left)}`
                  : `${formatRand(b.left)} left this month`}
              </p>
            </li>
          ))}
          {budgets.length === 0 && (
            <li className="py-6 text-center text-sm text-slate-500">
              No budgets yet. Pick a category above to set one.
            </li>
          )}
        </ul>
      </section>

      <section className="overflow-x-auto rounded-2xl border bg-white">
        <div className="flex items-center justify-between px-5 pt-5">
          <h2 className="font-semibold">Recurring items</h2>
          {manage && (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
            >
              <Plus size={16} /> Add
            </button>
          )}
        </div>
        <table className="mt-3 w-full min-w-[36rem] text-left text-sm">
          <tbody>
            {items.map((i) => (
              <tr key={i.id} className={`border-t ${i.active ? "" : "text-slate-400"}`}>
                <td className="px-5 py-3">
                  <div className="font-medium">{i.description}</div>
                  <div className="text-xs">
                    {i.kind === "income" ? "Money in" : "Money out"} · {categoryLabel(i.category)} · {FREQ[i.frequency]}
                  </div>
                </td>
                <td className="px-5 py-3 text-right">{formatRand(i.amount)}</td>
                <td className="px-5 py-3 text-right text-xs">
                  {i.active ? `Next ${i.next_date}` : "Stopped"}
                </td>
                <td className="px-5 py-3 text-right">
                  {manage && (
                    <button
                      type="button"
                      onClick={() => toggle(i)}
                      className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                    >
                      {i.active ? "Stop" : "Resume"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <p className="px-6 py-10 text-center text-sm text-slate-500">
            Nothing recurring yet. Add rent, salaries or a monthly client.
          </p>
        )}
      </section>

      {adding && (
        <AddRecurring
          expenseCategories={categories}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            void load();
          }}
        />
      )}
      {setting && (
        <BudgetDialog
          category={setting}
          current={budgets.find((b) => b.category === setting)?.budget}
          onClose={() => setSetting(null)}
          onSaved={() => {
            setSetting(null);
            void load();
          }}
        />
      )}
    </main>
  );
}

function AddRecurring({
  expenseCategories,
  onClose,
  onSaved,
}: {
  expenseCategories: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [category, setCategory] = useState("rent");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [frequency, setFrequency] = useState("monthly");
  const [start, setStart] = useState(today());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const list = kind === "income" ? INCOME : expenseCategories;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!description.trim()) return setError("Say what it is.");
    if (!(Number(amount) > 0)) return setError("Enter the amount.");
    try {
      setSaving(true);
      await api.post("/planning/recurring", {
        kind,
        category,
        description: description.trim(),
        amount: Number(amount),
        frequency,
        start_date: start,
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Add a recurring item" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <div className="grid grid-cols-2 gap-3">
          <select
            className={inputClass}
            value={kind}
            onChange={(e) => {
              const k = e.target.value as "expense" | "income";
              setKind(k);
              setCategory((k === "income" ? INCOME : expenseCategories)[0] ?? "other");
            }}
          >
            <option value="expense">Money out</option>
            <option value="income">Money in</option>
          </select>
          <select className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
            {list.map((c) => (
              <option key={c} value={c}>{categoryLabel(c)}</option>
            ))}
          </select>
        </div>
        <input className={inputClass} placeholder="What it is (e.g. Office rent)" value={description} onChange={(e) => setDescription(e.target.value)} />
        <div className="grid grid-cols-2 gap-3">
          <input className={inputClass} inputMode="decimal" placeholder="Amount (R)" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <select className={inputClass} value={frequency} onChange={(e) => setFrequency(e.target.value)}>
            <option value="weekly">Every week</option>
            <option value="monthly">Every month</option>
            <option value="yearly">Every year</option>
          </select>
        </div>
        <label className="block text-xs text-slate-500">First date
          <input type="date" className={inputClass} value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Save" />
      </form>
    </Dialog>
  );
}

function BudgetDialog({
  category,
  current,
  onClose,
  onSaved,
}: {
  category: string;
  current?: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [amount, setAmount] = useState(current ? String(current) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const value = Number(amount || 0);
    if (!(value >= 0)) return setError("Enter an amount.");
    try {
      setSaving(true);
      await api.put(`/planning/budgets/${category}`, { amount: value });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Monthly budget: ${categoryLabel(category)}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <input className={inputClass} inputMode="decimal" placeholder="Amount per month (R)" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <p className="text-xs text-slate-500">Leave empty or 0 to remove the budget. You are warned at 80% and when it is used up.</p>
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Save" />
      </form>
    </Dialog>
  );
}
