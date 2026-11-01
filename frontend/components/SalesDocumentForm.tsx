"use client";

import { FormEvent, useEffect, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";

import api from "@/lib/api";
import { formatRand, getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";
import { inputClass } from "@/components/Dialog";
import type { Customer, SalesLine } from "@/lib/sales";

export type DocumentFormValues = {
  customer_id: string;
  document_type: "quote" | "invoice";
  lines: SalesLine[];
  discount: number;
  due_date: string | null;
  valid_until: string | null;
  notes: string | null;
};

type Row = { key: number; description: string; quantity: string; unit_price: string };

let counter = 0;
const blank = (): Row => ({ key: ++counter, description: "", quantity: "1", unit_price: "" });

/**
 * One form for making a quote or invoice and for changing a draft. The
 * server works out the tax and the total; this only shows an estimate.
 */
export default function SalesDocumentForm({
  initial,
  lockType = false,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial: DocumentFormValues;
  lockType?: boolean;
  submitLabel: string;
  onSubmit: (values: DocumentFormValues) => Promise<void>;
  onCancel?: () => void;
}) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState(initial.customer_id);
  const [type, setType] = useState(initial.document_type);
  const [rows, setRows] = useState<Row[]>(
    initial.lines.length
      ? initial.lines.map((l) => ({
          key: ++counter,
          description: l.description,
          quantity: String(l.quantity),
          unit_price: String(l.unit_price),
        }))
      : [blank()],
  );
  const [discount, setDiscount] = useState(String(initial.discount || ""));
  const [dueDate, setDueDate] = useState(initial.due_date ?? "");
  const [validUntil, setValidUntil] = useState(initial.valid_until ?? "");
  const [notes, setNotes] = useState(initial.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<{ items: Customer[] }>("/customers")
      .then((r) => setCustomers(r.data.items))
      .catch(() => setCustomers([]));
  }, []);

  const subtotal = rows.reduce(
    (sum, r) => sum + (Number(r.quantity) || 0) * (Number(r.unit_price) || 0),
    0,
  );

  function update(key: number, patch: Partial<Row>) {
    setRows((current) => current.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const lines = rows
      .filter((r) => r.description.trim())
      .map((r) => ({
        description: r.description.trim(),
        quantity: Number(r.quantity),
        unit_price: Number(r.unit_price),
      }));

    if (!customerId) return setError("Choose a customer first.");
    if (lines.length === 0) return setError("Add at least one line with a description.");
    if (lines.some((l) => !(l.quantity > 0) || !(l.unit_price >= 0)))
      return setError("Check the quantity and price on each line.");

    try {
      setSaving(true);
      setError("");
      await onSubmit({
        customer_id: customerId,
        document_type: type,
        lines,
        discount: Number(discount) || 0,
        due_date: dueDate || null,
        valid_until: validUntil || null,
        notes: notes.trim() || null,
      });
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {error && <ErrorNote message={error} />}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Customer</span>
          <select
            className={inputClass}
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
          >
            <option value="">Choose a customer…</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Type</span>
          <select
            className={inputClass}
            value={type}
            disabled={lockType}
            onChange={(e) => setType(e.target.value as "quote" | "invoice")}
          >
            <option value="invoice">Invoice</option>
            <option value="quote">Quote</option>
          </select>
        </label>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium">What you are charging for</p>
        {rows.map((r) => (
          <div key={r.key} className="grid grid-cols-12 gap-2">
            <input
              className={`${inputClass} col-span-12 sm:col-span-6`}
              placeholder="Description"
              value={r.description}
              onChange={(e) => update(r.key, { description: e.target.value })}
            />
            <input
              className={`${inputClass} col-span-4 sm:col-span-2`}
              inputMode="decimal"
              placeholder="Qty"
              value={r.quantity}
              onChange={(e) => update(r.key, { quantity: e.target.value })}
            />
            <input
              className={`${inputClass} col-span-6 sm:col-span-3`}
              inputMode="decimal"
              placeholder="Price"
              value={r.unit_price}
              onChange={(e) => update(r.key, { unit_price: e.target.value })}
            />
            <button
              type="button"
              aria-label="Remove line"
              disabled={rows.length === 1}
              onClick={() => setRows((cur) => cur.filter((x) => x.key !== r.key))}
              className="col-span-2 flex items-center justify-center rounded-lg border text-slate-500 hover:bg-slate-50 disabled:opacity-40 sm:col-span-1"
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setRows((cur) => [...cur, blank()])}
          className="flex items-center gap-1 text-sm font-medium text-slate-700 hover:underline"
        >
          <Plus size={14} /> Add a line
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Discount (R)</span>
          <input
            className={inputClass}
            inputMode="decimal"
            value={discount}
            onChange={(e) => setDiscount(e.target.value)}
          />
        </label>
        {type === "invoice" ? (
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Due date</span>
            <input
              type="date"
              className={inputClass}
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
            <span className="mt-1 block text-xs text-slate-500">Blank = 30 days.</span>
          </label>
        ) : (
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Valid until</span>
            <input
              type="date"
              className={inputClass}
              value={validUntil}
              onChange={(e) => setValidUntil(e.target.value)}
            />
          </label>
        )}
        <div className="text-sm sm:text-right">
          <p className="text-slate-500">Subtotal</p>
          <p className="text-lg font-bold">{formatRand(subtotal - (Number(discount) || 0))}</p>
          <p className="text-xs text-slate-500">Tax is added automatically if it is on.</p>
        </div>
      </div>

      <label className="block text-sm">
        <span className="mb-1 block font-medium">Notes (shown on the document)</span>
        <textarea
          rows={2}
          className={inputClass}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>

      <div className="flex justify-end gap-2">
        {onCancel && (
          <button type="button" onClick={onCancel} className="rounded-lg border px-4 py-2 text-sm">
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
