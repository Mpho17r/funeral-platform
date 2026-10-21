"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loader2, TrendingDown, TrendingUp } from "lucide-react";

import api from "@/lib/api";
import { formatDate, formatMoney, getApiErrorMessage } from "@/lib/format";
import { Banner } from "@/components/Notices";
import {
  DashboardHeader,
  EmptyRow,
  Panel,
  QuickActions,
  Tile,
} from "@/components/dashboards/Shared";

/* ============================================================
   TYPES
============================================================ */

type Overview = {
  collected: {
    today: number;
    month: number;
    month_cases: number;
    month_memberships: number;
    last_month: number;
  };
  contributions: {
    due_soon_count: number;
    due_soon_amount: number;
    overdue_count: number;
    overdue_amount: number;
    collection_rate_percent: number | null;
    due_days: number;
  };
  memberships: {
    active: number;
    in_arrears: number;
    lapsed: number;
    new_this_month: number;
    lapsed_this_month: number;
  };
  outstanding_on_cases: number;
  claims_open: number;
  reminders_queued: number;
  trend: { month: string; collected: number | string }[];
  arrears: {
    total: number;
    total_unpaid: number;
    rows: {
      membership_id: string;
      membership_number: string;
      member_name: string;
      phone: string | null;
      days_in_arrears: number;
      days_until_lapse: number | null;
      amount_unpaid: number;
    }[];
  };
  debtors: {
    total: number;
    total_owed: number;
    rows: {
      case_id: string;
      case_number: string;
      deceased_full_name: string;
      next_of_kin_name: string | null;
      next_of_kin_phone: string | null;
      age_days: number;
      balance: number;
    }[];
  };
  recent_payments: {
    kind: "membership" | "case";
    date: string;
    who: string;
    reference: string;
    method: string;
    amount: number;
    link: string;
  }[];
};

const rand = (v: number | string) => `R ${formatMoney(v)}`;

function Trend({ trend }: { trend: Overview["trend"] }) {
  const values = trend.map((t) => Number(t.collected));
  const max = Math.max(...values, 1);

  return (
    <div
      className="flex h-36 items-end gap-3 px-5 pb-4 pt-5"
      role="img"
      aria-label={`Money collected per month: ${trend
        .map(
          (t) =>
            `${new Date(t.month).toLocaleString("en-GB", {
              month: "long",
            })} ${rand(t.collected)}`
        )
        .join(", ")}`}
    >
      {trend.map((t, i) => (
        <div
          key={t.month}
          className="flex h-full flex-1 flex-col items-center justify-end gap-1"
        >
          <span className="text-[11px] tabular-nums text-[var(--fos-text-muted)]">
            {values[i] > 0
              ? formatMoney(values[i]).replace(/\.00$/, "")
              : ""}
          </span>
          <div
            className="w-full max-w-12 rounded-t-md"
            style={{
              height: `${Math.max((values[i] / max) * 100, values[i] > 0 ? 3 : 0)}%`,
              background: "var(--fos-primary)",
              opacity: i === trend.length - 1 ? 1 : 0.55,
            }}
          />
          <span className="text-xs text-[var(--fos-text-muted)]">
            {new Date(t.month).toLocaleString("en-GB", { month: "short" })}
          </span>
        </div>
      ))}
    </div>
  );
}

function Change({ now, before }: { now: number; before: number }) {
  if (before === 0) {
    return now === 0 ? null : <>New this month</>;
  }

  const pct = Math.round(((now - before) / before) * 100);

  if (pct === 0) return <>Same as last month</>;

  const Icon = pct > 0 ? TrendingUp : TrendingDown;

  return (
    <span
      className={`inline-flex items-center gap-1 font-medium ${
        pct > 0 ? "text-emerald-700" : "text-red-700"
      }`}
    >
      <Icon size={12} aria-hidden />
      {pct > 0 ? "+" : ""}
      {pct}% vs last month
    </span>
  );
}

/* ============================================================
   PAGE
============================================================ */

