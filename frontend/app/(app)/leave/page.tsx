"use client";

import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { CalendarOff, Plus } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

import api from "@/lib/api";
import { categoryLabel, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Leave = {
  id: string;
  user_id: string;
  user_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string | null;
  status: "pending" | "approved" | "rejected" | "cancelled";
  decision_note: string | null;
};

type Mine = {
  balance: { year: number; entitlement: number; taken: number; pending: number; remaining: number };
  types: string[];
  items: Leave[];
};

type Team = { leave_days_per_year: number; off_today: string[]; items: Leave[] };

const TONE: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
  cancelled: "bg-slate-200 text-slate-600",
};

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const range = (l: Leave) =>
  l.start_date === l.end_date ? l.start_date : `${l.start_date} → ${l.end_date}`;

function LeaveInner() {
  const router = useRouter();
  const tab = useSearchParams().get("tab") === "team" ? "team" : "mine";
  const { can } = useCurrentUser();
  const manage = can("leave.manage");

  const [mine, setMine] = useState<Mine | null>(null);
  const [team, setTeam] = useState<Team | null>(null);
  const [asking, setAsking] = useState(false);
  const [rejecting, setRejecting] = useState<Leave | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const m = await api.get<Mine>("/leave/mine");
      setMine(m.data);
      if (manage) {
        const t = await api.get<Team>("/leave/team");
        setTeam(t.data);
      }
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load leave."));
    }
  }, [manage]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(path: string, body?: object) {
    try {
      setError("");
      await api.post(path, body ?? {});
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not work."));
    }
  }

  const pending = (team?.items ?? []).filter((l) => l.status === "pending");

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <CalendarOff size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Leave</h1>
            <p className="text-sm text-slate-500">Ask for time off and see who is away.</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setAsking(true)}
          className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"
        >
          <Plus size={16} /> Ask for leave
        </button>
      </header>

      {manage && (
        <div className="flex gap-2 border-b">
          {[
            ["mine", "My leave"],
            ["team", `Team${pending.length ? ` (${pending.length} waiting)` : ""}`],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => router.push(key === "team" ? "/leave?tab=team" : "/leave")}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                tab === key ? "border-slate-900" : "border-transparent text-slate-500"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {error && <ErrorNote message={error} />}

      {tab === "mine" && mine && (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            <Card label={`Yearly allowance ${mine.balance.year}`} value={`${mine.balance.entitlement} days`} />
            <Card label="Taken" value={`${mine.balance.taken}`} />
            <Card label="Waiting for approval" value={`${mine.balance.pending}`} />
            <Card label="Left" value={`${mine.balance.remaining}`} strong />
          </div>
          <List
            items={mine.items}
            empty="You have not asked for any leave yet."
            action={(l) =>
              (l.status === "pending" || l.status === "approved") && l.end_date >= iso(new Date()) ? (
                <button
                  type="button"
                  onClick={() => act(`/leave/${l.id}/cancel`)}
                  className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                >
                  Cancel
                </button>
              ) : null
            }
          />
        </>
      )}

      {tab === "team" && manage && team && (
        <>
          <div className="rounded-2xl border bg-white p-4 text-sm">
            <p className="font-medium">Away today</p>
            <p className="text-slate-600">
              {team.off_today.length ? team.off_today.join(", ") : "Nobody."}
            </p>
            <AllowanceEditor value={team.leave_days_per_year} onSaved={load} />
          </div>

          {pending.length > 0 && (
            <section>
              <h2 className="mb-2 font-semibold">Waiting for you</h2>
              <List
                showName
                items={pending}
                empty=""
                action={(l) => (
                  <span className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => act(`/leave/${l.id}/approve`)}
                      className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => setRejecting(l)}
                      className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                    >
                      Reject
                    </button>
                  </span>
                )}
              />
            </section>
          )}

          <section>
            <h2 className="mb-2 font-semibold">Everyone this year</h2>
            <List showName items={team.items} empty="No leave this year." />
          </section>
        </>
      )}

      {asking && mine && (
        <AskDialog
          types={mine.types}
          remaining={mine.balance.remaining}
          onClose={() => setAsking(false)}
          onSaved={() => {
            setAsking(false);
            void load();
          }}
        />
      )}
      {rejecting && (
        <RejectDialog
          leave={rejecting}
          onClose={() => setRejecting(null)}
          onSaved={() => {
            setRejecting(null);
            void load();
          }}
        />
      )}
    </main>
  );
}

