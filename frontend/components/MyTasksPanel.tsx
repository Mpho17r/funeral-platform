"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CalendarClock, ClipboardList, Users } from "lucide-react";

import api from "@/lib/api";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import TaskDrawer, { STATUS_LABEL, type TaskStatus, whenDue } from "@/components/TaskDrawer";

type Row = {
  id: string;
  title: string;
  deceased_full_name: string;
  status: TaskStatus;
  due_at: string | null;
  due_date: string | null;
  shared: boolean;
};

/** Only the tasks given to the signed-in person. */
export default function MyTasksPanel() {
  const { user } = useCurrentUser();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [now] = useState(() => Date.now());

  const load = useCallback(() => {
    return api
      .get<{ tasks: Row[] }>("/tasks/board", { params: { scope: "mine", state: "open" } })
      .then((r) => setRows(r.data.tasks))
      .catch(() => setRows([]));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function quick(id: string, status: TaskStatus) {
    try {
      await api.post(`/tasks/${id}/status`, { status });
    } finally {
      await load();
    }
  }

  const late = (t: Row) =>
    t.due_at
      ? new Date(t.due_at).getTime() < now
      : t.due_date
        ? new Date(`${t.due_date}T23:59:59`).getTime() < now
        : false;

  return (
    <section className="overflow-hidden rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--fos-border)] px-5 py-4">
        <h2 className="flex items-center gap-2 font-display text-xl font-semibold">
          <ClipboardList size={19} /> My tasks
        </h2>
        <Link href="/tasks" className="text-sm text-[var(--fos-text-muted)] hover:text-[var(--fos-text)]">
          All my tasks ↗
        </Link>
      </div>
      <div className="p-3">
        {rows === null && <p className="p-2 text-sm text-[var(--fos-text-muted)]">Loading…</p>}
        {rows && rows.length === 0 && (
          <p className="p-2 text-sm text-[var(--fos-text-muted)]">Nothing is waiting for you.</p>
        )}
        <ul className="divide-y divide-[var(--fos-border)]">
          {rows?.slice(0, 6).map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-2 py-2.5">
              <button type="button" onClick={() => setOpenId(t.id)} className="min-w-0 flex-1 text-left">
                <span className="block truncate text-sm font-medium">{t.title}</span>
                <span className="flex items-center gap-2 text-xs text-[var(--fos-text-muted)]">
                  <span className={`flex items-center gap-1 ${late(t) ? "font-semibold text-red-600" : ""}`}>
                    <CalendarClock size={12} /> {whenDue(t.due_at, t.due_date)}
                  </span>
                  {t.shared && (
                    <span className="flex items-center gap-1">
                      <Users size={12} /> shared
                    </span>
                  )}
                </span>
              </button>
              <select
                aria-label="Status"
                value={t.status}
                onChange={(e) => void quick(t.id, e.target.value as TaskStatus)}
                className="rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-2 py-1 text-xs"
              >
                {(Object.keys(STATUS_LABEL) as TaskStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      </div>
      {openId && (
        <TaskDrawer taskId={openId} meId={user?.user_id} onClose={() => setOpenId(null)} onChanged={() => void load()} />
      )}
    </section>
  );
}
