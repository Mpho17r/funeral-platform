"use client";

import { useEffect, useState } from "react";
import { Loader2, Package } from "lucide-react";

import { Dialog, inputClass } from "@/components/Dialog";
import api from "@/lib/api";
import { formatMoney, getApiErrorMessage } from "@/lib/format";

export type CatalogueItem = {
  id: string;
  name: string;
  service_type: string;
  default_price: string;
  default_quantity: number;
  price_varies: boolean;
  inventory_item_id: string | null;
  is_active: boolean;
};

type PackageItem = {
  catalogue_item_id: string;
  name: string;
  quantity: number;
  unit_price: string;
  price_varies: boolean;
};

export type ServicePackage = {
  id: string;
  name: string;
  total: string;
  items: PackageItem[];
};

/**
 * Add saved services to a case without retyping them. Prices can be
 * changed for this family; the quote or invoice follows automatically.
 */
export default function CatalogueAddDialog({
  caseId,
  onClose,
  onAdded,
}: {
  caseId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [items, setItems] = useState<CatalogueItem[]>([]);
  const [packages, setPackages] = useState<ServicePackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<CatalogueItem[]>("/service-catalogue"),
      api.get<ServicePackage[]>("/service-packages"),
    ])
      .then(([i, p]) => {
        setItems(i.data);
        setPackages(p.data);
      })
      .catch((err) =>
        setError(getApiErrorMessage(err, "Could not load the price list."))
      )
      .finally(() => setLoading(false));
  }, []);

  async function addItem(item: CatalogueItem) {
    setBusy(item.id);
    setError("");
    try {
      await api.post(`/cases/${caseId}/services/from-catalogue`, {
        catalogue_item_id: item.id,
        quantity: quantities[item.id] ? Number(quantities[item.id]) : undefined,
        unit_price: prices[item.id] ? prices[item.id] : undefined,
      });
      onAdded();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not add that service."));
    } finally {
      setBusy("");
    }
  }

  async function addPackage(pkg: ServicePackage) {
    setBusy(pkg.id);
    setError("");
    try {
      const overrides: Record<string, string> = {};
      for (const entry of pkg.items) {
        const typed = prices[`${pkg.id}:${entry.catalogue_item_id}`];
        if (typed) overrides[entry.catalogue_item_id] = typed;
      }
      await api.post(`/cases/${caseId}/services/from-package`, {
        package_id: pkg.id,
        prices: overrides,
      });
      onAdded();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not add that package."));
    } finally {
      setBusy("");
    }
  }

  const shown = items.filter((i) =>
    i.name.toLowerCase().includes(search.trim().toLowerCase())
  );

  return (
    <Dialog title="Add from price list" onClose={onClose} wide>
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </p>
      ) : (
        <div className="space-y-6">
          {error && (
            <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
              {error}
            </p>
          )}

          {packages.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-900">Packages</h3>
              <div className="space-y-3">
                {packages.map((pkg) => (
                  <div key={pkg.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 font-medium text-slate-900">
                        <Package size={16} /> {pkg.name}
                      </div>
                      <button
                        type="button"
                        disabled={busy === pkg.id}
                        onClick={() => addPackage(pkg)}
                        className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                      >
                        {busy === pkg.id ? "Adding…" : `Add all · R ${formatMoney(pkg.total)}`}
                      </button>
                    </div>
                    <ul className="mt-3 space-y-2 text-sm text-slate-600">
                      {pkg.items.map((entry) => (
                        <li key={entry.catalogue_item_id} className="flex items-center justify-between gap-3">
                          <span>
                            {entry.quantity} × {entry.name}
                          </span>
                          <input
                            aria-label={`Price for ${entry.name}`}
                            inputMode="decimal"
                            placeholder={formatMoney(entry.unit_price)}
                            value={prices[`${pkg.id}:${entry.catalogue_item_id}`] ?? ""}
                            onChange={(e) =>
                              setPrices({
                                ...prices,
                                [`${pkg.id}:${entry.catalogue_item_id}`]: e.target.value,
                              })
                            }
                            className="w-28 rounded-lg border border-slate-300 px-2 py-1 text-right text-sm"
                          />
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section>
            <div className="mb-2 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-slate-900">Single services</h3>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search…"
                className={`${inputClass} max-w-[14rem] !py-2`}
              />
            </div>
            {shown.length === 0 && (
              <p className="text-sm text-slate-500">
                Nothing saved yet. Add services on the Price list page.
              </p>
            )}
            <ul className="divide-y divide-slate-100">
              {shown.map((item) => (
                <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <p className="font-medium text-slate-900">{item.name}</p>
                    <p className="text-xs text-slate-500">
                      {item.service_type} · R {formatMoney(item.default_price)}
                      {item.price_varies && " · price varies"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      aria-label={`Quantity for ${item.name}`}
                      inputMode="numeric"
                      placeholder={String(item.default_quantity)}
                      value={quantities[item.id] ?? ""}
                      onChange={(e) => setQuantities({ ...quantities, [item.id]: e.target.value })}
                      className="w-14 rounded-lg border border-slate-300 px-2 py-1 text-center text-sm"
                    />
                    <input
                      aria-label={`Price for ${item.name}`}
                      inputMode="decimal"
                      placeholder={item.price_varies ? "Enter price" : formatMoney(item.default_price)}
                      value={prices[item.id] ?? ""}
                      onChange={(e) => setPrices({ ...prices, [item.id]: e.target.value })}
                      className="w-28 rounded-lg border border-slate-300 px-2 py-1 text-right text-sm"
                    />
                    <button
                      type="button"
                      disabled={busy === item.id}
                      onClick={() => addItem(item)}
                      className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {busy === item.id ? "Adding…" : "Add"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </Dialog>
  );
}
