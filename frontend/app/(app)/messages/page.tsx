"use client";

import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { Mail, MessageSquare, Plus, Send } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

import api from "@/lib/api";
import { categoryLabel, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Message = {
  id: string;
  customer_id: string | null;
  customer_name: string | null;
  appointment_id: string | null;
  recipient_name: string | null;
  kind: string;
  channel: "whatsapp" | "sms" | "email";
  recipient: string;
  subject: string | null;
  body: string;
  status: "queued" | "sent" | "cancelled";
  created_at: string;
  sent_at: string | null;
  delivered_by: string | null;
  delivery_error: string | null;
  cancel_reason: string | null;
  link: string | null;
};

type Listing = { items: Message[]; waiting: number; email_ready: boolean };
type Template = { key: string; label: string; subject: string; body: string };
type CustomerOption = { id: string; name: string; phone?: string | null; email?: string | null };

const TONE: Record<string, string> = {
  queued: "bg-amber-100 text-amber-800",
  sent: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-slate-200 text-slate-500",
};

const CHANNEL: Record<string, string> = { whatsapp: "WhatsApp", sms: "SMS", email: "Email" };

const stamp = (iso: string) =>
  new Date(iso).toLocaleString("en-ZA", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });

function MessagesInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { can } = useCurrentUser();
  const manage = can("outbox.manage");

  const [data, setData] = useState<Listing | null>(null);
  const [tab, setTab] = useState<"waiting" | "all">("waiting");
  const [channel, setChannel] = useState("");
  const [composing, setComposing] = useState(false);
  const [cancelling, setCancelling] = useState<Message | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const customerFilter = params.get("customer");

  const load = useCallback(async () => {
    try {
      const r = await api.get<Listing>("/outbox", {
        params: {
          status: tab === "waiting" ? "queued" : undefined,
          channel: channel || undefined,
          customer_id: customerFilter || undefined,
        },
      });
      setData(r.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load messages."));
    }
  }, [tab, channel, customerFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (params.get("new") && manage) setComposing(true);
  }, [params, manage]);

  async function act(m: Message, action: "send-email" | "mark-sent") {
    try {
      setBusy(m.id);
      setError("");
      await api.post(`/outbox/${m.id}/${action}`, {});
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not work."));
      await load();
    } finally {
      setBusy("");
    }
  }

  function closeCompose() {
    setComposing(false);
    if (params.get("new")) router.replace(customerFilter ? `/messages?customer=${customerFilter}` : "/messages");
  }

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-[var(--fos-primary)] p-3 text-[var(--fos-on-primary)]">
            <MessageSquare size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Messages</h1>
            <p className="text-sm text-slate-500">What you send to customers, and what is waiting to go.</p>
          </div>
        </div>
        {manage && (
          <button
            type="button"
            onClick={() => setComposing(true)}
            className="flex items-center gap-2 rounded-lg bg-[var(--fos-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)]"
          >
            <Plus size={16} /> New message
          </button>
        )}
      </header>

      {error && <ErrorNote message={error} />}

      {data && !data.email_ready && (
        <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
          Email sending is not set up on this server, so emails wait here for you to send. WhatsApp and SMS always open
          on your phone or computer to send. Your administrator can switch email on in the server settings.
        </p>
      )}

      <section className="flex flex-wrap items-center gap-3">
        <div className="flex overflow-hidden rounded-lg border border-slate-300 text-sm">
          {(["waiting", "all"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 ${tab === t ? "bg-[var(--fos-primary)] text-[var(--fos-on-primary)]" : "bg-white text-slate-700"}`}
            >
              {t === "waiting" ? `Waiting${data ? ` (${data.waiting})` : ""}` : "Everything"}
            </button>
          ))}
        </div>
        <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="">Any channel</option>
          {Object.entries(CHANNEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        {customerFilter && (
          <button type="button" className="text-sm underline" onClick={() => router.replace("/messages")}>
            Showing one customer. Show everyone
          </button>
        )}
      </section>

      {!data ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          <Mail className="mx-auto mb-2" />
          {tab === "waiting" ? "Nothing is waiting to be sent." : "No messages yet."}
        </div>
      ) : (
        data.items.map((m) => (
          <article key={m.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-semibold">
                  {m.recipient_name || m.customer_name || m.recipient}
                  <span className="ml-2 text-sm font-normal text-slate-500">
                    {CHANNEL[m.channel]} · {m.recipient}
                  </span>
                </p>
                <p className="text-xs text-slate-500">
                  {categoryLabel(m.kind)} · {stamp(m.sent_at ?? m.created_at)}
                  {m.delivered_by ? ` · ${m.delivered_by === "system" ? "sent automatically" : "sent by hand"}` : ""}
                </p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${TONE[m.status]}`}>{categoryLabel(m.status)}</span>
            </div>
            {m.subject && <p className="mt-2 text-sm font-medium">{m.subject}</p>}
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{m.body}</p>
            {m.delivery_error && <p className="mt-2 text-sm text-red-700">Not delivered: {m.delivery_error}</p>}
            {m.cancel_reason && <p className="mt-2 text-sm text-slate-500">Cancelled: {m.cancel_reason}</p>}

            {manage && m.status === "queued" && (
              <div className="mt-3 flex flex-wrap gap-2 text-sm">
                {m.channel === "email" ? (
                  <button
                    type="button"
                    disabled={busy === m.id || !data.email_ready}
                    title={data.email_ready ? "" : "Email is not set up on this server"}
                    onClick={() => void act(m, "send-email")}
                    className="flex items-center gap-1 rounded-lg bg-[var(--fos-primary)] px-3 py-1.5 font-medium text-[var(--fos-on-primary)] disabled:opacity-50"
                  >
                    <Send size={14} /> Send email
                  </button>
                ) : (
                  m.link && (
                    <a
                      href={m.link}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 rounded-lg bg-[var(--fos-primary)] px-3 py-1.5 font-medium text-[var(--fos-on-primary)]"
                    >
                      <Send size={14} /> Open {CHANNEL[m.channel]}
                    </a>
                  )
                )}
                <button
                  type="button"
                  disabled={busy === m.id}
                  onClick={() => void act(m, "mark-sent")}
                  className="rounded-lg border border-slate-300 px-3 py-1.5"
                >
                  I have sent it
                </button>
                <button type="button" className="rounded-lg border border-red-200 px-3 py-1.5 text-red-700" onClick={() => setCancelling(m)}>
                  Cancel
                </button>
              </div>
            )}
          </article>
        ))
      )}

      {composing && (
        <ComposeDialog
          presetCustomer={customerFilter}
          emailReady={data?.email_ready ?? false}
          onClose={closeCompose}
          onSaved={() => {
            closeCompose();
            setTab("waiting");
            void load();
          }}
        />
      )}
      {cancelling && (
        <CancelDialog
          message={cancelling}
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

export default function MessagesPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-500">Loading…</p>}>
      <MessagesInner />
    </Suspense>
  );
}

