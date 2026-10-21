"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Loader2,
  Truck,
} from "lucide-react";

import api from "@/lib/api";
import { formatDate, getApiErrorMessage } from "@/lib/format";
import { formatDateTime, formatTime } from "@/lib/datetime";
import { useCurrentUser } from "@/components/CurrentUserProvider";
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

type StepState = "done" | "todo" | "draft" | "pending";

type Row = {
  case_id: string;
  case_number: string;
  name: string;
  status: string;
  funeral_date: string | null;
  days_to_funeral: number | null;
  venue: string | null;
  steps: Record<string, StepState>;
  next_action: string;
  next_action_text: string;
  open_tasks: number;
  overdue_tasks: number;
  urgent: boolean;
};

type Overview = {
  kpis: {
    live_cases: number;
    funerals_today: number;
    funerals_this_week: number;
    needing_action: number;
    urgent: number;
    overdue_tasks: number;
    collections_due: number;
    vehicles_out_today: number;
    vehicles_in_fleet: number;
  };
  programme: {
    at: string;
    label: string;
    case_id: string;
    case_number: string;
    name: string;
    venue: string | null;
  }[];
  collections_due: {
    case_id: string;
    case_number: string;
    name: string;
    scheduled_at: string;
    status: string;
    overdue: boolean;
    pickup_type: string;
    pickup_address: string | null;
  }[];
  pipeline: Record<string, number>;
  step_labels: Record<string, string>;
  cases: Row[];
};

type Task = {
  id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  title: string;
  due_date: string | null;
  assigned_to: string | null;
  completed_at: string | null;
};

const STEP_ORDER = [
  "collection",
  "remains",
  "death_record",
  "arrangement",
  "paperwork",
  "vehicle",
];

function actionLink(row: Row): string {
  const base = `/cases/${row.case_id}`;

  switch (row.next_action) {
    case "arrange_collection":
    case "plan_arrangement":
    case "confirm_arrangement":
      return `${base}/arrangement`;
    case "take_in":
      return `${base}/remains`;
    case "death_record":
    case "paperwork":
      return `${base}/death-record`;
    case "book_vehicle":
      return "/resource-bookings";
    default:
      return base;
  }
}

function when(days: number | null): { text: string; hot: boolean } {
  if (days === null) return { text: "No date yet", hot: false };
  if (days < 0) return { text: `${-days}d ago`, hot: true };
  if (days === 0) return { text: "Today", hot: true };
  if (days === 1) return { text: "Tomorrow", hot: true };
  return { text: `In ${days} days`, hot: days <= 3 };
}

const PIPELINE_LABELS: Record<string, string> = {
  arrange_collection: "Collection to arrange",
  await_collection: "Awaiting collection",
  take_in: "To take into care",
  death_record: "Death record",
  plan_arrangement: "Arrangement to plan",
  confirm_arrangement: "To confirm with family",
  paperwork: "Paperwork",
  book_vehicle: "Vehicle to book",
  on_track: "On track",
};

/* ============================================================
   PAGE
============================================================ */

function StepDots({
  steps,
  labels,
}: {
  steps: Record<string, StepState>;
  labels: Record<string, string>;
}) {
  return (
    <span className="flex items-center gap-1.5" aria-label="Progress">
      {STEP_ORDER.map((key) => {
        const state = steps[key];
        const done = state === "done";
        const partial = state === "draft" || state === "pending";

        return (
          <span
            key={key}
            title={`${labels[key] ?? key}: ${
              done ? "done" : partial ? "in progress" : "still to do"
            }`}
            className={`h-2.5 w-2.5 rounded-full border ${
              done
                ? "border-emerald-600 bg-emerald-500"
                : partial
                  ? "border-amber-500 bg-amber-300"
                  : "border-[var(--fos-border)] bg-transparent"
            }`}
          />
        );
      })}
    </span>
  );
}

