"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Loader2, Package, Pencil, Plus, Power, PowerOff } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { Dialog, DialogFooter, Field, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";
import { useCurrentUser } from "@/components/CurrentUserProvider";

type Item = {
  id: string;
  name: string;
  service_type: string;
  description: string | null;
  unit_price: string;
  default_quantity: number;
  price_varies: boolean;
  is_standard: boolean;
  provider: string | null;
  is_active: boolean;
};

type Pack = {
  id: string;
  name: string;
  description: string | null;
  total: string;
  items: { catalog_item_id: string; name: string; quantity: number }[];
};

const TYPES = [
  "coffin", "hearse", "transport", "venue", "catering", "flowers",
  "tent", "mortuary", "documentation", "photography", "other",
];

const rand = (v: string | number) =>
  `R ${Number(v).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;

export default function ServiceCatalogPage() {
  const { can } = useCurrentUser();
  const canEdit = can("services.catalog");

  const [items, setItems] = useState<Item[]>([]);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Item | "new" | null>(null);
  const [packEditing, setPackEditing] = useState<Pack | "new" | null>(null);

  const fetchAll = useCallback(async () => {
    const [a, b] = await Promise.all([
      api.get<Item[]>("/service-catalog", {
        params: { include_inactive: true },
      }),
      api.get<Pack[]>("/service-packages"),
    ]);
    return { items: a.data, packs: b.data };
  }, []);

  const load = useCallback(() => {
    return fetchAll()
      .then((data) => {
        setItems(data.items);
        setPacks(data.packs);
        setError("");
      })
      .catch((err) =>
        setError(getApiErrorMessage(err, "Unable to load the price list."))
      )
      .finally(() => setLoading(false));
  }, [fetchAll]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(item: Item) {
    try {
      await api.patch(`/service-catalog/${item.id}`, {
        is_active: !item.is_active,
      });
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to change the service."));
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center p-20">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-6 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Price list</h1>
          <p className="mt-1 text-sm text-slate-500">
            Save your usual services once. They are added to cases in one
            click and flow into quotes and invoices automatically.
          </p>
        </div>
        {canEdit && (
          <button
            onClick={() => setEditing("new")}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
          >
            <Plus size={16} /> Add service
          </button>
        )}
      </div>

      {error && <ErrorNote message={error} />}

      <div className="overflow-x-auto rounded-2xl border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Service</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3 text-right">Usual price</th>
              <th className="px-4 py-3">Notes</th>
              {canEdit && <th className="px-4 py-3" />}
            </tr>
          </thead>
          <tbody className="divide-y">
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                  No services saved yet.
                </td>
              </tr>
            )}
            {items.map((item) => (
              <tr key={item.id} className={item.is_active ? "" : "opacity-50"}>
                <td className="px-4 py-3 font-medium text-slate-900">
                  {item.name}
                </td>
                <td className="px-4 py-3 capitalize">{item.service_type}</td>
                <td className="px-4 py-3 text-right">
                  {rand(item.unit_price)}
                </td>
                <td className="px-4 py-3 text-xs text-slate-500">
                  {item.price_varies && "Price varies. "}
                  {item.is_standard && "Standard on every funeral. "}
                  {!item.is_active && "Not offered."}
                </td>
                {canEdit && (
                  <td className="space-x-2 px-4 py-3 text-right">
                    <button
                      onClick={() => setEditing(item)}
                      aria-label="Edit"
                      className="text-slate-500 hover:text-slate-900"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onClick={() => toggle(item)}
                      aria-label={item.is_active ? "Stop offering" : "Offer again"}
                      className="text-slate-500 hover:text-slate-900"
                    >
                      {item.is_active ? <PowerOff size={16} /> : <Power size={16} />}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Packages</h2>
          {canEdit && (
            <button
              onClick={() => setPackEditing("new")}
              className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium hover:bg-slate-50"
            >
              <Package size={15} /> New package
            </button>
          )}
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {packs.length === 0 && (
            <p className="text-sm text-slate-500">
              Bundle services that usually go together, such as a standard
              funeral, and add them to a case in one click.
            </p>
          )}
          {packs.map((pack) => (
            <div key={pack.id} className="rounded-2xl border bg-white p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-slate-900">{pack.name}</h3>
                  <p className="text-sm text-slate-500">{rand(pack.total)}</p>
                </div>
                {canEdit && (
                  <button
                    onClick={() => setPackEditing(pack)}
                    aria-label="Edit package"
                    className="text-slate-500 hover:text-slate-900"
                  >
                    <Pencil size={16} />
                  </button>
                )}
              </div>
              <ul className="mt-3 space-y-1 text-sm text-slate-600">
                {pack.items.map((i) => (
                  <li key={i.catalog_item_id}>
                    {i.quantity} x {i.name}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {editing && (
        <ItemDialog
          item={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
      {packEditing && (
        <PackDialog
          pack={packEditing === "new" ? null : packEditing}
          items={items.filter((i) => i.is_active)}
          onClose={() => setPackEditing(null)}
          onSaved={() => {
            setPackEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function ItemDialog({
  item,
  onClose,
  onSaved,
}: {
  item: Item | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(item?.name ?? "");
  const [type, setType] = useState(item?.service_type ?? "other");
  const [price, setPrice] = useState(item?.unit_price ?? "");
  const [qty, setQty] = useState(String(item?.default_quantity ?? 1));
  const [varies, setVaries] = useState(item?.price_varies ?? false);
  const [standard, setStandard] = useState(item?.is_standard ?? false);
  const [description, setDescription] = useState(item?.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setError("");
      const body = {
        name,
        service_type: type,
        unit_price: price || "0",
        default_quantity: Number(qty) || 1,
        price_varies: varies,
        is_standard: standard,
        description: description || null,
      };
      if (item) await api.patch(`/service-catalog/${item.id}`, body);
      else await api.post("/service-catalog", body);
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to save the service."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={item ? "Edit service" : "Add service"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Name">
          <input className={inputClass} value={name} required
            onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Type">
            <select className={inputClass} value={type}
              onChange={(e) => setType(e.target.value)}>
              {TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </Field>
          <Field label="Usual price (R)">
            <input className={inputClass} type="number" min={0} step="0.01"
              value={price} onChange={(e) => setPrice(e.target.value)} />
          </Field>
        </div>
        <Field label="Usual quantity">
          <input className={inputClass} type="number" min={1} value={qty}
            onChange={(e) => setQty(e.target.value)} />
        </Field>
        <Field label="Description (optional)">
          <input className={inputClass} value={description}
            onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={varies}
            onChange={(e) => setVaries(e.target.checked)} />
          The price changes from case to case
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={standard}
            onChange={(e) => setStandard(e.target.checked)} />
          Standard: add to every funeral with &quot;Add standard services&quot;
        </label>
        {error && <ErrorNote message={error} />}
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Save" />
      </form>
    </Dialog>
  );
}

function PackDialog({
  pack,
  items,
  onClose,
  onSaved,
}: {
  pack: Pack | null;
  items: Item[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(pack?.name ?? "");
  const [qty, setQty] = useState<Record<string, number>>(
    Object.fromEntries(
      (pack?.items ?? []).map((i) => [i.catalog_item_id, i.quantity])
    )
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setError("");
      const body = {
        name,
        items: Object.entries(qty)
          .filter(([, q]) => q > 0)
          .map(([catalog_item_id, quantity]) => ({ catalog_item_id, quantity })),
      };
      if (pack) await api.patch(`/service-packages/${pack.id}`, body);
      else await api.post("/service-packages", body);
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to save the package."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={pack ? "Edit package" : "New package"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Package name">
          <input className={inputClass} value={name} required
            onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="max-h-64 space-y-2 overflow-y-auto">
          {items.map((i) => (
            <div key={i.id} className="flex items-center justify-between gap-3 text-sm">
              <span>{i.name} ({rand(i.unit_price)})</span>
              <input type="number" min={0} className="w-20 rounded-lg border px-2 py-1.5"
                value={qty[i.id] ?? 0}
                onChange={(e) =>
                  setQty({ ...qty, [i.id]: Number(e.target.value) })
                } />
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-500">
          Set a quantity of 0 to leave a service out.
        </p>
        {error && <ErrorNote message={error} />}
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Save" />
      </form>
    </Dialog>
  );
}
