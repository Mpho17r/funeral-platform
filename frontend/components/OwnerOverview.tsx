"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Download, TrendingDown, TrendingUp } from "lucide-react";

import api from "@/lib/api";
import { formatDate, formatMoney, getApiErrorMessage } from "@/lib/format";
import { Banner } from "@/components/Notices";

type Figures = {
  collected: number | string;
  collected_cases: number | string;
  collected_memberships: number | string;
  cases_opened: number;
  funerals_held: number;
  new_members: number;
  memberships_lapsed: number;
  memberships_cancelled: number;
};

export type OverviewData = {
  date_from: string;
  date_to: string;
  previous_from: string;
  previous_to: string;
  current: Figures;
  previous: Figures;
  trend: {
    month: string;
    collected: number | string;
    cases_opened: number;
    new_members: number;
  }[];
  now: {
    active_memberships: number;
    memberships_in_arrears: number;
    memberships_lapsed: number;
    outstanding: number | string;
    cases_with_balance: number;
  };
};

type ArrearsRow = {
  membership_id: string;
  membership_number: string;
  member_name: string;
  phone: string | null;
  plan: string | null;
  days_in_arrears: number;
  days_until_lapse: number | null;
  amount_unpaid: number | string;
};

type DebtorRow = {
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  next_of_kin_name: string | null;
  next_of_kin_phone: string | null;
  age_days: number;
  balance: number | string;
};

const rand = (v: number | string) => `R ${formatMoney(v)}`;

