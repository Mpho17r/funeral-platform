"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Landmark, Plus } from "lucide-react";

import api from "@/lib/api";
import { categoryLabel, formatRand, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Bill = {
  id: string;
  supplier_name: string;
  description: string;
  category: string;
  amount: number;
  bill_date: string;
  due_date: string | null;
  reference: string | null;
  status: "unpaid" | "paid" | "void";
  paid_on: string | null;
  days_overdue: number;
  void_reason: string | null;
};

type Page = { total: number; owed: number; overdue: number; items: Bill[] };

const today = () => new Date().toISOString().slice(0, 10);

export default function BillsPage() {
  const { can } = useCurrentUser();
  const [data, setData] = useState<Page | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [status, setStatus] = useState("unpaid");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api.get<Page>("/bills", { params: status ? { status } : {} });
      setData(r.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load bills."));
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    api
      .get<{ expenses: string[] }>("/money/categories")
      .then((r) => setCategories(r.data.expenses))
      .catch(() => setCategories(["other"]));
  }, []);

  async function pay(b: Bill) {
    if (!window.confirm(`Mark ${b.supplier_name} - ${formatRand(b.amount)} as paid today?`)) return;
    try {
      await api.post(`/bills/${b.id}/pay`, { paid_on: today(), method: "eft" });
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not mark it paid."));
    }
  }

  async function cancel(b: Bill) {
    const reason = window.prompt("Why is this bill being cancelled?");
    if (!reason || reason.trim().length < 3) return;
    try {
      await api.post(`/bills/${b.id}/void`, { reason: reason.trim() });
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not cancel it."));
    }
  }

  const manage = can("bills.manage");

  return (
    <main className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <Landmark size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Bills you owe</h1>
            <p className="text-sm text-slate-500">Supplier bills. Paying one records the expense for you.</p>
          </div>
        </div>
        {manage && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"
          >
            <Plus size={16} /> Add bill
          </button>
        )}
      </header>

      {error && <ErrorNote message={error} />}

      {data && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border bg-white p-4">
            <p className="text-xs text-slate-500">Unpaid bills</p>
            <p className="mt-1 text-lg font-bold">{formatRand(data.owed)}</p>
          </div>
          <div className="rounded-2xl border bg-white p-4">
            <p className="text-xs text-slate-500">Overdue</p>
            <p className={`mt-1 text-lg font-bold ${data.overdue > 0 ? "text-red-700" : ""}`}>
              {formatRand(data.overdue)}
            </p>
          </div>
        </div>
      )}

      <select className={`${inputClass} !w-auto`} value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="unpaid">Waiting to be paid</option>
        <option value="paid">Paid</option>
        <option value="void">Cancelled</option>
        <option value="">All</option>
      </select>

      <div className="overflow-x-auto rounded-2xl border bg-white">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Supplier</th>
              <th className="px-4 py-3">Due</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((b) => (
              <tr key={b.id} className="border-t">
                <td className="px-4 py-3">
                  <div className="font-medium">{b.supplier_name}</div>
                  <div className="text-xs text-slate-500">
                    {b.description} · {categoryLabel(b.category)}
                  </div>
                </td>
                <td className="px-4 py-3">
                  {b.status === "paid"
                    ? `Paid ${b.paid_on}`
                    : b.status === "void"
                      ? "Cancelled"
                      : b.days_overdue > 0
                        ? <span className="font-medium text-red-700">{b.days_overdue}d overdue</span>
                        : (b.due_date ?? "No date")}
                </td>
                <td className="px-4 py-3 text-right">{formatRand(b.amount)}</td>
                <td className="space-x-2 whitespace-nowrap px-4 py-3 text-right">
                  {manage && b.status === "unpaid" && (
                    <>
                      <button type="button" onClick={() => pay(b)} className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white">
                        Mark paid
                      </button>
                      <button type="button" onClick={() => cancel(b)} className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50">
                        Cancel
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.items.length === 0 && (
          <p className="px-6 py-12 text-center text-sm text-slate-500">No bills here.</p>
        )}
      </div>

      {adding && (
        <AddBill
          categories={categories}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            void load();
          }}
        />
      )}
    </main>
  );
}

function AddBill({
  categories,
  onClose,
  onSaved,
}: {
  categories: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [supplier, setSupplier] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState(categories[0] ?? "other");
  const [amount, setAmount] = useState("");
  const [billDate, setBillDate] = useState(today());
  const [dueDate, setDueDate] = useState("");
  const [reference, setReference] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!supplier.trim() || !description.trim()) return setError("Enter who it is from and what it is for.");
    if (!(Number(amount) > 0)) return setError("Enter the amount.");
    try {
      setSaving(true);
      await api.post("/bills", {
        supplier_name: supplier.trim(),
        description: description.trim(),
        category,
        amount: Number(amount),
        bill_date: billDate,
        due_date: dueDate || null,
        reference: reference.trim() || null,
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save the bill."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Add a bill" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <input className={inputClass} placeholder="Supplier" value={supplier} onChange={(e) => setSupplier(e.target.value)} />
        <input className={inputClass} placeholder="What it is for" value={description} onChange={(e) => setDescription(e.target.value)} />
        <div className="grid gap-3 sm:grid-cols-2">
          <select className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
            {(categories.length ? categories : ["other"]).map((c) => (
              <option key={c} value={c}>{categoryLabel(c)}</option>
            ))}
          </select>
          <input className={inputClass} inputMode="decimal" placeholder="Amount (R)" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <label className="text-xs text-slate-500">Bill date
            <input type="date" className={inputClass} value={billDate} onChange={(e) => setBillDate(e.target.value)} />
          </label>
          <label className="text-xs text-slate-500">Due date
            <input type="date" className={inputClass} value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </label>
        </div>
        <input className={inputClass} placeholder="Reference (optional)" value={reference} onChange={(e) => setReference(e.target.value)} />
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Save bill" />
      </form>
    </Dialog>
  );
}
