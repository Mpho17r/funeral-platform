"use client";

import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { CalendarClock, MapPin, MessageSquare, Plus, User } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

import api from "@/lib/api";
import { categoryLabel, getApiErrorMessage, statusOf } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Appointment = {
  id: string;
  title: string;
  start_at: string;
  end_at: string;
  status: "scheduled" | "confirmed" | "completed" | "cancelled" | "no_show";
  customer_id: string | null;
  customer_name: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  who: string | null;
  who_phone: string | null;
  who_email: string | null;
  location: string | null;
  notes: string | null;
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  cancel_reason: string | null;
};

type Listing = { items: Appointment[]; reminders_on: boolean; email_ready: boolean };
type Person = { id: string; full_name: string | null };
type CustomerOption = { id: string; name: string };

const TONE: Record<string, string> = {
  scheduled: "bg-slate-100 text-slate-700",
  confirmed: "bg-emerald-100 text-emerald-800",
  completed: "bg-sky-100 text-sky-800",
  cancelled: "bg-slate-200 text-slate-500 line-through",
  no_show: "bg-amber-100 text-amber-800",
};

const LIVE = new Set(["scheduled", "confirmed"]);

const timeOf = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit", hour12: false });

const dayOf = (iso: string) =>
  new Date(iso).toLocaleDateString("en-ZA", { weekday: "long", day: "numeric", month: "long" });

const dayKey = (iso: string) => new Date(iso).toLocaleDateString("en-CA");

