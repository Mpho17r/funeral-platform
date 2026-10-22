"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Ban, Loader2, Pencil, Plus } from "lucide-react";

import api from "@/lib/api";
import {
  formatDate,
  formatMoney,
  categoryLabel,
  methodLabel,
  getApiErrorMessage,
} from "@/lib/format";
import type { Supplier } from "@/lib/inventory";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, Field, inputClass } from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";
import { Panel, Tile } from "@/components/dashboards/Shared";

type Expense = {
  id: string;
  category: string;
  description: string;
  amount: number;
  expense_date: string;
  payment_method: string;
  reference: string | null;
  notes: string | null;
  case_id: string | null;
  supplier_id: string | null;
  status: "recorded" | "voided";
  void_reason: string | null;
};

type Summary = {
  today: number;
  month: number;
  by_category: { category: string; total: number }[];
  trend: { month: string; total: number }[];
};

type CaseOption = {
  id: string;
  case_number: string;
  deceased_full_name: string;
};

const METHODS = ["cash", "eft", "card", "insurance", "other"];

type Form = {
  category: string;
  description: string;
  amount: string;
  expense_date: string;
  payment_method: string;
  reference: string;
  notes: string;
  case_id: string;
  supplier_id: string;
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

function blankForm(category: string): Form {
  return {
    category,
    description: "",
    amount: "",
    expense_date: today(),
    payment_method: "cash",
    reference: "",
    notes: "",
    case_id: "",
    supplier_id: "",
  };
}

type Dialogue =
  | { kind: "create" }
  | { kind: "edit"; expense: Expense }
  | { kind: "void"; expense: Expense }
  | null;

export default function ExpensesPage() {
  const { can } = useCurrentUser();
  const canManage = can("expenses.manage");

  const [items, setItems] = useState<Expense[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [cases, setCases] = useState<CaseOption[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [category, setCategory] = useState("");
  const [showVoided, setShowVoided] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [form, setForm] = useState<Form>(blankForm("other"));
  const [voidReason, setVoidReason] = useState("");
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  // Lookups used by the form. The lists are optional extras, so a
  // missing permission just leaves that dropdown empty.
  useEffect(() => {
    api
      .get<{ categories: string[] }>("/expenses/categories")
      .then((r) => setCategories(r.data.categories))
      .catch(() => {});
    api
      .get<Supplier[]>("/suppliers")
      .then((r) => setSuppliers(r.data))
      .catch(() => {});
    api
      .get<CaseOption[]>("/cases")
      .then((r) => setCases(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [list, sum] = await Promise.all([
          api.get<{ total: number; items: Expense[] }>("/expenses", {
            params: {
              start: start || undefined,
              end: end || undefined,
              category: category || undefined,
              include_voided: showVoided,
            },
          }),
          api.get<Summary>("/expenses/summary"),
        ]);

        if (!cancelled) {
          setItems(list.data.items);
          setTotal(list.data.total);
          setSummary(sum.data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err, "Could not load expenses."));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [start, end, category, showVoided, reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  function close() {
    setDialog(null);
    setDialogError("");
  }

  function openCreate() {
    setForm(blankForm(categories.includes("other") ? "other" : categories[0] ?? "other"));
    setDialogError("");
    setDialog({ kind: "create" });
  }

  function openEdit(expense: Expense) {
    setForm({
      category: expense.category,
      description: expense.description,
      amount: String(expense.amount),
      expense_date: expense.expense_date,
      payment_method: expense.payment_method,
      reference: expense.reference ?? "",
      notes: expense.notes ?? "",
      case_id: expense.case_id ?? "",
      supplier_id: expense.supplier_id ?? "",
    });
    setDialogError("");
    setDialog({ kind: "edit", expense });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!dialog) return;

    setSaving(true);
    setDialogError("");

    try {
      if (dialog.kind === "void") {
        await api.post(`/expenses/${dialog.expense.id}/void`, {
          reason: voidReason.trim(),
        });
        setNotice("Expense voided. It stays in the history.");
        setVoidReason("");
      } else {
        const body = {
          category: form.category,
          description: form.description.trim(),
          amount: form.amount,
          expense_date: form.expense_date,
          payment_method: form.payment_method,
          reference: form.reference.trim() || null,
          notes: form.notes.trim() || null,
          case_id: form.case_id || null,
          supplier_id: form.supplier_id || null,
        };

        if (dialog.kind === "create") {
          await api.post("/expenses", body);
          setNotice("Expense recorded.");
        } else {
          await api.patch(`/expenses/${dialog.expense.id}`, body);
          setNotice("Expense updated.");
        }
      }
      close();
      reload();
    } catch (err) {
      setDialogError(getApiErrorMessage(err, "Could not save this expense."));
    } finally {
      setSaving(false);
    }
  }

  const supplierName = (id: string | null) =>
    suppliers.find((s) => s.id === id)?.name;
  const caseLabel = (id: string | null) => {
    const c = cases.find((x) => x.id === id);
    return c ? `${c.case_number} · ${c.deceased_full_name}` : undefined;
  };

  const maxTrend = Math.max(1, ...(summary?.trend.map((t) => t.total) ?? [0]));

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--fos-text)]">
            Expenses
          </h1>
          <p className="text-sm text-[var(--fos-text-muted)]">
            Money the business spends. Mistakes are voided, never deleted.
          </p>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={openCreate}
            className="flex items-center gap-2 rounded-lg bg-[var(--fos-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)]"
          >
            <Plus size={16} /> Record expense
          </button>
        )}
      </div>

      {notice && (
        <Banner tone="success" onDismiss={() => setNotice("")}>
          {notice}
        </Banner>
      )}
      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Tile label="Spent today" value={`R ${formatMoney(summary?.today ?? 0)}`} />
        <Tile label="Spent this month" value={`R ${formatMoney(summary?.month ?? 0)}`} />
        <Tile
          label="In the list below"
          value={`R ${formatMoney(total)}`}
          hint="Matches the filters"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="This month by category">
        <div className="p-5">
          {summary && summary.by_category.length > 0 ? (
            <ul className="space-y-2">
              {summary.by_category.map((row) => (
                <li key={row.category} className="flex justify-between text-sm">
                  <span className="text-[var(--fos-text)]">
                    {categoryLabel(row.category)}
                  </span>
                  <span className="font-medium text-[var(--fos-text)]">
                    R {formatMoney(row.total)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--fos-text-muted)]">
              Nothing spent this month yet.
            </p>
          )}
        </div>
        </Panel>

        <Panel title="Last 6 months">
        <div className="p-5">
          <div className="flex items-end gap-3">
            {summary?.trend.map((t) => (
              <div key={t.month} className="flex flex-1 flex-col items-center gap-1">
                <div className="flex h-28 w-full items-end">
                  <div
                    className="w-full rounded-t bg-[var(--fos-primary)]"
                    style={{ height: `${Math.max(2, (t.total / maxTrend) * 100)}%` }}
                    title={`R ${formatMoney(t.total)}`}
                  />
                </div>
                <span className="text-xs text-[var(--fos-text-muted)]">
                  {new Date(t.month).toLocaleDateString("en-ZA", { month: "short" })}
                </span>
              </div>
            ))}
          </div>
        </div>
        </Panel>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-[var(--fos-text-muted)]">From</span>
          <input type="date" className={inputClass} value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-[var(--fos-text-muted)]">To</span>
          <input type="date" className={inputClass} value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-[var(--fos-text-muted)]">Category</span>
          <select className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c} value={c}>{categoryLabel(c)}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-3 text-sm text-[var(--fos-text)]">
          <input type="checkbox" checked={showVoided} onChange={(e) => setShowVoided(e.target.checked)} />
          Show voided
        </label>
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)]">
        {loading ? (
          <p className="flex items-center gap-2 p-6 text-sm text-[var(--fos-text-muted)]">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </p>
        ) : items.length === 0 ? (
          <p className="p-6 text-sm text-[var(--fos-text-muted)]">
            No expenses match these filters.
          </p>
        ) : (
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-[var(--fos-border)] text-[var(--fos-text-muted)]">
              <tr>
                <th className="p-3 font-medium">Date</th>
                <th className="p-3 font-medium">What</th>
                <th className="p-3 font-medium">Paid with</th>
                <th className="p-3 text-right font-medium">Amount</th>
                {canManage && <th className="p-3" />}
              </tr>
            </thead>
            <tbody>
              {items.map((e) => {
                const voided = e.status === "voided";
                return (
                  <tr key={e.id} className="border-b border-[var(--fos-border)] last:border-0">
                    <td className="p-3 whitespace-nowrap text-[var(--fos-text)]">{formatDate(e.expense_date)}</td>
                    <td className="p-3">
                      <p className={`font-medium text-[var(--fos-text)] ${voided ? "line-through opacity-60" : ""}`}>
                        {e.description}
                      </p>
                      <p className="text-xs text-[var(--fos-text-muted)]">
                        {categoryLabel(e.category)}
                        {supplierName(e.supplier_id) && ` · ${supplierName(e.supplier_id)}`}
                        {caseLabel(e.case_id) && ` · ${caseLabel(e.case_id)}`}
                        {e.reference && ` · Ref ${e.reference}`}
                      </p>
                      {voided && (
                        <p className="text-xs text-red-600">Voided: {e.void_reason}</p>
                      )}
                    </td>
                    <td className="p-3 text-[var(--fos-text)]">{methodLabel(e.payment_method)}</td>
                    <td className={`p-3 text-right font-medium text-[var(--fos-text)] ${voided ? "line-through opacity-60" : ""}`}>
                      R {formatMoney(e.amount)}
                    </td>
                    {canManage && (
                      <td className="p-3 text-right whitespace-nowrap">
                        {!voided && (
                          <>
                            <button type="button" aria-label="Edit expense" onClick={() => openEdit(e)} className="mr-2 text-[var(--fos-text-muted)] hover:text-[var(--fos-text)]">
                              <Pencil size={16} />
                            </button>
                            <button
                              type="button"
                              aria-label="Void expense"
                              onClick={() => {
                                setVoidReason("");
                                setDialogError("");
                                setDialog({ kind: "void", expense: e });
                              }}
                              className="text-[var(--fos-text-muted)] hover:text-red-600"
                            >
                              <Ban size={16} />
                            </button>
                          </>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {dialog && dialog.kind === "void" && (
        <Dialog title="Void this expense" onClose={close}>
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-slate-600">
              {dialog.expense.description} · R {formatMoney(dialog.expense.amount)}.
              It stays in the history but no longer counts as money spent.
            </p>
            <Field label="Reason">
              <input className={inputClass} value={voidReason} onChange={(e) => setVoidReason(e.target.value)} />
            </Field>
            {dialogError && <ErrorNote message={dialogError} />}
            <DialogFooter onClose={close} saving={saving} submitLabel="Void expense" danger disabled={voidReason.trim().length < 3} />
          </form>
        </Dialog>
      )}

      {dialog && dialog.kind !== "void" && (
        <Dialog title={dialog.kind === "create" ? "Record expense" : "Edit expense"} onClose={close} wide>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="What was it for?">
                <input required className={inputClass} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </Field>
              <Field label="Amount (R)">
                <input required type="number" min="0.01" step="0.01" className={inputClass} value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
              </Field>
              <Field label="Category">
                <select className={inputClass} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                  {categories.map((c) => (
                    <option key={c} value={c}>{categoryLabel(c)}</option>
                  ))}
                </select>
              </Field>
              <Field label="Date">
                <input required type="date" max={today()} className={inputClass} value={form.expense_date} onChange={(e) => setForm({ ...form, expense_date: e.target.value })} />
              </Field>
              <Field label="Paid with">
                <select className={inputClass} value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
                  {METHODS.map((m) => (
                    <option key={m} value={m}>{methodLabel(m)}</option>
                  ))}
                </select>
              </Field>
              <Field label="Reference" hint="Invoice or slip number">
                <input className={inputClass} value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
              </Field>
              <Field label="Supplier (optional)">
                <select className={inputClass} value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}>
                  <option value="">None</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </Field>
              <Field label="Funeral (optional)" hint="Links the cost to that funeral">
                <select className={inputClass} value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
                  <option value="">None</option>
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>{c.case_number} · {c.deceased_full_name}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Notes (optional)">
              <textarea rows={2} className={inputClass} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Field>
            {dialogError && <ErrorNote message={dialogError} />}
            <DialogFooter onClose={close} saving={saving} submitLabel={dialog.kind === "create" ? "Record expense" : "Save changes"} />
          </form>
        </Dialog>
      )}
    </div>
  );
}
