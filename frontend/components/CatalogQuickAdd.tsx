"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Package, Plus, Sparkles } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";

type CatalogItem = {
  id: string;
  name: string;
  service_type: string;
  unit_price: string;
  default_quantity: number;
  price_varies: boolean;
  is_standard: boolean;
};

type PackageRow = {
  id: string;
  name: string;
  total: string;
  items: { name: string; quantity: number }[];
};

function rand(value: string | number) {
  return `R ${Number(value).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
  })}`;
}

/**
 * Add services to a case from the saved price list: one at a time, as a
 * ready-made package, or all the "standard" ones. The quote and invoice
 * are then built from these, so nothing is typed twice.
 */
export function CatalogQuickAdd({
  caseId,
  onAdded,
}: {
  caseId: string;
  onAdded: () => void;
}) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [packages, setPackages] = useState<PackageRow[]>([]);
  const [ready, setReady] = useState(false);
  const [selected, setSelected] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<CatalogItem[]>("/service-catalog"),
      api.get<PackageRow[]>("/service-packages"),
    ])
      .then(([a, b]) => {
        setItems(a.data);
        setPackages(b.data);
      })
      .catch(() => undefined)
      .finally(() => setReady(true));
  }, []);

  const chosen = useMemo(
    () => items.find((item) => item.id === selected) ?? null,
    [items, selected]
  );
  const standardCount = items.filter((i) => i.is_standard).length;

  async function run(key: string, request: () => Promise<number>) {
    try {
      setBusy(key);
      setError("");
      setNote("");
      const added = await request();
      setNote(
        added === 0
          ? "Nothing new to add - those services are already on the case."
          : `Added ${added} service${added === 1 ? "" : "s"}.`
      );
      onAdded();
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to add the service."));
    } finally {
      setBusy("");
    }
  }

  if (!ready) return null;

  if (items.length === 0) {
    return (
      <div className="mt-8 rounded-2xl border border-dashed bg-[var(--fos-surface)] px-6 py-5 text-sm text-[var(--fos-text-muted)]">
        <span className="font-semibold text-[var(--fos-text)]">
          Save your usual services once.
        </span>{" "}
        Add them to the{" "}
        <a href="/service-catalog" className="underline">
          price list
        </a>{" "}
        and they can be added to any case in one click and flow straight
        into quotes and invoices.
      </div>
    );
  }

  return (
    <div className="mt-8 rounded-2xl border bg-[var(--fos-surface)] p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[var(--fos-text)]">
            Add from your price list
          </h2>
          <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
            Prices can be changed for this case. Quotes and invoices pick
            these up automatically.
          </p>
        </div>

        {standardCount > 0 && (
          <button
            type="button"
            disabled={busy !== ""}
            onClick={() =>
              run("standard", async () => {
                const r = await api.post<unknown[]>(
                  `/cases/${caseId}/services/apply-standard`
                );
                return r.data.length;
              })
            }
            className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium hover:bg-[var(--fos-surface-muted)] disabled:opacity-60"
          >
            {busy === "standard" ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Sparkles size={15} />
            )}
            Add standard services ({standardCount})
          </button>
        )}
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-[1fr_90px_140px_auto]">
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setQuantity("");
            setPrice("");
          }}
          className="rounded-lg border px-3 py-2.5 text-sm"
        >
          <option value="">Choose a service...</option>
          {items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} - {rand(item.unit_price)}
              {item.price_varies ? " (price varies)" : ""}
            </option>
          ))}
        </select>

        <input
          type="number"
          min={1}
          placeholder={chosen ? String(chosen.default_quantity) : "Qty"}
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          className="rounded-lg border px-3 py-2.5 text-sm"
          aria-label="Quantity"
        />

        <input
          type="number"
          min={0}
          step="0.01"
          placeholder={chosen ? `${chosen.unit_price}` : "Price"}
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          className={`rounded-lg border px-3 py-2.5 text-sm ${
            chosen?.price_varies ? "border-amber-400" : ""
          }`}
          aria-label="Price for this case"
        />

        <button
          type="button"
          disabled={!chosen || busy !== ""}
          onClick={() =>
            run("one", async () => {
              await api.post(`/cases/${caseId}/services/from-catalog`, {
                catalog_item_id: selected,
                ...(quantity ? { quantity: Number(quantity) } : {}),
                ...(price !== "" ? { unit_price: price } : {}),
              });
              setSelected("");
              setQuantity("");
              setPrice("");
              return 1;
            })
          }
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {busy === "one" ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Plus size={15} />
          )}
          Add
        </button>
      </div>

      {chosen?.price_varies && (
        <p className="mt-2 text-xs text-amber-700">
          The price for this service changes from case to case. Enter this
          case&apos;s price above.
        </p>
      )}

      {packages.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {packages.map((pack) => (
            <button
              key={pack.id}
              type="button"
              disabled={busy !== ""}
              title={pack.items
                .map((i) => `${i.quantity} x ${i.name}`)
                .join(", ")}
              onClick={() =>
                run(`pack:${pack.id}`, async () => {
                  const r = await api.post<unknown[]>(
                    `/cases/${caseId}/services/from-package`,
                    { package_id: pack.id }
                  );
                  return r.data.length;
                })
              }
              className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium hover:bg-[var(--fos-surface-muted)] disabled:opacity-60"
            >
              <Package size={14} />
              {pack.name} - {rand(pack.total)}
            </button>
          ))}
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {note && <p className="mt-3 text-sm text-emerald-700">{note}</p>}
    </div>
  );
}