/** "2026-11-05T09:30" for a datetime-local box, in the browser's own time. */
function localInput(date: Date) {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}T${p(date.getHours())}:${p(date.getMinutes())}`;
}

function AppointmentsInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { can } = useCurrentUser();
  const manage = can("appointments.manage");
  const canMessage = can("outbox.manage");

  const [data, setData] = useState<Listing | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [scope, setScope] = useState<"upcoming" | "all">("upcoming");
  const [mine, setMine] = useState(false);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Appointment | "new" | null>(null);
  const [cancelling, setCancelling] = useState<Appointment | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const prefillCustomer = params.get("customer");

  const load = useCallback(async () => {
    try {
      const r = await api.get<Listing>("/appointments", {
        params: {
          upcoming: scope === "upcoming" || undefined,
          mine: mine || undefined,
          status: status || undefined,
          q: search.trim() || undefined,
        },
      });
      setData(r.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load appointments."));
    }
  }, [scope, mine, status, search]);

  useEffect(() => {
    const t = setTimeout(() => void load(), 200);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    if (!manage) return;
    api.get<Person[]>("/users").then((r) => setPeople(r.data)).catch(() => undefined);
    api
      .get<{ items: CustomerOption[] }>("/customers")
      .then((r) => setCustomers(r.data.items))
      .catch(() => undefined); // roles without customer access can still type a contact
  }, [manage]);

  useEffect(() => {
    if (prefillCustomer && manage) setEditing("new");
  }, [prefillCustomer, manage]);

  async function act(a: Appointment, action: string) {
    try {
      setError("");
      await api.post(`/appointments/${a.id}/${action}`, {});
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not work."));
    }
  }

  async function message(a: Appointment, kind: string) {
    try {
      setError("");
      const r = await api.post<{ status: string; channel: string }>(
        `/appointments/${a.id}/message`,
        { kind },
      );
      setNote(
        r.data.status === "sent"
          ? "Sent."
          : "Ready in Messages. Open it there to send it.",
      );
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not prepare the message."));
    }
  }

  async function toggleReminders(on: boolean) {
    try {
      await api.put("/appointments/settings/reminders", { appointment_reminders: on });
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not change reminders."));
    }
  }

  const groups = new Map<string, Appointment[]>();
  for (const a of data?.items ?? []) {
    const key = dayKey(a.start_at);
    groups.set(key, [...(groups.get(key) ?? []), a]);
  }

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-[var(--fos-primary)] p-3 text-[var(--fos-on-primary)]">
            <CalendarClock size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Appointments</h1>
            <p className="text-sm text-slate-500">Book customers in, and keep them informed.</p>
          </div>
        </div>
        {manage && (
          <button
            type="button"
            onClick={() => setEditing("new")}
            className="flex items-center gap-2 rounded-lg bg-[var(--fos-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)]"
          >
            <Plus size={16} /> Book appointment
          </button>
        )}
      </header>

      {error && <ErrorNote message={error} />}
      {note && (
        <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800" role="status">
          {note}
        </p>
      )}

      <section className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex overflow-hidden rounded-lg border border-slate-300 text-sm">
          {(["upcoming", "all"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setScope(s)}
              className={`px-3 py-1.5 ${scope === s ? "bg-[var(--fos-primary)] text-[var(--fos-on-primary)]" : "bg-white text-slate-700"}`}
            >
              {s === "upcoming" ? "Upcoming" : "All"}
            </button>
          ))}
        </div>
        <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {Object.keys(TONE).map((s) => (
            <option key={s} value={s}>
              {categoryLabel(s)}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Only mine
        </label>
        <input
          className="min-w-40 flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          placeholder="Search title, person or place"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </section>

      {manage && data && (
        <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={data.reminders_on}
            onChange={(e) => void toggleReminders(e.target.checked)}
          />
          <span>
            <span className="font-semibold">Remind customers the day before</span>
            <span className="block text-slate-500">
              A reminder is prepared in Messages for every booking in the next 24 hours.{" "}
              {data.email_ready
                ? "Emails go out by themselves."
                : "Email is not set up, so you send each one yourself (WhatsApp, SMS or email)."}
            </span>
          </span>
        </label>
      )}

      {!data ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          <CalendarClock className="mx-auto mb-2" />
          {scope === "upcoming" ? "Nothing booked from now on." : "No appointments match."}
        </div>
      ) : (
        [...groups.entries()].map(([key, rows]) => (
          <section key={key} className="space-y-2">
            <h2 className="text-sm font-semibold text-slate-600">{dayOf(rows[0].start_at)}</h2>
            {rows.map((a) => (
              <article key={a.id} className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold">
                      {timeOf(a.start_at)}–{timeOf(a.end_at)} · {a.title}
                    </p>
                    <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
                      {a.who && (
                        <span className="flex items-center gap-1">
                          <User size={14} /> {a.who}
                        </span>
                      )}
                      {a.assigned_user_name && <span>With {a.assigned_user_name}</span>}
                      {a.location && (
                        <span className="flex items-center gap-1">
                          <MapPin size={14} /> {a.location}
                        </span>
                      )}
                    </p>
                    {a.notes && <p className="mt-1 text-sm text-slate-500">{a.notes}</p>}
                    {a.cancel_reason && <p className="mt-1 text-sm text-slate-500">Cancelled: {a.cancel_reason}</p>}
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${TONE[a.status]}`}>
                    {categoryLabel(a.status)}
                  </span>
                </div>

                {manage && LIVE.has(a.status) && (
                  <div className="mt-3 flex flex-wrap gap-2 text-sm">
                    {a.status === "scheduled" && (
                      <button type="button" className="rounded-lg border border-slate-300 px-3 py-1.5" onClick={() => void act(a, "confirm")}>
                        Confirm
                      </button>
                    )}
                    <button type="button" className="rounded-lg border border-slate-300 px-3 py-1.5" onClick={() => void act(a, "complete")}>
                      Done
                    </button>
                    <button type="button" className="rounded-lg border border-slate-300 px-3 py-1.5" onClick={() => void act(a, "no-show")}>
                      No-show
                    </button>
                    <button type="button" className="rounded-lg border border-slate-300 px-3 py-1.5" onClick={() => setEditing(a)}>
                      Change
                    </button>
                    {canMessage && (a.who_phone || a.who_email) && (
                      <button
                        type="button"
                        className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5"
                        onClick={() => void message(a, "appointment_confirmation")}
                      >
                        <MessageSquare size={14} /> Tell them
                      </button>
                    )}
                    <button type="button" className="rounded-lg border border-red-200 px-3 py-1.5 text-red-700" onClick={() => setCancelling(a)}>
                      Cancel
                    </button>
                  </div>
                )}
              </article>
            ))}
          </section>
        ))
      )}

      {canMessage && (
        <p className="text-xs text-slate-500">
          Messages to customers wait in{" "}
          <button type="button" className="underline" onClick={() => router.push("/messages")}>
            Messages
          </button>
          .
        </p>
      )}

      {editing && (
        <BookDialog
          existing={editing === "new" ? null : editing}
          people={people}
          customers={customers}
          presetCustomer={editing === "new" ? prefillCustomer : null}
          onClose={() => {
            setEditing(null);
            if (prefillCustomer) router.replace("/appointments");
          }}
          onSaved={() => {
            setEditing(null);
            if (prefillCustomer) router.replace("/appointments");
            void load();
          }}
        />
      )}
      {cancelling && (
        <CancelDialog
          appointment={cancelling}
          onClose={() => setCancelling(null)}
          onSaved={() => {
            setCancelling(null);
            void load();
          }}
        />
      )}
    </main>
  );
}

