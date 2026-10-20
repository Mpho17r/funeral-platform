"use client";

import Link from "next/link";

import api from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import {
  DashboardHeader,
  EmptyRow,
  Panel,
  QuickActions,
  Tile,
  useLoad,
} from "@/components/dashboards/Shared";

type Entry = {
  remains_id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  tag_number: string;
  location_name: string | null;
  received_at: string;
  identified: boolean;
  cooled: boolean;
  cooling_overdue: boolean;
};

type Board = {
  in_custody: number;
  cooling_overdue: number;
  entries: Entry[];
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

export default function MortuaryDashboard() {
  const { user } = useCurrentUser();
  const board = useLoad(async () =>
    (await api.get<Board>("/mortuary/board")).data
  );
  const tasks = useLoad(async () =>
    (await api.get<Task[]>("/tasks")).data
  );

  const entries = board.data?.entries ?? [];
  const notIdentified = entries.filter((e) => !e.identified).length;
  const mine = (tasks.data ?? []).filter(
    (t) => t.assigned_to === user?.user_id && !t.completed_at
  );

  return (
    <main className="space-y-6 p-6 md:p-8">
      <DashboardHeader subtitle="Who is in our care, what needs doing, and what is ready." />

      <QuickActions
        actions={[
          { label: "Mortuary board", href: "/mortuary" },
          { label: "Staff workspace", href: "/staff" },
        ]}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="In our care" value={board.data?.in_custody ?? "–"} />
        <Tile
          label="Cooling overdue"
          value={board.data?.cooling_overdue ?? "–"}
          tone={board.data?.cooling_overdue ? "warn" : "neutral"}
        />
        <Tile
          label="Not yet identified"
          value={board.data ? notIdentified : "–"}
          tone={notIdentified ? "warn" : "neutral"}
        />
        <Tile label="My open tasks" value={tasks.data ? mine.length : "–"} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="In our care" href="/mortuary" linkLabel="Open board">
          {board.error ? (
            <EmptyRow>{board.error}</EmptyRow>
          ) : entries.length === 0 ? (
            <EmptyRow>Nobody is in our care right now.</EmptyRow>
          ) : (
            <ul className="divide-y divide-[var(--fos-border)]">
              {entries.slice(0, 8).map((e) => (
                <li key={e.remains_id} className="px-5 py-3">
                  <Link
                    href={`/cases/${e.case_id}`}
                    className="flex items-center justify-between gap-3"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-[var(--fos-text)]">
                        {e.deceased_full_name}
                      </span>
                      <span className="block truncate text-xs text-[var(--fos-text-muted)]">
                        Tag {e.tag_number}
                        {e.location_name ? ` · ${e.location_name}` : ""} ·
                        received {formatDate(e.received_at)}
                      </span>
                    </span>
                    <span className="flex shrink-0 gap-1.5 text-[11px] font-medium">
                      {e.cooling_overdue && (
                        <span className="rounded-full bg-red-100 px-2 py-0.5 text-red-700">
                          Cooling overdue
                        </span>
                      )}
                      {!e.identified && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-800">
                          Not identified
                        </span>
                      )}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="My tasks" href="/tasks" linkLabel="All tasks">
          {tasks.error ? (
            <EmptyRow>{tasks.error}</EmptyRow>
          ) : mine.length === 0 ? (
            <EmptyRow>Nothing assigned to you.</EmptyRow>
          ) : (
            <ul className="divide-y divide-[var(--fos-border)]">
              {mine.slice(0, 8).map((t) => (
                <li key={t.id} className="px-5 py-3">
                  <Link href={`/cases/${t.case_id}`} className="block">
                    <span className="block text-sm font-medium text-[var(--fos-text)]">
                      {t.title}
                    </span>
                    <span className="block text-xs text-[var(--fos-text-muted)]">
                      {t.deceased_full_name} · {t.case_number}
                      {t.due_date ? ` · due ${formatDate(t.due_date)}` : ""}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </main>
  );
}
