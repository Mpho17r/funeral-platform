"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, ClipboardList, Loader2, RefreshCw, Users } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import TaskDrawer, { STATUS_LABEL, type TaskStatus, whenDue } from "@/components/TaskDrawer";

type Row = {
  id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  title: string;
  status: TaskStatus;
  due_date: string | null;
  due_at: string | null;
  assignees: { id: string; name: string }[];
  is_mine: boolean;
  shared: boolean;
  created_at: string;
  completed_at: string | null;
};

type Board = { scope: Scope; scopes: Scope[]; tasks: Row[] };
type Scope = "mine" | "branch" | "organisation";

const SCOPE_LABEL: Record<Scope, string> = {
  mine: "My tasks",
  branch: "Whole branch",
  organisation: "Whole organisation",
};

const STATUS_STYLE: Record<TaskStatus, string> = {
  pending: "bg-amber-50 text-amber-700",
  in_progress: "bg-blue-50 text-blue-700",
  completed: "bg-emerald-50 text-emerald-700",
};

function dayLabel(value: string) {
  const d = new Date(value);
  const today = new Date();
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  const yesterday = new Date(today.getTime() - 86400000);
  if (same(d, today)) return "Given today";
  if (same(d, yesterday)) return "Given yesterday";
  return `Given ${d.toLocaleDateString("en-ZA", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}`;
}

function isOverdue(t: Row, now: number) {
  if (t.status === "completed") return false;
  if (t.due_at) return new Date(t.due_at).getTime() < now;
  if (t.due_date) return new Date(`${t.due_date}T23:59:59`).getTime() < now;
  return false;
}

export default function TasksWorkspacePage() {
  const { user } = useCurrentUser();
  const [scope, setScope] = useState<Scope>("mine");
  const [state, setState] = useState<"open" | "done" | "all">("open");
  const [board, setBoard] = useState<Board | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [now] = useState(() => Date.now());

  const load = useCallback(() => {
    return api
      .get<Board>("/tasks/board", { params: { scope, state } })
      .then((r) => {
        setBoard(r.data);
        setError("");
      })
      .catch((err) => setError(getApiErrorMessage(err, "Could not load tasks.")))
      .finally(() => setLoading(false));
  }, [scope, state]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    void load();
  }, [load]);

  const groups = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = (board?.tasks ?? []).filter(
      (t) =>
        !q ||
        t.title.toLowerCase().includes(q) ||
        t.deceased_full_name.toLowerCase().includes(q) ||
        t.assignees.some((a) => a.name.toLowerCase().includes(q)),
    );
    const byDay = new Map<string, Row[]>();
    for (const t of rows) {
      const key = new Date(t.created_at).toDateString();
      byDay.set(key, [...(byDay.get(key) ?? []), t]);
    }
    return [...byDay.values()]
      .map((list) => ({
        label: dayLabel(list[0].created_at),
        at: new Date(list[0].created_at).getTime(),
        tasks: list.sort((a, b) => {
          const ad = a.due_at ?? a.due_date;
          const bd = b.due_at ?? b.due_date;
          if (!ad) return 1;
          if (!bd) return -1;
          return new Date(ad).getTime() - new Date(bd).getTime();
        }),
      }))
      .sort((a, b) => b.at - a.at);
  }, [board, search]);

  const scopes = board?.scopes ?? ["mine"];

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <ClipboardList size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Tasks</h1>
            <p className="text-sm text-slate-500">Grouped by the day they were given, with when each is due.</p>
          </div>
        </div>
        <button type="button" onClick={() => void load()} className="flex items-center gap-1 rounded-lg border px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
          <RefreshCw size={14} /> Refresh
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {scopes.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setScope(s)}
            className={`rounded-full px-4 py-1.5 text-sm ${scope === s ? "bg-slate-900 text-white" : "border bg-white text-slate-700 hover:bg-slate-50"}`}
          >
            {SCOPE_LABEL[s]}
          </button>
        ))}
        <span className="mx-1 hidden h-5 w-px bg-slate-200 sm:block" />
        {(["open", "done", "all"] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setState(s)}
            className={`rounded-full px-3 py-1.5 text-sm ${state === s ? "bg-slate-200 font-medium text-slate-900" : "text-slate-600 hover:bg-slate-100"}`}
          >
            {s === "open" ? "To do" : s === "done" ? "Done" : "All"}
          </button>
        ))}
      </div>

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by task, family or person…"
        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-slate-900"
      />

      {error && <ErrorNote message={error} />}
      {loading && <Loader2 className="animate-spin text-slate-400" />}

      {!loading && groups.length === 0 && !error && (
        <p className="rounded-2xl border bg-white p-8 text-center text-sm text-slate-500">
          {scope === "mine" ? "Nothing is waiting for you. Nice." : "No tasks here."}
        </p>
      )}

      {groups.map((g) => (
        <section key={g.label + g.at}>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{g.label}</h2>
          <ul className="divide-y overflow-hidden rounded-2xl border bg-white">
            {g.tasks.map((t) => (
              <li key={t.id}>
                <button type="button" onClick={() => setOpenId(t.id)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-slate-50">
                  <div className="min-w-0 flex-1">
                    <p className={`truncate font-medium ${t.status === "completed" ? "text-slate-400 line-through" : "text-slate-900"}`}>{t.title}</p>
                    <p className="truncate text-xs text-slate-500">
                      {t.deceased_full_name} · {t.case_number}
                    </p>
                  </div>
                  <span className={`flex items-center gap-1 text-xs ${isOverdue(t, now) ? "font-semibold text-red-600" : "text-slate-600"}`}>
                    <CalendarClock size={13} /> {whenDue(t.due_at, t.due_date)}
                    {isOverdue(t, now) ? " · overdue" : ""}
                  </span>
                  {scope !== "mine" || t.shared ? (
                    <span className="flex items-center gap-1 text-xs text-slate-500">
                      <Users size={13} />
                      {t.assignees.length ? t.assignees.map((a) => a.name.split(" ")[0]).join(", ") : "Nobody"}
                    </span>
                  ) : null}
                  <span className={`rounded-full px-2.5 py-0.5 text-xs ${STATUS_STYLE[t.status]}`}>{STATUS_LABEL[t.status]}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {openId && (
        <TaskDrawer
          taskId={openId}
          meId={user?.user_id}
          onClose={() => setOpenId(null)}
          onChanged={() => void load()}
        />
      )}
    </main>
  );
}
