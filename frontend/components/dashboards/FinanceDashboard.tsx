"use client";

import api from "@/lib/api";
import { formatMoney } from "@/lib/format";
import {
  DashboardHeader,
  EmptyRow,
  Panel,
  QuickActions,
  Tile,
  useLoad,
} from "@/components/dashboards/Shared";

type Figures = {
  collected: number | string;
  new_members: number;
  memberships_lapsed: number;
};

type Overview = {
  current: Figures;
  now: {
    active_memberships: number;
    memberships_in_arrears: number;
    outstanding: number | string;
  };
};

type ArrearsRow = {
  membership_id: string;
  membership_number: string;
  member_name: string;
  phone: string | null;
  days_in_arrears: number;
  days_until_lapse: number | null;
  amount_unpaid: number | string;
};

type Arrears = {
  total: number;
  total_unpaid: number | string;
  rows: ArrearsRow[];
};

function monthRange(): { date_from: string; date_to: string } {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const day = (d: Date) =>
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  return {
    date_from: day(new Date(now.getFullYear(), now.getMonth(), 1)),
    date_to: day(now),
  };
}

export default function FinanceDashboard() {
  const overview = useLoad(
    async () =>
      (await api.get<Overview>("/reports/overview", { params: monthRange() }))
        .data
  );
  const arrears = useLoad(async () =>
    (await api.get<Arrears>("/reports/arrears")).data
  );

  const o = overview.data;
  const rows = arrears.data?.rows ?? [];

  return (
    <main className="space-y-6 p-6 md:p-8">
      <DashboardHeader subtitle="Contributions, new memberships and who is behind, this month." />

      <QuickActions
        actions={[
          { label: "Record a payment", href: "/membership-payments" },
          { label: "New member", href: "/members" },
          { label: "Contributions", href: "/membership-contributions" },
          { label: "Send reminders", href: "/communications" },
        ]}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile
          label="Collected this month"
          value={o ? `R ${formatMoney(o.current.collected)}` : "–"}
        />
        <Tile label="New members" value={o?.current.new_members ?? "–"} />
        <Tile
          label="Behind on payments"
          value={o?.now.memberships_in_arrears ?? "–"}
          tone={o?.now.memberships_in_arrears ? "warn" : "neutral"}
          hint={
            arrears.data
              ? `R ${formatMoney(arrears.data.total_unpaid)} unpaid`
              : undefined
          }
        />
        <Tile
          label="Lapsed this month"
          value={o?.current.memberships_lapsed ?? "–"}
        />
      </div>

      <Panel
        title="Members behind on payments"
        href="/memberships"
        linkLabel="Memberships"
      >
        {arrears.error ? (
          <EmptyRow>{arrears.error}</EmptyRow>
        ) : rows.length === 0 ? (
          <EmptyRow>Nobody is behind.</EmptyRow>
        ) : (
          <ul className="divide-y divide-[var(--fos-border)]">
            {rows.slice(0, 10).map((r) => (
              <li
                key={r.membership_id}
                className="flex items-center justify-between gap-3 px-5 py-3"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-[var(--fos-text)]">
                    {r.member_name}
                  </span>
                  <span className="block truncate text-xs text-[var(--fos-text-muted)]">
                    {r.membership_number}
                    {r.phone ? ` · ${r.phone}` : ""}
                  </span>
                </span>
                <span className="shrink-0 text-right tabular-nums">
                  <span className="block text-sm text-[var(--fos-text)]">
                    R {formatMoney(r.amount_unpaid)}
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
    </main>
  );
}