function ComposeDialog({
  presetCustomer,
  emailReady,
  onClose,
  onSaved,
}: {
  presetCustomer: string | null;
  emailReady: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [customerId, setCustomerId] = useState(presetCustomer ?? "");
  const [channel, setChannel] = useState("whatsapp");
  const [name, setName] = useState("");
  const [recipient, setRecipient] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<{ items: CustomerOption[] }>("/customers")
      .then((r) => setCustomers(r.data.items))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    api
      .get<Template[]>("/outbox/templates", { params: { customer_id: customerId || undefined } })
      .then((r) => setTemplates(r.data))
      .catch(() => setTemplates([]));
  }, [customerId]);

  // Choosing a customer fills in the way to reach them.
  useEffect(() => {
    const c = customers.find((x) => x.id === customerId);
    if (!c) return;
    setName(c.name);
    setRecipient((channel === "email" ? c.email : c.phone) ?? "");
  }, [customerId, channel, customers]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setError("");
      await api.post("/outbox", {
        channel,
        body: body.trim(),
        subject: channel === "email" ? subject.trim() || null : null,
        customer_id: customerId || null,
        recipient_name: name.trim() || null,
        recipient: recipient.trim() || null,
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not prepare the message."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="New message" onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        {customers.length > 0 && (
          <select className={inputClass} value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">Someone who is not a saved customer</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
        <div className="grid gap-3 sm:grid-cols-3">
          <select className={inputClass} value={channel} onChange={(e) => setChannel(e.target.value)}>
            {Object.entries(CHANNEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <input className={inputClass} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <input
            className={inputClass}
            placeholder={channel === "email" ? "Email address" : "Phone number"}
            required
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
          />
        </div>
        {templates.length > 0 && (
          <select
            className={inputClass}
            defaultValue=""
            onChange={(e) => {
              const t = templates.find((x) => x.key === e.target.value);
              if (t) {
                setBody(t.body);
                setSubject(t.subject);
              }
            }}
          >
            <option value="">Start from a ready-made message…</option>
            {templates.map((t) => (
              <option key={t.key} value={t.key}>
                {t.label}
              </option>
            ))}
          </select>
        )}
        {channel === "email" && (
          <input className={inputClass} placeholder="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
        )}
        <textarea className={inputClass} rows={5} required maxLength={2000} placeholder="Your message" value={body} onChange={(e) => setBody(e.target.value)} />
        <p className="text-xs text-slate-500">
          {channel === "email"
            ? emailReady
              ? "Email is sent straight away."
              : "Email is not set up on this server, so it waits in Messages for you to send."
            : "It will wait in Messages with a button that opens the app ready to send."}
        </p>
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Prepare message" />
      </form>
    </Dialog>
  );
}

function CancelDialog({
  message,
  onClose,
  onSaved,
}: {
  message: Message;
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
      await api.post(`/outbox/${message.id}/cancel`, { reason });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not cancel."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Cancel this message" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <textarea className={inputClass} rows={3} required placeholder="Why is it not being sent?" value={reason} onChange={(e) => setReason(e.target.value)} />
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Cancel message" danger />
      </form>
    </Dialog>
  );
}