export default function AppointmentsPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-500">Loading…</p>}>
      <AppointmentsInner />
    </Suspense>
  );
}

function BookDialog({
  existing,
  people,
  customers,
  presetCustomer,
  onClose,
  onSaved,
}: {
  existing: Appointment | null;
  people: Person[];
  customers: CustomerOption[];
  presetCustomer: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const start0 = existing ? new Date(existing.start_at) : new Date(Date.now() + 3600_000);
  if (!existing) start0.setMinutes(0, 0, 0);
  const minutes0 = existing
    ? Math.round((new Date(existing.end_at).getTime() - new Date(existing.start_at).getTime()) / 60000)
    : 60;

  const [title, setTitle] = useState(existing?.title ?? "");
  const [start, setStart] = useState(localInput(start0));
  const [minutes, setMinutes] = useState(String(minutes0));
  const [customerId, setCustomerId] = useState(existing?.customer_id ?? presetCustomer ?? "");
  const [name, setName] = useState(existing?.contact_name ?? "");
  const [phone, setPhone] = useState(existing?.contact_phone ?? "");
  const [email, setEmail] = useState(existing?.contact_email ?? "");
  const [place, setPlace] = useState(existing?.location ?? "");
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [who, setWho] = useState(existing?.assigned_user_id ?? "");
  const [tell, setTell] = useState(false);
  const [clash, setClash] = useState("");
  const [allowClash, setAllowClash] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setError("");
      const startAt = new Date(start).toISOString();
      const endAt = new Date(new Date(start).getTime() + Number(minutes || 60) * 60000).toISOString();
      const body = {
        title: title.trim(),
        start_at: startAt,
        end_at: endAt,
        customer_id: customerId || null,
        contact_name: name.trim() || null,
        contact_phone: phone.trim() || null,
        contact_email: email.trim() || null,
        location: place.trim() || null,
        notes: notes.trim() || null,
        assigned_user_id: who || null,
        allow_clash: allowClash,
      };
      if (existing) {
        await api.patch(`/appointments/${existing.id}`, body);
      } else {
        await api.post("/appointments", {
          ...body,
          duration_minutes: Number(minutes || 60),
          send_confirmation: tell,
        });
      }
      onSaved();
    } catch (err) {
      const message = getApiErrorMessage(err, "Could not save the appointment.");
      if (statusOf(err) === 409) {
        setClash(message);
      } else {
        setError(message);
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={existing ? "Change appointment" : "Book appointment"} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        {clash && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" role="alert">
            <p>{clash}</p>
            <label className="mt-2 flex items-center gap-2">
              <input type="checkbox" checked={allowClash} onChange={(e) => setAllowClash(e.target.checked)} />
              Book it anyway
            </label>
          </div>
        )}
        <input className={inputClass} placeholder="What is it for? (e.g. Quote visit)" required value={title} onChange={(e) => setTitle(e.target.value)} />
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-slate-500">
            Starts
            <input type="datetime-local" className={inputClass} required value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="text-xs text-slate-500">
            Minutes
            <input type="number" min={5} max={1440} step={5} className={inputClass} value={minutes} onChange={(e) => setMinutes(e.target.value)} />
          </label>
        </div>
        <select className={inputClass} value={who} onChange={(e) => setWho(e.target.value)}>
          <option value="">Nobody in particular</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.full_name}
            </option>
          ))}
        </select>
        {customers.length > 0 && (
          <select className={inputClass} value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">Not one of my saved customers</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
        {!customerId && (
          <div className="grid gap-3 sm:grid-cols-3">
            <input className={inputClass} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
            <input className={inputClass} placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <input className={inputClass} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        )}
        <input className={inputClass} placeholder="Where (optional)" value={place} onChange={(e) => setPlace(e.target.value)} />
        <textarea className={inputClass} rows={2} placeholder="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        {!existing && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={tell} onChange={(e) => setTell(e.target.checked)} />
            Prepare a confirmation message for them
          </label>
        )}
        <DialogFooter onClose={onClose} saving={saving} submitLabel={existing ? "Save" : "Book"} />
      </form>
    </Dialog>
  );
}

function CancelDialog({
  appointment,
  onClose,
  onSaved,
}: {
  appointment: Appointment;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      await api.post(`/appointments/${appointment.id}/cancel`, { reason });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not cancel."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Cancel “${appointment.title}”`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <textarea className={inputClass} rows={3} required placeholder="Why is it cancelled?" value={reason} onChange={(e) => setReason(e.target.value)} />
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Cancel appointment" danger />
      </form>
    </Dialog>
  );
}
