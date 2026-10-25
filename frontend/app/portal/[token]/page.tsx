"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import axios from "axios";
import { Loader2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Family = {
  kind: "family";
  business_name: string;
  case_number: string;
  deceased_full_name: string;
  funeral_date: string | null;
  funeral_venue: string | null;
  status: string;
  schedule: {
    name: string;
    type: string;
    scheduled_for: string | null;
    status: string;
  }[];
  balance: { total: number; paid: number; outstanding: number } | null;
  documents: {
    type: string;
    number: string | null;
    total: number;
    status: string;
    issued_at: string | null;
    due_date: string | null;
  }[];
};

type MemberView = {
  kind: "member";
  business_name: string;
  member_name: string;
  memberships: {
    number: string;
    plan: string | null;
    monthly_contribution: number | null;
    status: string;
    next_due_date: string | null;
    arrears_since: string | null;
  }[];
  outstanding: number;
  contributions: {
    period: string;
    due: number;
    paid: number;
    status: string;
    due_date: string;
  }[];
  payments: { date: string; amount: number; method: string }[];
};

const rand = (n: number) =>
  `R ${n.toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const day = (v: string | null) =>
  v ? new Date(v).toLocaleDateString("en-ZA", { dateStyle: "long" }) : "To be confirmed";
const words = (v: string) => v.replace(/_/g, " ");

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="mb-3 text-base font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

export default function PortalPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<Family | MemberView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let off = false;
    axios
      .get(`${API}/portal/${token}`)
      .then((r) => !off && setData(r.data))
      .catch((e) => {
        if (off) return;
        setError(
          e?.response?.status === 429
            ? "Too many attempts. Please try again in a few minutes."
            : "This link is not valid any more. Please ask the funeral home for a new one.",
        );
      });
    return () => {
      off = true;
    };
  }, [token]);

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-2xl space-y-4">
        {!data && !error && (
          <div className="flex items-center gap-2 text-slate-500">
            <Loader2 className="animate-spin" size={18} /> Loading…
          </div>
        )}
        {error && (
          <p className="rounded-xl border bg-white p-5 text-slate-700">{error}</p>
        )}

        {data?.kind === "family" && (
          <>
            <header>
              <p className="text-sm text-slate-500">{data.business_name}</p>
              <h1 className="text-2xl font-bold text-slate-900">
                In loving memory of {data.deceased_full_name}
              </h1>
              <p className="text-sm text-slate-500">Reference {data.case_number}</p>
            </header>

            <Card title="The funeral">
              <p className="text-sm text-slate-700">
                {day(data.funeral_date)}
                {data.funeral_venue ? ` · ${data.funeral_venue}` : ""}
              </p>
              {data.schedule.length > 0 && (
                <ul className="mt-3 space-y-2 text-sm">
                  {data.schedule.map((s, i) => (
                    <li key={i} className="flex justify-between gap-3">
                      <span className="text-slate-800">{s.name}</span>
                      <span className="text-slate-500">
                        {day(s.scheduled_for)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {data.balance && (
              <Card title="Account">
                <dl className="grid grid-cols-3 gap-3 text-sm">
                  <div><dt className="text-slate-500">Total</dt><dd className="font-semibold">{rand(data.balance.total)}</dd></div>
                  <div><dt className="text-slate-500">Paid</dt><dd className="font-semibold">{rand(data.balance.paid)}</dd></div>
                  <div><dt className="text-slate-500">Still to pay</dt><dd className="font-semibold">{rand(data.balance.outstanding)}</dd></div>
                </dl>
              </Card>
            )}

            {data.documents.length > 0 && (
              <Card title="Documents">
                <ul className="space-y-2 text-sm">
                  {data.documents.map((d, i) => (
                    <li key={i} className="flex justify-between gap-3">
                      <span className="capitalize text-slate-800">
                        {words(d.type)} {d.number ?? ""}
                      </span>
                      <span className="text-slate-500">{rand(d.total)}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </>
        )}

        {data?.kind === "member" && (
          <>
            <header>
              <p className="text-sm text-slate-500">{data.business_name}</p>
              <h1 className="text-2xl font-bold text-slate-900">
                Hello {data.member_name}
              </h1>
            </header>

            {data.memberships.map((m) => (
              <Card key={m.number} title={`Membership ${m.number}`}>
                <p className="text-sm text-slate-700">
                  {m.plan ?? "Plan"}
                  {m.monthly_contribution !== null
                    ? ` · ${rand(m.monthly_contribution)} a month`
                    : ""}
                </p>
                <p className="mt-1 text-sm capitalize text-slate-700">
                  Status: {words(m.status)}
                </p>
                {m.next_due_date && (
                  <p className="text-sm text-slate-500">
                    Next payment due {day(m.next_due_date)}
                  </p>
                )}
                {m.arrears_since && (
                  <p className="text-sm text-amber-700">
                    Behind on payments since {day(m.arrears_since)}
                  </p>
                )}
              </Card>
            ))}

            <Card title="Amount outstanding">
              <p className="text-2xl font-bold text-slate-900">{rand(data.outstanding)}</p>
            </Card>

            {data.payments.length > 0 && (
              <Card title="Recent payments">
                <ul className="space-y-2 text-sm">
                  {data.payments.map((p, i) => (
                    <li key={i} className="flex justify-between gap-3">
                      <span className="text-slate-800">{day(p.date)}</span>
                      <span className="text-slate-500">{rand(p.amount)}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </>
        )}
      </div>
    </main>
  );
}
