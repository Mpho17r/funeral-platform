"use client";

import Link from "next/link";

import api from "@/lib/api";
import { formatDate, formatStatus } from "@/lib/format";
import {
  DashboardHeader,
  EmptyRow,
  Panel,
  QuickActions,
  Tile,
  useLoad,
} from "@/components/dashboards/Shared";

type Summary = {
  total_cases: number;
  active_cases: number;
  upcoming_funeral_count: number;
  recent_cases: {
    id: string;
    case_number: string;
    deceased_full_name: string;
    status: string;
    funeral_date: string | null;
  }[];
  upcoming_funerals: {
    id: string;
    case_number: string;
    deceased_full_name: string;
    funeral_date: string;
    funeral_venue: string | null;
  }[];
};

type Task = {
  id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  title: string;
  due_date: string | null;
  assigned_to_name: string | null;
  completed_at: string | null;
};

export default function OperationsDashboard() {
  const summary = useLoad(async () =>
    (await api.get<Summary>("/dashboard/summary")).data
  );
  const tasks = useLoad(async () =>
    (await api.get<Task[]>("/tasks")).data
  );

  const today = new Date().toISOString().slice(0, 10);
  const open = (tasks.data ?? []).filter((t) => !t.completed_at);
  const overdue = open.filter((t) => t.due_date && t.due_date < today);
  const s = summary.data;

  return (
    <main className="space-y-6 p-6 md:p-8">
      <DashboardHeader subtitle="Every case, what comes next, and what is running late." />

      <QuickActions
        actions={[
          { label: "New case", href: "/cases" },
          { label: "Run sheet", href: "/run-sheet" },
          { label: "Schedule", href: "/resource-bookings" },
          { label: "Staff workspace", href: "/staff" },
        ]}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Active cases" value={s?.active_cases ?? "–"} />
        <Tile
          label="Funerals in 30 days"
          value={s?.upcoming_funeral_count ?? "–"}
        />
        <Tile label="Open tasks" value={tasks.data ? open.length : "–"} />
        <Tile
          label="Overdue tasks"
          value={tasks.data ? overdue.length : "–"}
          tone={overdue.length ? "warn" : "neutral"}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Upcoming funerals" href="/run-sheet" linkLabel="Run sheet">
          {summary.error ? (
            <EmptyRow>{summary.error}</EmptyRow>
          ) : !s || s.upcoming_funerals.length === 0 ? (
            <EmptyRow>No funerals in the next 30 days.</EmptyRow>
          ) : (
            <ul className="divide-y divide-[var(--fos-border)]">
              {s.upcoming_funerals.map((f) => (
                <li key={f.id} className="px-5 py-3">
                  <Link href={`/cases/${f.id}`} className="block">
                    <span className="block text-sm font-medium text-[var(--fos-text)]">
                      {f.deceased_full_name}
                    </span>
                    <span className="block text-xs text-[var(--fos-text-muted)]">
                      {formatDate(f.funeral_date)}
                      {f.funeral_venue ? ` · ${f.funeral_venue}` : ""} ·{" "}
                      {f.case_number}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Latest cases" href="/cases" linkLabel="All cases">
          {!s || s.recent_cases.length === 0 ? (
            <EmptyRow>No cases yet.</EmptyRow>
          ) : (
            <ul className="divide-y divide-[var(--fos-border)]">
              {s.recent_cases.map((c) => (
                <li key={c.id} className="px-5 py-3">
                  <Link
                    href={`/cases/${c.id}`}
                    className="flex items-center justify-between gap-3"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-[var(--fos-text)]">
                        {c.deceased_full_name}
                      </span>
                      <span className="block text-xs text-[var(--fos-text-muted)]">
                        {c.case_number}
                      </span>
                    </span>
                    <span className="shrink-0 rounded-full bg-[var(--fos-surface-muted)] px-2.5 py-0.5 text-xs text-[var(--fos-text-secondary)]">
                      {formatStatus(c.status)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Overdue work" href="/tasks" linkLabel="All tasks">
        {overdue.length === 0 ? (
          <EmptyRow>Nothing is overdue.</EmptyRow>
        ) : (
          <ul className="divide-y divide-[var(--fos-border)]">
            {overdue.slice(0, 8).map((t) => (
              <li key={t.id} className="px-5 py-3">
                <Link href={`/cases/${t.case_id}`} className="block">
                  <span className="block text-sm font-medium text-[var(--fos-text)]">
                    {t.title}
                  </span>
                  <span className="block text-xs text-[var(--fos-text-muted)]">
                    {t.deceased_full_name} · due{" "}
                    {t.due_date ? formatDate(t.due_date) : ""}
                    {t.assigned_to_name ? ` · ${t.assigned_to_name}` : ""}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </main>
  );
}