export default function OperationsDashboard() {
  const { user, can } = useCurrentUser();
  const [data, setData] = useState<Overview | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"action" | "all">("action");

  const load = useCallback(async () => {
    try {
      const [o, t] = await Promise.all([
        api.get<Overview>("/operations/overview"),
        api.get<Task[]>("/tasks").catch(() => ({ data: [] as Task[] })),
      ]);
      setData(o.data);
      setTasks(t.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load operations."));
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

  const k = data?.kpis;
  const mine = tasks.filter(
    (t) => t.assigned_to === user?.user_id && !t.completed_at
  );
  const rows = (data?.cases ?? []).filter(
    (r) => filter === "all" || r.next_action !== "on_track"
  );

  return (
    <main className="space-y-6 p-6 md:p-8">
      <DashboardHeader subtitle="Every live funeral, where it has got to, and the next thing to do." />

      <QuickActions
        actions={[
          ...(can("cases.create")
            ? [{ label: "New case", href: "/cases" }]
            : []),
          { label: "Run sheet", href: "/run-sheet" },
          { label: "Schedule", href: "/resource-bookings" },
          { label: "Staff workspace", href: "/staff" },
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

      {data && k && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <Tile
              label="Funerals today"
              value={k.funerals_today}
              hint={`${k.funerals_this_week} in the next 7 days`}
            />
            <Tile
              label="Need action"
              value={k.needing_action}
              hint={`${k.live_cases} live cases`}
              tone={k.urgent ? "warn" : "neutral"}
            />
            <Tile
              label="Urgent"
              value={k.urgent}
              hint="Funeral within 3 days, or tasks overdue"
              tone={k.urgent ? "warn" : "neutral"}
            />
            <Tile
              label="Collections due"
              value={k.collections_due}
              hint="Today or overdue"
              tone={k.collections_due ? "warn" : "neutral"}
            />
            <Tile
              label="Vehicles out today"
              value={`${k.vehicles_out_today} / ${k.vehicles_in_fleet}`}
              hint={`${k.overdue_tasks} overdue tasks`}
            />
          </div>

          {/* PIPELINE */}
          <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-[var(--fos-text)]">
              Where the cases are
            </h2>
            <ul className="mt-3 flex flex-wrap gap-2">
              {Object.entries(data.pipeline)
                .sort((a, b) => b[1] - a[1])
                .map(([code, count]) => (
                  <li
                    key={code}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      code === "on_track"
                        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"
                        : "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)]"
                    }`}
                  >
                    <span className="mr-1.5 font-bold tabular-nums">
                      {count}
                    </span>
                    {PIPELINE_LABELS[code] ?? code}
                  </li>
                ))}
              {Object.keys(data.pipeline).length === 0 && (
                <li className="text-sm text-[var(--fos-text-muted)]">
                  No live cases.
                </li>
              )}
            </ul>
          </section>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            {/* CASES */}
            <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-sm xl:col-span-2">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--fos-border)] px-5 py-4">
                <div>
                  <h2 className="text-sm font-semibold text-[var(--fos-text)]">
                    Funerals in progress
                  </h2>
                  <p className="text-xs text-[var(--fos-text-muted)]">
                    Soonest first. Dots: collection · in care · death record ·
                    arrangement · paperwork · vehicle.
                  </p>
                </div>
                <div
                  role="tablist"
                  className="inline-flex rounded-lg border border-[var(--fos-border)] p-0.5 text-xs"
                >
                  {(
                    [
                      ["action", "Needs action"],
                      ["all", "All"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      role="tab"
                      aria-selected={filter === id}
                      onClick={() => setFilter(id)}
                      className={`rounded-md px-3 py-1 font-medium ${
                        filter === id
                          ? "bg-[var(--fos-primary)] text-[var(--fos-on-primary)]"
                          : "text-[var(--fos-text-secondary)]"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {rows.length === 0 ? (
                <EmptyRow>
                  {filter === "action"
                    ? "Nothing is waiting on you. Every case is on track."
                    : "No live cases."}
                </EmptyRow>
              ) : (
                <ul className="divide-y divide-[var(--fos-border)]">
                  {rows.slice(0, 25).map((r) => {
                    const w = when(r.days_to_funeral);

                    return (
                      <li key={r.case_id} className="px-5 py-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <Link
                            href={`/cases/${r.case_id}`}
                            className="min-w-0"
                          >
                            <span className="block truncate text-sm font-semibold text-[var(--fos-text)]">
                              {r.name}
                            </span>
                            <span className="block truncate text-xs text-[var(--fos-text-muted)]">
                              {r.case_number}
                              {r.funeral_date
                                ? ` · ${formatDate(r.funeral_date)}`
                                : ""}
                              {r.venue ? ` · ${r.venue}` : ""}
                            </span>
                          </Link>

                          <div className="flex items-center gap-3">
                            <StepDots
                              steps={r.steps}
                              labels={data.step_labels}
                            />
                            <span
                              className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                                w.hot
                                  ? "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300"
                                  : "bg-[var(--fos-surface-muted)] text-[var(--fos-text-muted)]"
                              }`}
                            >
                              {w.text}
                            </span>
                          </div>
                        </div>

                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                          {r.next_action === "on_track" ? (
                            <span className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-300">
                              <CheckCircle2 size={14} /> On track
                            </span>
                          ) : (
                            <Link
                              href={actionLink(r)}
                              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--fos-primary)] hover:underline"
                            >
                              Next: {r.next_action_text}
                              <ArrowRight size={12} />
                            </Link>
                          )}
                          {r.overdue_tasks > 0 && (
                            <span className="flex items-center gap-1 text-xs text-red-700 dark:text-red-300">
                              <AlertTriangle size={12} />
                              {r.overdue_tasks} overdue{" "}
                              {r.overdue_tasks === 1 ? "task" : "tasks"}
                            </span>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <div className="space-y-6">
              {/* TODAY */}
              <Panel title="Today's programme">
                {data.programme.length === 0 ? (
                  <EmptyRow>No services or committals today.</EmptyRow>
                ) : (
                  <ul className="divide-y divide-[var(--fos-border)]">
                    {data.programme.map((p, i) => (
                      <li key={i} className="flex gap-3 px-5 py-3">
                        <span className="w-12 shrink-0 text-sm font-bold tabular-nums text-[var(--fos-text)]">
                          {formatTime(p.at)}
                        </span>
                        <Link href={`/cases/${p.case_id}`} className="min-w-0">
                          <span className="block text-sm font-medium text-[var(--fos-text)]">
                            {p.label}: {p.name}
                          </span>
                          <span className="block truncate text-xs text-[var(--fos-text-muted)]">
                            {p.venue ?? p.case_number}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              {/* COLLECTIONS */}
              <Panel title="Collections due">
                {data.collections_due.length === 0 ? (
                  <EmptyRow>No collections waiting.</EmptyRow>
                ) : (
                  <ul className="divide-y divide-[var(--fos-border)]">
                    {data.collections_due.map((c) => (
                      <li key={c.case_id} className="px-5 py-3">
                        <Link
                          href={`/cases/${c.case_id}/arrangement`}
                          className="block"
                        >
                          <span className="flex items-center gap-2 text-sm font-medium text-[var(--fos-text)]">
                            <Truck size={14} /> {c.name}
                          </span>
                          <span
                            className={`block text-xs ${
                              c.overdue
                                ? "text-red-700 dark:text-red-300"
                                : "text-[var(--fos-text-muted)]"
                            }`}
                          >
                            {c.overdue ? "Overdue · " : ""}
                            {formatDateTime(c.scheduled_at)} ·{" "}
                            {c.pickup_address || c.pickup_type}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              <Panel title="My tasks" href="/tasks" linkLabel="All tasks">
                {mine.length === 0 ? (
                  <EmptyRow>Nothing assigned to you.</EmptyRow>
                ) : (
                  <ul className="divide-y divide-[var(--fos-border)]">
                    {mine.slice(0, 6).map((t) => (
                      <li key={t.id} className="px-5 py-3">
                        <Link href={`/cases/${t.case_id}`} className="block">
                          <span className="block text-sm font-medium text-[var(--fos-text)]">
                            {t.title}
                          </span>
                          <span className="block text-xs text-[var(--fos-text-muted)]">
                            {t.deceased_full_name}
                            {t.due_date
                              ? ` · due ${formatDate(t.due_date)}`
                              : ""}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