export default function LeavePage() {
  return (
    <Suspense fallback={null}>
      <LeaveInner />
    </Suspense>
  );
}

function Card({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`rounded-2xl border bg-white p-4 ${strong ? "ring-2 ring-slate-900" : ""}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-bold">{value}</p>
    </div>
  );
}

function List({
  items,
  empty,
  showName,
  action,
}: {
  items: Leave[];
  empty: string;
  showName?: boolean;
  action?: (l: Leave) => React.ReactNode;
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border bg-white">
      <table className="w-full min-w-[34rem] text-left text-sm">
        <tbody>
          {items.map((l) => (
            <tr key={l.id} className="border-t first:border-t-0">
              <td className="px-4 py-3">
                <div className="font-medium">
                  {showName ? `${l.user_name} · ` : ""}
                  {categoryLabel(l.leave_type)}
                </div>
                <div className="text-xs text-slate-500">
                  {range(l)} · {l.days} working day{l.days === 1 ? "" : "s"}
                  {l.reason ? ` · ${l.reason}` : ""}
                </div>
                {l.decision_note && <div className="text-xs text-slate-500">Note: {l.decision_note}</div>}
              </td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${TONE[l.status]}`}>
                  {categoryLabel(l.status)}
                </span>
              </td>
              <td className="px-4 py-3 text-right">{action?.(l)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && empty && (
        <p className="px-6 py-10 text-center text-sm text-slate-500">{empty}</p>
      )}
    </div>
  );
}

function AllowanceEditor({ value, onSaved }: { value: number; onSaved: () => void }) {
  const [days, setDays] = useState(String(value));
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  async function save() {
    try {
      setSaving(true);
      await api.put("/leave/settings", { leave_days_per_year: Number(days) });
      setMsg("Saved.");
      onSaved();
    } catch (err) {
      setMsg(getApiErrorMessage(err, "Could not save."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
      <span className="text-slate-600">Annual leave per person per year:</span>
      <input
        className={`${inputClass} !w-20 !py-1.5`}
        inputMode="numeric"
        value={days}
        onChange={(e) => setDays(e.target.value)}
      />
      <button
        type="button"
        disabled={saving}
        onClick={save}
        className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
      >
        Save
      </button>
      {msg && <span className="text-xs text-slate-500">{msg}</span>}
    </div>
  );
}

function AskDialog({
  types,
  remaining,
  onClose,
  onSaved,
}: {
  types: string[];
  remaining: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [type, setType] = useState("annual");
  const [from, setFrom] = useState(iso(new Date()));
  const [to, setTo] = useState(iso(new Date()));
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      await api.post("/leave", {
        leave_type: type,
        start_date: from,
        end_date: to < from ? from : to,
        reason: reason.trim() || null,
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not send the request."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Ask for leave" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
          {types.map((t) => (
            <option key={t} value={t}>
              {categoryLabel(t)}
              {t === "annual" ? ` (${remaining} days left)` : ""}
            </option>
          ))}
        </select>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-slate-500">
            First day
            <input
              type="date"
              className={inputClass}
              value={from}
              onChange={(e) => {
                setFrom(e.target.value);
                if (to < e.target.value) setTo(e.target.value);
              }}
            />
          </label>
          <label className="text-xs text-slate-500">
            Last day
            <input type="date" className={inputClass} value={to} min={from} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
        <textarea
          className={inputClass}
          rows={2}
          placeholder="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <p className="text-xs text-slate-500">Weekends are not counted. Sick leave can be asked for after the fact.</p>
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Send request" />
      </form>
    </Dialog>
  );
}

function RejectDialog({
  leave,
  onClose,
  onSaved,
}: {
  leave: Leave;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!note.trim()) return setError("Say why, so they know.");
    try {
      setSaving(true);
      await api.post(`/leave/${leave.id}/reject`, { note: note.trim() });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not reject."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Reject ${leave.user_name}'s leave`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <textarea className={inputClass} rows={3} placeholder="Reason" value={note} onChange={(e) => setNote(e.target.value)} />
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Reject" danger />
      </form>
    </Dialog>
  );
}
