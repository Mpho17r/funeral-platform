"use client";

import { useEffect, useState } from "react";
import { HandCoins } from "lucide-react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
import { formatRand, getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { docStatusLabel, docStatusTone, type SalesDoc } from "@/lib/sales";

type Receivables = {
  outstanding: number;
  overdue: number;
  buckets: { current: number; "1_30": number; "31_60": number; over_60: number };
  customers: { customer_id: string; customer_name: string; owes: number; overdue: number }[];
  invoices: SalesDoc[];
};

const BUCKETS: [keyof Receivables["buckets"], string][] = [
  ["current", "Not due yet"],
  ["1_30", "1-30 days late"],
  ["31_60", "31-60 days late"],
  ["over_60", "Over 60 days late"],
];

export default function ReceivablesPage() {
  const router = useRouter();
  const { can } = useCurrentUser();
  const [data, setData] = useState<Receivables | null>(null);
  const [error, setError] = useState("");

  async function remind(id: string) {
    try {
      setError("");
      await api.post(`/outbox/invoice/${id}/reminder`, {});
      router.push("/messages");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not prepare the reminder."));
    }
  }

  useEffect(() => {
    api
      .get<Receivables>("/sales/receivables")
      .then((r) => setData(r.data))
      .catch((err) => setError(getApiErrorMessage(err, "Could not load.")));
  }, []);

  return (
    <main className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
      <header className="flex items-center gap-3">
        <div className="rounded-xl bg-slate-900 p-3 text-white">
          <HandCoins size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Who owes you</h1>
          <p className="text-sm text-slate-500">Unpaid customer invoices, oldest first.</p>
        </div>
      </header>

      {error && <ErrorNote message={error} />}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Card label="Total owed" value={formatRand(data.outstanding)} strong />
            {BUCKETS.map(([key, label]) => (
              <Card
                key={key}
                label={label}
                value={formatRand(data.buckets[key])}
                late={key !== "current" && data.buckets[key] > 0}
              />
            ))}
          </div>

          <section className="overflow-x-auto rounded-2xl border bg-white">
            <h2 className="px-4 pt-4 font-semibold">By customer</h2>
            <table className="mt-2 w-full min-w-[28rem] text-left text-sm">
              <tbody>
                {data.customers.map((c) => (
                  <tr key={c.customer_id} className="border-t">
                    <td className="px-4 py-3 font-medium">{c.customer_name}</td>
                    <td className="px-4 py-3 text-right">{formatRand(c.owes)}</td>
                    <td className="px-4 py-3 text-right text-red-700">
                      {c.overdue > 0 ? `${formatRand(c.overdue)} late` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.customers.length === 0 && (
              <p className="px-6 py-10 text-center text-sm text-slate-500">
                Nobody owes you anything. 
              </p>
            )}
          </section>

          {data.invoices.length > 0 && (
            <section className="overflow-x-auto rounded-2xl border bg-white">
              <h2 className="px-4 pt-4 font-semibold">Unpaid invoices</h2>
              <table className="mt-2 w-full min-w-[36rem] text-left text-sm">
                <tbody>
                  {data.invoices.map((d) => (
                    <tr
                      key={d.id}
                      tabIndex={0}
                      onClick={() => router.push(`/sales/${d.id}`)}
                      onKeyDown={(e) => e.key === "Enter" && router.push(`/sales/${d.id}`)}
                      className="cursor-pointer border-t hover:bg-slate-50"
                    >
                      <td className="px-4 py-3 font-medium">{d.number}</td>
                      <td className="px-4 py-3">{d.customer_name}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${docStatusTone(d)}`}>
                          {docStatusLabel(d)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-semibold">{formatRand(d.balance)}</td>
                      {can("outbox.manage") && (
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              void remind(d.id);
                            }}
                            className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-100"
                          >
                            Send reminder
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </main>
  );
}

function Card({ label, value, strong, late }: { label: string; value: string; strong?: boolean; late?: boolean }) {
  return (
    <div className={`rounded-2xl border bg-white p-4 ${strong ? "ring-2 ring-slate-900" : ""}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 text-lg font-bold ${late ? "text-red-700" : ""}`}>{value}</p>
    </div>
  );
}
