"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Contact, Plus, Search } from "lucide-react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
import { formatRand, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";
import type { Customer } from "@/lib/sales";

export default function CustomersPage() {
  const router = useRouter();
  const { can } = useCurrentUser();
  const [items, setItems] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Customer | "new" | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async () => {
    try {
      const r = await api.get<{ total: number; items: Customer[] }>("/customers", {
        params: query ? { search: query } : {},
      });
      setItems(r.data.items);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load customers."));
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <Contact size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Customers</h1>
            <p className="text-sm text-slate-500">The people and companies you sell to.</p>
          </div>
        </div>
        {can("customers.manage") && (
          <button
            type="button"
            onClick={() => setEditing("new")}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"
          >
            <Plus size={16} /> Add customer
          </button>
        )}
      </header>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-3 text-slate-400" />
        <input
          className={`${inputClass} pl-9`}
          placeholder="Search by name, phone or email"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {error && <ErrorNote message={error} />}

      <div className="overflow-x-auto rounded-2xl border bg-white">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Contact</th>
              <th className="px-4 py-3 text-right">Owes you</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className="border-t">
                <td className="px-4 py-3 font-medium">{c.name}</td>
                <td className="px-4 py-3 text-slate-600">
                  {[c.phone, c.email].filter(Boolean).join(" · ") || "-"}
                </td>
                <td className="px-4 py-3 text-right">
                  {c.owes ? (
                    <span className="font-semibold text-red-700">{formatRand(c.owes)}</span>
                  ) : (
                    <span className="text-slate-400">-</span>
                  )}
                </td>
                <td className="space-x-2 whitespace-nowrap px-4 py-3 text-right">
                  {can("sales.manage") && (
                    <button
                      type="button"
                      onClick={() => router.push(`/sales/new?customer=${c.id}`)}
                      className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                    >
                      New invoice
                    </button>
                  )}
                  {can("appointments.manage") && (
                    <button
                      type="button"
                      onClick={() => router.push(`/appointments?customer=${c.id}`)}
                      className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                    >
                      Book
                    </button>
                  )}
                  {can("outbox.manage") && (
                    <button
                      type="button"
                      onClick={() => router.push(`/messages?customer=${c.id}&new=1`)}
                      className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                    >
                      Message
                    </button>
                  )}
                  {can("customers.manage") && (
                    <button
                      type="button"
                      onClick={() => setEditing(c)}
                      className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                    >
                      Edit
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && items.length === 0 && (
          <p className="px-6 py-12 text-center text-sm text-slate-500">
            {query ? "No customers match." : "No customers yet. Add your first one."}
          </p>
        )}
      </div>

      {editing && (
        <CustomerDialog
          customer={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void load();
          }}
        />
      )}
    </main>
  );
}

function CustomerDialog({
  customer,
  onClose,
  onSaved,
}: {
  customer: Customer | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    name: customer?.name ?? "",
    phone: customer?.phone ?? "",
    email: customer?.email ?? "",
    address: customer?.address ?? "",
    tax_number: customer?.tax_number ?? "",
    notes: customer?.notes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = Object.fromEntries(
      Object.entries(f).map(([k, v]) => [k, v.trim() || null]),
    );
    if (!f.name.trim()) return setError("Enter a name.");
    try {
      setSaving(true);
      if (customer) await api.patch(`/customers/${customer.id}`, body);
      else await api.post("/customers", body);
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
    } finally {
      setSaving(false);
    }
  }

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF((c) => ({ ...c, [k]: e.target.value }));

  return (
    <Dialog title={customer ? "Edit customer" : "Add customer"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <input className={inputClass} placeholder="Name" value={f.name} onChange={set("name")} />
        <div className="grid gap-3 sm:grid-cols-2">
          <input className={inputClass} placeholder="Phone" value={f.phone} onChange={set("phone")} />
          <input className={inputClass} placeholder="Email" value={f.email} onChange={set("email")} />
        </div>
        <textarea className={inputClass} rows={2} placeholder="Address" value={f.address} onChange={set("address")} />
        <input className={inputClass} placeholder="Tax / VAT number (optional)" value={f.tax_number} onChange={set("tax_number")} />
        <textarea className={inputClass} rows={2} placeholder="Notes" value={f.notes} onChange={set("notes")} />
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Save" />
      </form>
    </Dialog>
  );
}
