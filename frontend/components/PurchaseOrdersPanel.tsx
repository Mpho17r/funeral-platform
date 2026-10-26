"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";

type Order = {
  id: string;
  number: string;
  item_name: string | null;
  unit: string | null;
  supplier_name: string | null;
  quantity: string;
  status: "to_send" | "sent" | "received" | "cancelled";
  automatic: boolean;
  send_error: string | null;
  created_at: string;
};

const LABELS: Record<Order["status"], string> = {
  to_send: "Needs sending",
  sent: "Sent, waiting for stock",
  received: "Received",
  cancelled: "Cancelled",
};

/** Open supplier orders: placed by hand or automatically when stock ran low. */
export function PurchaseOrdersPanel({
  reloadKey,
  onChanged,
  onError,
}: {
  reloadKey: number;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api.get<Order[]>("/inventory/orders");
      setOrders(r.data.filter((o) => o.status === "to_send" || o.status === "sent"));
    } catch {
      setOrders([]);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load, reloadKey]);

  async function act(order: Order, action: "mark-sent" | "receive" | "cancel") {
    try {
      setBusy(order.id);
      await api.post(`/inventory/orders/${order.id}/${action}`);
      onChanged();
      await load();
    } catch (err) {
      onError(getApiErrorMessage(err, "Could not update the order."));
    } finally {
      setBusy("");
    }
  }

  if (orders.length === 0) return null;

  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50/50 p-4">
      <h2 className="mb-3 text-base font-semibold text-slate-900">Supplier orders</h2>
      <ul className="divide-y divide-amber-100">
        {orders.map((o) => (
          <li key={o.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
            <div>
              <p className="font-medium text-slate-900">
                {o.number}: {Number(o.quantity)} {o.unit} of {o.item_name}
              </p>
              <p className="text-xs text-slate-600">
                {o.supplier_name} · {LABELS[o.status]}
                {o.automatic ? " · placed automatically" : ""}
              </p>
              {o.status === "to_send" && o.send_error && (
                <p className="text-xs text-amber-800">
                  Not emailed: {o.send_error} Send it yourself, then mark it sent.
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {busy === o.id && <Loader2 size={16} className="animate-spin" />}
              {o.status === "to_send" && (
                <button
                  type="button"
                  disabled={busy === o.id}
                  onClick={() => void act(o, "mark-sent")}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-800"
                >
                  Mark sent
                </button>
              )}
              <button
                type="button"
                disabled={busy === o.id}
                onClick={() => void act(o, "receive")}
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white"
              >
                Stock arrived
              </button>
              <button
                type="button"
                disabled={busy === o.id}
                onClick={() => void act(o, "cancel")}
                className="text-xs font-medium text-red-700 hover:underline"
              >
                Cancel
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
