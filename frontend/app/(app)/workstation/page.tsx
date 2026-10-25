"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  CalendarDays,
  ClipboardList,
  Coffee,
  FileText,
  Loader2,
  LogIn,
  LogOut,
  MessageSquare,
  Phone,
  Upload,
  Users,
} from "lucide-react";
import api from "@/lib/api";
import { useCurrentUser } from "@/components/CurrentUserProvider";

type AttendanceMe = {
  attendance: { checked_in_at: string; status: string } | null;
  current_break: { break_type: "tea" | "lunch"; started_at: string } | null;
  break_expires_at: string | null;
  presence: string;
};

type PresenceRow = {
  user_id: string;
  user_name: string;
  role: string;
  status: string;
  last_seen_at: string | null;
};

const statusStyle: Record<string, { dot: string; label: string }> = {
  online: { dot: "bg-emerald-500", label: "Online" },
  checked_in: { dot: "bg-emerald-500", label: "Online" },
  away: { dot: "bg-amber-400", label: "Away" },
  busy: { dot: "bg-red-500", label: "Busy" },
  offline: { dot: "bg-slate-400", label: "Offline" },
};

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

export default function WorkstationPage() {
  const { user } = useCurrentUser();
  const [attendance, setAttendance] = useState<AttendanceMe | null>(null);
  const [people, setPeople] = useState<PresenceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [attendanceResponse, peopleResponse] = await Promise.all([
        api.get<AttendanceMe>("/attendance/me"),
        api.get<PresenceRow[]>("/presence"),
      ]);
      setAttendance(attendanceResponse.data);
      setPeople(peopleResponse.data);
      setError("");
    } catch {
      setError("Some workstation information could not be loaded. You can still use the links below.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function shiftAction(kind: "check-in" | "check-out" | "start-tea" | "start-lunch" | "end-break") {
    setAction(kind);
    setError("");
    try {
      if (kind === "check-in") await api.post("/attendance/check-in");
      if (kind === "check-out") await api.post("/attendance/check-out");
      if (kind === "start-tea") await api.post("/attendance/breaks/start", { break_type: "tea" });
      if (kind === "start-lunch") await api.post("/attendance/breaks/start", { break_type: "lunch" });
      if (kind === "end-break") await api.post("/attendance/breaks/end");
      await load();
    } catch (caught) {
      const detail = (caught as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
      setError(typeof detail === "string" ? detail : "We couldn't update your shift. Please try again.");
    } finally {
      setAction("");
    }
  }

  const onShift = Boolean(attendance?.attendance);
  const onBreak = Boolean(attendance?.current_break);
  const shiftLabel = !onShift
    ? "Not checked in"
    : onBreak
      ? attendance?.current_break?.break_type === "tea" ? "On tea break" : "On lunch break"
      : "On shift";

  const card = "rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)]";
  const linkAction = "flex min-h-20 flex-col items-start justify-between rounded-xl border border-[var(--fos-border)] bg-[var(--fos-page)] p-3 text-sm font-medium text-[var(--fos-text)] transition hover:border-[var(--fos-primary)] hover:bg-[var(--fos-surface-muted)]";

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--fos-text-muted)]">Personal workspace</p>
        <h1 className="mt-1 font-display text-3xl font-semibold text-[var(--fos-text)] sm:text-4xl">My workstation</h1>
        <p className="mt-2 text-sm text-[var(--fos-text-muted)]">Your shift, team and everyday actions in one place.</p>
      </header>

      {error && <div role="alert" className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</div>}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(13rem,0.8fr)_minmax(0,1.25fr)_minmax(14rem,0.85fr)]">
        <div className="space-y-5">
          <section className="overflow-hidden rounded-2xl p-5 text-white shadow-sm" style={{ background: "linear-gradient(135deg, #173d30, #244a3b 65%, #535537)" }}>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/65">Shift</p>
            <h2 className="mt-3 font-display text-3xl">{loading ? "Loading…" : shiftLabel}</h2>
            <p className="mt-1 text-sm text-white/70">
              {attendance?.attendance?.checked_in_at
                ? `Started ${new Date(attendance.attendance.checked_in_at).toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit", hour12: false })}`
                : "Your shift controls are ready when you are."}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {!onShift ? (
                <button type="button" disabled={Boolean(action) || loading} onClick={() => void shiftAction("check-in")} className="inline-flex items-center gap-2 rounded-xl bg-amber-300 px-3 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-60">
                  {action === "check-in" ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />} Clock in
                </button>
              ) : onBreak ? (
                <button type="button" disabled={Boolean(action)} onClick={() => void shiftAction("end-break")} className="inline-flex items-center gap-2 rounded-xl bg-amber-300 px-3 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-60">
                  {action === "end-break" ? <Loader2 size={15} className="animate-spin" /> : <Coffee size={15} />} End break
                </button>
              ) : (
                <>
                  <button type="button" disabled={Boolean(action)} onClick={() => void shiftAction("start-tea")} className="inline-flex items-center gap-2 rounded-xl bg-white/15 px-3 py-2.5 text-sm font-medium hover:bg-white/25 disabled:opacity-60"><Coffee size={15} /> Tea break</button>
                  <button type="button" disabled={Boolean(action)} onClick={() => void shiftAction("start-lunch")} className="inline-flex items-center gap-2 rounded-xl bg-white/15 px-3 py-2.5 text-sm font-medium hover:bg-white/25 disabled:opacity-60"><CalendarDays size={15} /> Lunch</button>
                  <button type="button" disabled={Boolean(action)} onClick={() => void shiftAction("check-out")} className="inline-flex items-center gap-2 rounded-xl bg-white/15 px-3 py-2.5 text-sm font-medium hover:bg-white/25 disabled:opacity-60"><LogOut size={15} /> Clock out</button>
                </>
              )}
            </div>
          </section>

          <section className={`${card} p-4`}>
            <h2 className="mb-3 font-display text-xl font-semibold">Quick actions</h2>
            <div className="grid grid-cols-2 gap-2.5">
              <Link href="/cases" className={linkAction}><FileText size={18} className="text-[var(--fos-secondary)]" />New case</Link>
              <Link href="/communications" className={linkAction}><Phone size={18} className="text-[var(--fos-secondary)]" />Log a call</Link>
              <Link href="/staff" className={linkAction}><MessageSquare size={18} className="text-[var(--fos-secondary)]" />Message team</Link>
              <Link href="/cases" className={linkAction}><Upload size={18} className="text-[var(--fos-secondary)]" />Upload document</Link>
            </div>
          </section>
        </div>

        <section className={`${card} overflow-hidden`}>
          <div className="flex items-center justify-between border-b border-[var(--fos-border)] px-5 py-4">
            <h2 className="font-display text-xl font-semibold">Your day</h2>
            <Link href="/calendar" className="text-sm text-[var(--fos-text-muted)] hover:text-[var(--fos-text)]">Open calendar ↗</Link>
          </div>
          <div className="p-5">
            <div className="flex items-start gap-3 rounded-xl bg-[var(--fos-page)] p-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--fos-surface)] text-[var(--fos-secondary)]"><CalendarDays size={19} /></span>
              <div>
                <p className="font-medium text-[var(--fos-text)]">Meetings and scheduled activities</p>
                <p className="mt-1 text-sm leading-5 text-[var(--fos-text-muted)]">See your branch calendar for upcoming meetings, appointments and funeral arrangements.</p>
                <Link href="/calendar" className="mt-3 inline-flex text-sm font-semibold text-[var(--fos-text)] underline underline-offset-4">View calendar</Link>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Link href="/tasks" className="rounded-xl border border-[var(--fos-border)] p-4 transition hover:bg-[var(--fos-page)]">
                <ClipboardList size={19} className="text-[var(--fos-secondary)]" />
                <p className="mt-2 font-medium">My tasks</p>
                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">Review assigned work and follow-ups.</p>
              </Link>
              <Link href="/groups" className="rounded-xl border border-[var(--fos-border)] p-4 transition hover:bg-[var(--fos-page)]">
                <Users size={19} className="text-[var(--fos-secondary)]" />
                <p className="mt-2 font-medium">Team groups</p>
                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">Open your branch and department groups.</p>
              </Link>
            </div>
          </div>
        </section>

        <div className="space-y-5">
          <section className={`${card} overflow-hidden`}>
            <div className="flex items-center justify-between border-b border-[var(--fos-border)] px-4 py-4">
              <h2 className="font-display text-xl font-semibold">People</h2>
              <span className="text-xs text-[var(--fos-text-muted)]">{people.length}</span>
            </div>
            <div className="p-4">
              {people.length ? (
                <ul className="space-y-3">
                  {people.map((person) => {
                    const status = statusStyle[person.status] ?? statusStyle.offline;
                    return <li key={person.user_id} className="flex items-center gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--fos-surface-muted)] text-xs font-semibold text-[var(--fos-text)]">{initials(person.user_name)}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-[var(--fos-text)]">{person.user_name}{person.user_id === user?.user_id ? " (you)" : ""}</span>
                        <span className="block truncate text-xs text-[var(--fos-text-muted)]">{person.role.replaceAll("_", " ")}</span>
                      </span>
                      <span title={status.label} className={`h-2.5 w-2.5 shrink-0 rounded-full ${status.dot}`} />
                    </li>;
                  })}
                </ul>
              ) : <p className="text-sm text-[var(--fos-text-muted)]">Staff availability will appear here when presence data is available.</p>}
              <button type="button" onClick={() => void load()} className="mt-4 text-sm font-medium text-[var(--fos-text-muted)] hover:text-[var(--fos-text)]">Refresh people</button>
            </div>
          </section>

          <section className={`${card} overflow-hidden`}>
            <div className="border-b border-[var(--fos-border)] px-4 py-4"><h2 className="font-display text-xl font-semibold">Team chat</h2></div>
            <div className="p-4">
              <p className="text-sm leading-5 text-[var(--fos-text-muted)]">Continue conversations with your colleagues and branch groups.</p>
              <Link href="/staff" className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[var(--fos-border)] px-3 py-2 text-sm font-medium hover:bg-[var(--fos-page)]"><MessageSquare size={16} />Open team chat</Link>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