/** Change against the previous period. `goodWhenUp` flips the colour. */
function Change({
  now,
  before,
  goodWhenUp = true,
}: {
  now: number;
  before: number;
  goodWhenUp?: boolean;
}) {
  if (before === 0 && now === 0) {
    return <span className="text-xs text-gray-500">No change</span>;
  }

  if (before === 0) {
    return <span className="text-xs text-gray-500">New this period</span>;
  }

  const pct = Math.round(((now - before) / before) * 100);

  if (pct === 0) {
    return <span className="text-xs text-gray-500">No change</span>;
  }

  const up = pct > 0;
  const good = up === goodWhenUp;
  const Icon = up ? TrendingUp : TrendingDown;

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium ${
        good ? "text-emerald-700" : "text-red-700"
      }`}
    >
      <Icon size={13} aria-hidden />
      {up ? "+" : ""}
      {pct}% <span className="font-normal text-gray-500">vs before</span>
    </span>
  );
}

function Kpi({
  label,
  value,
  now,
  before,
  goodWhenUp,
}: {
  label: string;
  value: string;
  now: number;
  before: number;
  goodWhenUp?: boolean;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
      <div className="mt-1">
        <Change now={now} before={before} goodWhenUp={goodWhenUp} />
      </div>
    </div>
  );
}

function TrendChart({ trend }: { trend: OverviewData["trend"] }) {
  const values = trend.map((t) => Number(t.collected));
  const max = Math.max(...values, 1);

  return (
    <div
      className="flex h-44 items-end gap-3 px-5 pb-4 pt-6"
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
      {trend.map((t, i) => {
        const v = values[i];
        const last = i === trend.length - 1;

        return (
          <div
            key={t.month}
            className="flex h-full flex-1 flex-col items-center justify-end gap-1"
          >
            <span className="text-[11px] tabular-nums text-gray-500">
              {v > 0 ? formatMoney(v).replace(/\.00$/, "") : ""}
            </span>
            <div
              className="w-full max-w-12 rounded-t-md"
              style={{
                height: `${Math.max((v / max) * 100, v > 0 ? 3 : 0)}%`,
                background: "var(--fos-primary)",
                opacity: last ? 1 : 0.55,
              }}
            />
            <span className="text-xs text-gray-500">
              {new Date(t.month).toLocaleString("en-GB", {
                month: "short",
              })}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function ListPanel({
  title,
  note,
  csv,
  onDownload,
  extra,
  children,
}: {
  title: string;
  note: string;
  csv: string;
  onDownload: (path: string) => void;
  extra?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-gray-200 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
          <p className="mt-0.5 text-xs text-gray-500">{note}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
        {extra}
        <button
          type="button"
          onClick={() => onDownload(csv)}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          <Download size={14} aria-hidden /> CSV
        </button>
        </div>
      </div>
      {children}
    </section>
  );
}

export default function OwnerOverview({
  data,
  branchId,
}: {
  data: OverviewData;
  branchId: string | null;
}) {
  const [arrears, setArrears] = useState<{
    total: number;
    total_unpaid: number | string;
    rows: ArrearsRow[];
  } | null>(null);
  const [debtors, setDebtors] = useState<{
    total: number;
    total_owed: number | string;
    rows: DebtorRow[];
  } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const params = branchId ? { branch_id: branchId } : {};

    Promise.all([
      api.get("/reports/arrears", { params }),
      api.get("/reports/debtors", { params }),
    ])
      .then(([a, d]) => {
        if (!cancelled) {
          setArrears(a.data);
          setDebtors(d.data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(getApiErrorMessage(err, "Could not load the lists."));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [branchId]);

  async function download(path: string) {
    try {
      const response = await api.get(`/reports/${path}`, {
        params: branchId ? { branch_id: branchId } : {},
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = path;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not download the file."));
    }
  }

  const c = data.current;
  const p = data.previous;

  return (
    <div className="space-y-6">
      <p className="text-xs text-gray-500">
        Compared with {formatDate(data.previous_from)} to{" "}
        {formatDate(data.previous_to)}.
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label="Money collected"
          value={rand(c.collected)}
          now={Number(c.collected)}
          before={Number(p.collected)}
        />
        <Kpi
          label="Cases opened"
          value={String(c.cases_opened)}
          now={c.cases_opened}
          before={p.cases_opened}
        />
        <Kpi
          label="New members"
          value={String(c.new_members)}
          now={c.new_members}
          before={p.new_members}
        />
        <Kpi
          label="Memberships lapsed"
          value={String(c.memberships_lapsed)}
          now={c.memberships_lapsed}
          before={p.memberships_lapsed}
          goodWhenUp={false}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Of the money collected</p>
          <p className="mt-2 text-sm text-gray-700">
            Funerals {rand(c.collected_cases)}
          </p>
          <p className="text-sm text-gray-700">
            Memberships {rand(c.collected_memberships)}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Funerals held</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">
            {c.funerals_held}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            {c.memberships_cancelled} memberships cancelled
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Right now</p>
          <p className="mt-2 text-sm text-gray-700">
            {data.now.active_memberships} active ·{" "}
            {data.now.memberships_in_arrears} behind ·{" "}
            {data.now.memberships_lapsed} lapsed
          </p>
          <p className="text-sm font-medium text-gray-900">
            {rand(data.now.outstanding)} owed on{" "}
            {data.now.cases_with_balance} cases
          </p>
        </div>
      </div>

      <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-gray-900">
            Money collected, last 6 months
          </h2>
        </div>
        <TrendChart trend={data.trend} />
      </section>

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ListPanel
          title="Members behind on payments"
          note={
            arrears
              ? `${arrears.total} members · ${rand(arrears.total_unpaid)} unpaid`
              : "Loading…"
          }
          csv="arrears.csv"
          onDownload={download}
          extra={
            <Link
              href="/communications"
              className="inline-flex shrink-0 items-center rounded-lg bg-[var(--fos-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--fos-on-primary)]"
            >
              Send reminders
            </Link>
          }
        >
          {arrears && arrears.rows.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-gray-500">
              Nobody is behind. 
            </p>
          ) : (
            <div className="max-h-96 overflow-auto">
              <table className="min-w-full text-sm">
                <tbody className="divide-y divide-gray-100">
                  {arrears?.rows.map((r) => (
                    <tr key={r.membership_id}>
                      <td className="px-5 py-3">
                        <p className="font-medium text-gray-900">
                          {r.member_name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {r.membership_number}
                          {r.phone ? ` · ${r.phone}` : ""}
                        </p>
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        <p className="text-gray-900">
                          {rand(r.amount_unpaid)}
                        </p>
                        <p className="text-xs text-gray-500">
                          {r.days_in_arrears} days
                          {r.days_until_lapse !== null &&
                            ` · lapses in ${Math.max(r.days_until_lapse, 0)}`}
                        </p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </ListPanel>

        <ListPanel
          title="Cases that still owe"
          note={
            debtors
              ? `${debtors.total} cases · ${rand(debtors.total_owed)} owed`
              : "Loading…"
          }
          csv="debtors.csv"
          onDownload={download}
        >
          {debtors && debtors.rows.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-gray-500">
              No case has a balance.
            </p>
          ) : (
            <div className="max-h-96 overflow-auto">
              <table className="min-w-full text-sm">
                <tbody className="divide-y divide-gray-100">
                  {debtors?.rows.map((r) => (
                    <tr key={r.case_id}>
                      <td className="px-5 py-3">
                        <p className="font-medium text-gray-900">
                          {r.deceased_full_name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {r.case_number}
                          {r.next_of_kin_name
                            ? ` · ${r.next_of_kin_name}`
                            : ""}
                          {r.next_of_kin_phone
                            ? ` ${r.next_of_kin_phone}`
                            : ""}
                        </p>
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        <p className="text-gray-900">{rand(r.balance)}</p>
                        <p className="text-xs text-gray-500">
                          {r.age_days} days old
                        </p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </ListPanel>
      </div>
    </div>
  );
}