export default function FinanceDashboard() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData((await api.get<Overview>("/finance/overview")).data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load finance."));
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const timer = window.setInterval(() => {
      if (!document.hidden) load();
    }, 60000);
    return () => window.clearInterval(timer);
  }, [load]);

  const c = data?.collected;
  const k = data?.contributions;
  const m = data?.memberships;

  return (
    <main className="space-y-6 p-6 md:p-8">
      <DashboardHeader subtitle="Money in, money due, and who needs chasing today." />

      <QuickActions
        actions={[
          { label: "Record a payment", href: "/membership-payments" },
          { label: "New member", href: "/members" },
          { label: "Contributions", href: "/membership-contributions" },
          {
            label: data?.reminders_queued
              ? `Send reminders (${data.reminders_queued} queued)`
              : "Send reminders",
            href: "/communications",
          },
        ]}
      />

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      {!data && !error && (
        <div className="flex justify-center py-16 text-[var(--fos-text-muted)]">
          <Loader2 className="animate-spin" />
        </div>
      )}

      {data && c && k && m && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <Tile label="Collected today" value={rand(c.today)} />
            <Tile
              label="Collected this month"
              value={rand(c.month)}
              hint={undefined}
            />
            <Tile
              label="Contribution collection rate"
              value={
                k.collection_rate_percent === null
                  ? "–"
                  : `${k.collection_rate_percent}%`
              }
              hint="Paid against due, this month"
            />
            <Tile
              label={`Due in ${k.due_days} days`}
              value={rand(k.due_soon_amount)}
              hint={`${k.due_soon_count} contributions`}
            />
            <Tile
              label="Overdue"
              value={rand(k.overdue_amount)}
              hint={`${k.overdue_count} contributions`}
              tone={k.overdue_count ? "warn" : "neutral"}
            />
          </div>

          <p className="-mt-3 text-xs text-[var(--fos-text-muted)]">
            This month:{" "}
            <Change now={c.month} before={c.last_month} /> · funerals{" "}
            {rand(c.month_cases)} · memberships {rand(c.month_memberships)}
          </p>

          <section className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {(
              [
                ["Active memberships", m.active, false],
                ["Behind on payments", m.in_arrears, m.in_arrears > 0],
                ["Lapsed", m.lapsed, false],
                ["New this month", m.new_this_month, false],
                ["Lapsed this month", m.lapsed_this_month, false],
                ["Open claims", data.claims_open, false],
              ] as const
            ).map(([label, value, warn]) => (
              <Tile
                key={label}
                label={label}
                value={value}
                tone={warn ? "warn" : "neutral"}
              />
            ))}
          </section>

          <Panel title="Money collected, last 6 months">
            <Trend trend={data.trend} />
          </Panel>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Panel
              title="Members behind on payments"
              href="/memberships"
              linkLabel={`${data.arrears.total} members · ${rand(
                data.arrears.total_unpaid
              )}`}
            >
              {data.arrears.rows.length === 0 ? (
                <EmptyRow>Nobody is behind.</EmptyRow>
              ) : (
                <ul className="divide-y divide-[var(--fos-border)]">
                  {data.arrears.rows.map((r) => (
                    <li
                      key={r.membership_id}
                      className="flex items-center justify-between gap-3 px-5 py-3"
                    >
                      <Link
                        href="/memberships"
                        className="min-w-0"
                      >
                        <span className="block truncate text-sm font-medium text-[var(--fos-text)]">
                          {r.member_name}
                        </span>
                        <span className="block truncate text-xs text-[var(--fos-text-muted)]">
                          {r.membership_number}
                          {r.phone ? ` · ${r.phone}` : ""}
                        </span>
                      </Link>
                      <span className="shrink-0 text-right tabular-nums">
                        <span className="block text-sm text-[var(--fos-text)]">
                          {rand(r.amount_unpaid)}
                        </span>
                        <span className="block text-xs text-[var(--fos-text-muted)]">
                          {r.days_in_arrears} days
                          {r.days_until_lapse !== null
                            ? ` · lapses in ${Math.max(r.days_until_lapse, 0)}`
                            : ""}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel
              title="Funerals that still owe"
              href="/reports"
              linkLabel={`${data.debtors.total} cases · ${rand(
                data.debtors.total_owed
              )}`}
            >
              {data.debtors.rows.length === 0 ? (
                <EmptyRow>No case has a balance.</EmptyRow>
              ) : (
                <ul className="divide-y divide-[var(--fos-border)]">
                  {data.debtors.rows.map((r) => (
                    <li
                      key={r.case_id}
                      className="flex items-center justify-between gap-3 px-5 py-3"
                    >
                      <Link
                        href={`/cases/${r.case_id}/financial`}
                        className="min-w-0"
                      >
                        <span className="block truncate text-sm font-medium text-[var(--fos-text)]">
                          {r.deceased_full_name}
                        </span>
                        <span className="block truncate text-xs text-[var(--fos-text-muted)]">
                          {r.case_number}
                          {r.next_of_kin_name
                            ? ` · ${r.next_of_kin_name}`
                            : ""}
                          {r.next_of_kin_phone
                            ? ` ${r.next_of_kin_phone}`
                            : ""}
                        </span>
                      </Link>
                      <span className="shrink-0 text-right tabular-nums">
                        <span className="block text-sm text-[var(--fos-text)]">
                          {rand(r.balance)}
                        </span>
                        <span className="block text-xs text-[var(--fos-text-muted)]">
                          {r.age_days} days old
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <Panel
            title="Recent payments"
            href="/membership-payments"
            linkLabel="All payments"
          >
            {data.recent_payments.length === 0 ? (
              <EmptyRow>No payments recorded yet.</EmptyRow>
            ) : (
              <ul className="divide-y divide-[var(--fos-border)]">
                {data.recent_payments.map((p, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between gap-3 px-5 py-3"
                  >
                    <Link href={p.link} className="min-w-0">
                      <span className="block truncate text-sm font-medium text-[var(--fos-text)]">
                        {p.who}
                      </span>
                      <span className="block truncate text-xs text-[var(--fos-text-muted)]">
                        {p.kind === "membership"
                          ? "Membership"
                          : "Funeral"}{" "}
                        · {p.reference} · {p.method.replace("_", " ")} ·{" "}
                        {formatDate(p.date)}
                      </span>
                    </Link>
                    <span className="shrink-0 text-sm font-medium tabular-nums text-[var(--fos-text)]">
                      {rand(p.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      )}
    </main>
  );
}
