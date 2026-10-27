"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Loader2, Package, Plus, Tags } from "lucide-react";

import type { CatalogueItem, ServicePackage } from "@/components/CatalogueAddDialog";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, inputClass } from "@/components/Dialog";
import api from "@/lib/api";
import { formatMoney, getApiErrorMessage } from "@/lib/format";

type StockItem = { id: string; name: string };

const TYPES = ["coffin", "transport", "catering", "flowers", "venue", "mortuary", "documentation", "labour", "other"];

export default function CataloguePage() {
  const { can } = useCurrentUser();
  const manage = can("services.manage");

  const [items, setItems] = useState<CatalogueItem[]>([]);
  const [packages, setPackages] = useState<ServicePackage[]>([]);
  const [stock, setStock] = useState<StockItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<CatalogueItem | "new" | null>(null);
  const [pkgEditing, setPkgEditing] = useState<ServicePackage | "new" | null>(null);

  const load = useCallback(async () => {
    try {
      const [i, p] = await Promise.all([
        api.get<CatalogueItem[]>("/service-catalogue", { params: { include_inactive: true } }),
        api.get<ServicePackage[]>("/service-packages", { params: { include_inactive: true } }),
      ]);
      setItems(i.data);
      setPackages(p.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load the price list."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    api
      .get<{ items?: StockItem[] } | StockItem[]>("/inventory/items")
      .then((r) => setStock(Array.isArray(r.data) ? r.data : r.data.items ?? []))
      .catch(() => setStock([]));
  }, [load]);

  return (
    <main className="mx-auto max-w-5xl space-y-8 p-6 md:p-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <Tags size={22} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--fos-text)]">Price list</h1>
            <p className="text-sm text-[var(--fos-text-muted)]">
              Save services once. Add them to any case in a click and they flow onto the quote and invoice.
            </p>
          </div>
        </div>
        {manage && (
          <div className="flex gap-3">
            <button onClick={() => setPkgEditing("new")} className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700">
              <Package size={16} /> New package
            </button>
            <button onClick={() => setEditing("new")} className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white">
              <Plus size={16} /> New service
            </button>
          </div>
        )}
      </header>

      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {loading && <Loader2 className="animate-spin text-slate-400" />}

      <section>
        <h2 className="mb-3 text-lg font-semibold text-[var(--fos-text)]">Packages</h2>
        {packages.length === 0 && !loading && (
          <p className="text-sm text-[var(--fos-text-muted)]">No packages yet. A package bundles services you sell together, such as a standard funeral.</p>
        )}
        <div className="grid gap-3 md:grid-cols-2">
          {packages.map((p) => (
            <button key={p.id} onClick={() => manage && setPkgEditing(p)} className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-4 text-left">
              <div className="flex justify-between font-medium text-[var(--fos-text)]">
                <span>{p.name}</span>
                <span>R {formatMoney(p.total)}</span>
              </div>
              <p className="mt-1 text-sm text-[var(--fos-text-muted)]">{p.items.map((i) => `${i.quantity}× ${i.name}`).join(", ") || "Empty"}</p>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-[var(--fos-text)]">Services and products</h2>
        <div className="overflow-hidden rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)]">
          <table className="w-full text-sm">
            <thead className="bg-[var(--fos-page)] text-left text-xs uppercase text-[var(--fos-text-muted)]">
              <tr><th className="p-3">Name</th><th className="p-3">Type</th><th className="p-3 text-right">Price</th><th className="p-3">Notes</th></tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} onClick={() => manage && setEditing(i)} className={`border-t border-[var(--fos-border)] ${manage ? "cursor-pointer hover:bg-[var(--fos-page)]" : ""} ${i.is_active ? "" : "opacity-50"}`}>
                  <td className="p-3 font-medium">{i.name}</td>
                  <td className="p-3 capitalize">{i.service_type}</td>
                  <td className="p-3 text-right">R {formatMoney(i.default_price)}</td>
                  <td className="p-3 text-xs text-[var(--fos-text-muted)]">
                    {[i.price_varies && "price varies", i.inventory_item_id && "takes stock", !i.is_active && "switched off"].filter(Boolean).join(" · ")}
                  </td>
                </tr>
              ))}
              {items.length === 0 && !loading && (
                <tr><td colSpan={4} className="p-6 text-center text-[var(--fos-text-muted)]">Nothing saved yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {editing && (
        <ItemDialog item={editing === "new" ? null : editing} stock={stock} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
      {pkgEditing && (
        <PackageDialog pkg={pkgEditing === "new" ? null : pkgEditing} items={items.filter((i) => i.is_active)} onClose={() => setPkgEditing(null)} onSaved={() => { setPkgEditing(null); load(); }} />
      )}
    </main>
  );
}

function ItemDialog({ item, stock, onClose, onSaved }: { item: CatalogueItem | null; stock: StockItem[]; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(item?.name ?? "");
  const [type, setType] = useState(item?.service_type ?? "other");
  const [price, setPrice] = useState(item ? String(item.default_price) : "");
  const [qty, setQty] = useState(String(item?.default_quantity ?? 1));
  const [varies, setVaries] = useState(item?.price_varies ?? false);
  const [stockId, setStockId] = useState(item?.inventory_item_id ?? "");
  const [active, setActive] = useState(item?.is_active ?? true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    const body = { name, service_type: type, default_price: price || "0", default_quantity: Number(qty) || 1, price_varies: varies, inventory_item_id: stockId || null };
    try {
      if (item) await api.patch(`/service-catalogue/${item.id}`, { ...body, is_active: active });
      else await api.post("/service-catalogue", body);
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
      setSaving(false);
    }
  }

  return (
    <Dialog title={item ? "Edit service" : "New service"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <label className="block text-sm font-medium">Name<input required className={inputClass} value={name} onChange={(e) => setName(e.target.value)} /></label>
        <div className="grid grid-cols-3 gap-3">
          <label className="block text-sm font-medium">Type
            <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
              {[...new Set([...TYPES, type])].map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium">Price (R)<input inputMode="decimal" className={inputClass} value={price} onChange={(e) => setPrice(e.target.value)} /></label>
          <label className="block text-sm font-medium">Usual qty<input inputMode="numeric" className={inputClass} value={qty} onChange={(e) => setQty(e.target.value)} /></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={varies} onChange={(e) => setVaries(e.target.checked)} /> The price usually changes from case to case</label>
        <label className="block text-sm font-medium">Takes from stock (optional)
          <select className={inputClass} value={stockId} onChange={(e) => setStockId(e.target.value)}>
            <option value="">Not a stocked item</option>
            {stock.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        {item && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Available to add to cases</label>}
        <button disabled={saving} className="w-full rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">{saving ? "Saving…" : "Save"}</button>
      </form>
    </Dialog>
  );
}

function PackageDialog({ pkg, items, onClose, onSaved }: { pkg: ServicePackage | null; items: CatalogueItem[]; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(pkg?.name ?? "");
  const [qty, setQty] = useState<Record<string, string>>(
    Object.fromEntries((pkg?.items ?? []).map((i) => [i.catalogue_item_id, String(i.quantity)]))
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function toggle(id: string) {
    const next = { ...qty };
    if (id in next) delete next[id];
    else next[id] = "1";
    setQty(next);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    const body = { name, items: Object.entries(qty).map(([id, q]) => ({ catalogue_item_id: id, quantity: Number(q) || 1 })) };
    try {
      if (pkg) await api.patch(`/service-packages/${pkg.id}`, body);
      else await api.post("/service-packages", body);
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
      setSaving(false);
    }
  }

  return (
    <Dialog title={pkg ? "Edit package" : "New package"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <label className="block text-sm font-medium">Package name<input required className={inputClass} value={name} onChange={(e) => setName(e.target.value)} /></label>
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {items.map((i) => (
            <div key={i.id} className="flex items-center justify-between gap-3 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={i.id in qty} onChange={() => toggle(i.id)} />{i.name}</label>
              {i.id in qty && <input aria-label={`Quantity of ${i.name}`} className="w-14 rounded border border-slate-300 px-2 py-1 text-center" value={qty[i.id]} onChange={(e) => setQty({ ...qty, [i.id]: e.target.value })} />}
            </div>
          ))}
        </div>
        <button disabled={saving} className="w-full rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">{saving ? "Saving…" : "Save"}</button>
      </form>
    </Dialog>
  );
}
