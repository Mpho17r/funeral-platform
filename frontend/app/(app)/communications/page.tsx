"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  ExternalLink,
  Loader2,
  MessageSquare,
  Pencil,
  Search,
  Settings2,
  UserCog,
  X,
} from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { useBranches } from "@/lib/branches";
import {
  CHANNELS,
  CHANNEL_LABELS,
  KIND_HELP,
  KIND_LABELS,
  KIND_STYLE,
  SKIP_REASON,
  formatRecipient,
  formatWhen,
  openLabel,
  type Channel,
  type CommunicationMessage,
  type MessageList,
  type MessageStatus,
  type ReminderGenerateResult,
  type ReminderKind,
  type ReminderPlan,
  type Template,
  type TemplateList,
} from "@/lib/communications";
import { ALL_BRANCHES, BranchFilter } from "@/components/BranchControls";
import { ContactPreferencesDialog } from "@/components/ContactPreferencesDialog";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";
import AutoRemindersToggle from "@/components/AutoRemindersToggle";

type Tab = MessageStatus | "wording";

type MemberOption = {
  id: string;
  member_number: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
};

const PAGE_SIZE = 50;

const TABS: { value: Tab; label: string }[] = [
  { value: "queued", label: "To send" },
  { value: "sent", label: "Sent" },
  { value: "cancelled", label: "Cancelled" },
  { value: "wording", label: "Wording" },
];

export default function CommunicationsPage() {
  const { branches, multiple } = useBranches();

  const [tab, setTab] = useState<Tab>("queued");
  const [branch, setBranch] = useState(ALL_BRANCHES);

  const [list, setList] = useState<MessageList | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [finding, setFinding] = useState(false);
  const [writing, setWriting] = useState(false);
  const [cancelling, setCancelling] =
    useState<CommunicationMessage | null>(null);
  const [contactFor, setContactFor] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [busyId, setBusyId] = useState("");

  const branchParams = useMemo(
    () => (branch !== ALL_BRANCHES ? { branch_id: branch } : {}),
    [branch],
  );

  const loadMessages = useCallback(async () => {
    if (tab === "wording") {
      return;
    }

    try {
      setError("");

      const response = await api.get<MessageList>(
        "/communications/messages",
        {
          params: {
            status: tab,
            limit: PAGE_SIZE,
            ...branchParams,
          },
        },
      );

      setList(response.data);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not load the messages."),
      );
    } finally {
      setLoading(false);
    }
  }, [tab, branchParams]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMessages();
  }, [loadMessages]);

  async function showMore() {
    if (!list) {
      return;
    }

    try {
      setLoadingMore(true);

      const response = await api.get<MessageList>(
        "/communications/messages",
        {
          params: {
            status: tab,
            limit: PAGE_SIZE,
            offset: list.items.length,
            ...branchParams,
          },
        },
      );

      setList({
        ...response.data,
        items: [...list.items, ...response.data.items],
      });
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not load more messages."),
      );
    } finally {
      setLoadingMore(false);
    }
  }

  function changeTab(next: Tab) {
    if (next !== tab) {
      setLoading(next !== "wording");
      setList(null);
      setTab(next);
    }
  }

  async function deliverNow(message: CommunicationMessage) {
    try {
      setBusyId(message.id);
      setError("");
      await api.post(`/communications/messages/${message.id}/deliver`);
      setNotice(`Email sent to ${message.member_name ?? "the member"}.`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not send the email."));
    } finally {
      setBusyId("");
      await loadMessages();
    }
  }

  async function markSent(message: CommunicationMessage) {
    try {
      setBusyId(message.id);
      setError("");

      await api.post(`/communications/messages/${message.id}/mark-sent`);

      setNotice(`Marked as sent to ${message.member_name ?? "the member"}.`);
      await loadMessages();
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not mark the message as sent."),
      );
    } finally {
      setBusyId("");
    }
  }

  const counts = list?.counts;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reminders</h1>
          <p className="text-sm text-slate-500">
            Payment and membership reminders. Check each one, send it
            from WhatsApp, SMS or email, then mark it sent.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {multiple && (
            <BranchFilter
              branches={branches}
              value={branch}
              onChange={(value) => {
                setLoading(true);
                setBranch(value);
              }}
            />
          )}

          <button
            type="button"
            onClick={() => setWriting(true)}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Write a message
          </button>

          <button
            type="button"
            onClick={() => setFinding(true)}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
          >
            <Search size={16} />
            Find reminders
          </button>
        </div>
      </div>

      <AutoRemindersToggle />

      {notice && (
        <Banner tone="success" onDismiss={() => setNotice("")}>
          {notice}
        </Banner>
      )}

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      <div
        role="tablist"
        className="flex flex-wrap gap-1 border-b border-slate-200"
      >
        {TABS.map(({ value, label }) => {
          const count =
            value !== "wording" && counts ? counts[value] : null;

          return (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => changeTab(value)}
              className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium ${
                tab === value
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {label}
              {count !== null && (
                <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {tab === "wording" ? (
        <WordingTab onError={setError} onNotice={setNotice} />
      ) : (
        <>
          {loading && (
            <p className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 size={16} className="animate-spin" /> Loading…
            </p>
          )}

          {list && list.items.length === 0 && !loading && (
            <EmptyState tab={tab} onFind={() => setFinding(true)} />
          )}

          {list && list.items.length > 0 && (
            <ul className="space-y-3">
              {list.items.map((message) => (
                <MessageRow
                  key={message.id}
                  message={message}
                  busy={busyId === message.id}
                  onMarkSent={() => markSent(message)}
                  onDeliver={() => deliverNow(message)}
                  onCancel={() => setCancelling(message)}
                  onContact={() =>
                    setContactFor({
                      id: message.member_id,
                      name: message.member_name ?? "Member",
                    })
                  }
                />
              ))}
            </ul>
          )}

          {list && list.items.length < list.total && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={showMore}
                disabled={loadingMore}
                className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                {loadingMore && (
                  <Loader2 size={16} className="animate-spin" />
                )}
                Show more ({list.total - list.items.length} left)
              </button>
            </div>
          )}
        </>
      )}

      {finding && (
        <FindRemindersDialog
          branchParams={branchParams}
          onClose={() => setFinding(false)}
          onQueued={async (created) => {
            setFinding(false);
            setNotice(
              created === 1
                ? "1 reminder is ready to send."
                : `${created} reminders are ready to send.`,
            );
            setTab("queued");
            setLoading(true);
            await loadMessages();
          }}
        />
      )}

      {writing && (
        <WriteMessageDialog
          onClose={() => setWriting(false)}
          onCreated={async () => {
            setWriting(false);
            setNotice("The message is ready to send.");
            setTab("queued");
            setLoading(true);
            await loadMessages();
          }}
        />
      )}

      {cancelling && (
        <CancelDialog
          message={cancelling}
          onClose={() => setCancelling(null)}
          onCancelled={async () => {
            setCancelling(null);
            setNotice("The message was cancelled.");
            await loadMessages();
          }}
        />
      )}

      {contactFor && (
        <ContactPreferencesDialog
          memberId={contactFor.id}
          memberName={contactFor.name}
          onClose={() => setContactFor(null)}
          onSaved={() => setNotice("Contact preferences saved.")}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------
// A message in the list
// ------------------------------------------------------------

function MessageRow({
  message,
  busy,
  onMarkSent,
  onDeliver,
  onCancel,
  onContact,
}: {
  message: CommunicationMessage;
  busy: boolean;
  onMarkSent: () => void;
  onDeliver: () => void;
  onCancel: () => void;
  onContact: () => void;
}) {
  return (
    <li className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${KIND_STYLE[message.kind]}`}
            >
              {KIND_LABELS[message.kind]}
            </span>

            <p className="font-semibold text-slate-900">
              {message.member_name ?? "Member"}
            </p>

            {message.membership_number && (
              <span className="text-sm text-slate-500">
                · {message.membership_number}
              </span>
            )}
          </div>

          <p className="mt-1 text-sm text-slate-500">
            {CHANNEL_LABELS[message.channel]} ·{" "}
            {formatRecipient(message)}
          </p>
        </div>

        <p className="text-xs text-slate-500">
          {message.status === "sent" && message.sent_at
            ? `Sent ${formatWhen(message.sent_at)}`
            : message.status === "cancelled" && message.cancelled_at
              ? `Cancelled ${formatWhen(message.cancelled_at)}`
              : `Queued ${formatWhen(message.created_at)}`}
        </p>
      </div>

      {message.subject && message.channel === "email" && (
        <p className="text-sm font-medium text-slate-800">
          {message.subject}
        </p>
      )}

      <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
        {message.body}
      </p>

      {message.status === "queued" && message.delivery_error && (
        <p className="text-sm text-amber-700">
          Automatic sending failed ({message.delivery_attempts}{" "}
          {message.delivery_attempts === 1 ? "try" : "tries"}):{" "}
          {message.delivery_error}. You can still send it by hand.
        </p>
      )}

      {message.status === "sent" && message.delivered_by === "smtp" && (
        <p className="text-sm text-slate-500">Sent automatically by email.</p>
      )}

      {message.status === "cancelled" && message.cancel_reason && (
        <p className="text-sm text-slate-500">
          Reason: {message.cancel_reason}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {message.status === "queued" && (
          <>
            <a
              href={message.action_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              <ExternalLink size={16} />
              {openLabel(message.channel)}
            </a>

            {message.channel === "email" && (
              <button
                type="button"
                onClick={onDeliver}
                disabled={busy}
                className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
              >
                Send email now
              </button>
            )}

            <button
              type="button"
              onClick={onMarkSent}
              disabled={busy}
              className="flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2.5 text-sm font-medium text-emerald-800 hover:bg-emerald-100 disabled:opacity-60"
            >
              {busy ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Check size={16} />
              )}
              Mark sent
            </button>

            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
          </>
        )}

        <button
          type="button"
          onClick={onContact}
          className="ml-auto flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-100"
        >
          <UserCog size={16} />
          Contact preferences
        </button>
      </div>
    </li>
  );
}

function EmptyState({
  tab,
  onFind,
}: {
  tab: Tab;
  onFind: () => void;
}) {
  const text: Record<string, string> = {
    queued: "Nothing waiting to be sent.",
    sent: "No messages have been sent yet.",
    cancelled: "No messages have been cancelled.",
  };

  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center">
      <MessageSquare className="mx-auto mb-3 text-slate-400" size={28} />
      <p className="text-sm font-medium text-slate-700">{text[tab]}</p>

      {tab === "queued" && (
        <button
          type="button"
          onClick={onFind}
          className="mt-4 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
        >
          Find reminders
        </button>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Find reminders: preview, then queue
// ------------------------------------------------------------

function FindRemindersDialog({
  branchParams,
  onClose,
  onQueued,
}: {
  branchParams: { branch_id?: string };
  onClose: () => void;
  onQueued: (created: number) => void | Promise<void>;
}) {
  const [plan, setPlan] = useState<ReminderPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await api.post<ReminderPlan>(
          "/communications/reminders/preview",
          branchParams,
        );

        if (!cancelled) {
          setPlan(response.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            getApiErrorMessage(err, "Could not look for reminders."),
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [branchParams]);

  async function queue(event: FormEvent) {
    event.preventDefault();

    try {
      setSaving(true);
      setError("");

      const response = await api.post<ReminderGenerateResult>(
        "/communications/reminders/generate",
        branchParams,
      );

      await onQueued(response.data.created);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not queue the reminders."),
      );
    } finally {
      setSaving(false);
    }
  }

  const total = plan?.items.length ?? 0;

  return (
    <Dialog title="Find reminders" onClose={onClose} wide>
      <form onSubmit={queue} className="space-y-4">
        {error && <ErrorNote message={error} />}

        {loading && (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 size={16} className="animate-spin" /> Checking
            memberships…
          </p>
        )}

        {plan && (
          <>
            {plan.disabled_kinds.length > 0 && (
              <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                Switched off in Wording:{" "}
                {plan.disabled_kinds
                  .map((kind) => KIND_LABELS[kind])
                  .join(", ")}
                .
              </p>
            )}

            {total === 0 ? (
              <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-600">
                Nothing new to send right now.
                {plan.already_queued > 0 &&
                  ` ${plan.already_queued} ${
                    plan.already_queued === 1 ? "is" : "are"
                  } already queued or sent.`}
              </p>
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(plan.counts).map(([kind, count]) => (
                    <span
                      key={kind}
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${
                        KIND_STYLE[kind as ReminderKind]
                      }`}
                    >
                      {KIND_LABELS[kind as ReminderKind]}: {count}
                    </span>
                  ))}
                </div>

                <ul className="max-h-72 space-y-2 overflow-y-auto">
                  {plan.items.map((item) => (
                    <li
                      key={`${item.kind}-${item.membership_id}-${item.body.length}`}
                      className="rounded-lg border border-slate-200 p-3"
                    >
                      <p className="flex flex-wrap items-center gap-2 text-sm">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${KIND_STYLE[item.kind]}`}
                        >
                          {KIND_LABELS[item.kind]}
                        </span>
                        <span className="font-semibold text-slate-900">
                          {item.member_name}
                        </span>
                        <span className="text-slate-500">
                          · {item.membership_number} ·{" "}
                          {CHANNEL_LABELS[item.channel]}
                        </span>
                      </p>

                      <p className="mt-2 text-sm text-slate-600">
                        {item.body}
                      </p>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {plan.skipped.length > 0 && (
              <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <p className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                  <AlertTriangle size={16} />
                  {plan.skipped.length === 1
                    ? "1 member cannot be reminded"
                    : `${plan.skipped.length} members cannot be reminded`}
                </p>

                <ul className="space-y-1 text-sm text-amber-900">
                  {plan.skipped.map((item) => (
                    <li key={`${item.kind}-${item.membership_number}`}>
                      {item.member_name} · {item.membership_number} ·{" "}
                      {KIND_LABELS[item.kind]} —{" "}
                      {SKIP_REASON[item.reason]}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {total > 0 && plan.already_queued > 0 && (
              <p className="text-xs text-slate-500">
                {plan.already_queued} more were already queued or sent
                and are left out.
              </p>
            )}
          </>
        )}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          disabled={loading || total === 0}
          submitLabel={
            total === 1 ? "Queue 1 reminder" : `Queue ${total} reminders`
          }
        />
      </form>
    </Dialog>
  );
}

// ------------------------------------------------------------
// Write a one-off message
// ------------------------------------------------------------

function WriteMessageDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void | Promise<void>;
}) {
  const [members, setMembers] = useState<MemberOption[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(true);
  const [search, setSearch] = useState("");
  const [memberId, setMemberId] = useState("");
  const [channel, setChannel] = useState<Channel | "">("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await api.get<MemberOption[]>("/members");

        if (!cancelled) {
          setMembers(response.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            getApiErrorMessage(err, "Could not load the members."),
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingMembers(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  const matches = useMemo(() => {
    const term = search.trim().toLowerCase();

    if (!term) {
      return members.slice(0, 8);
    }

    return members
      .filter((member) =>
        `${member.first_name} ${member.last_name} ${member.member_number}`
          .toLowerCase()
          .includes(term),
      )
      .slice(0, 8);
  }, [members, search]);

  const chosen = members.find((member) => member.id === memberId);

  async function submit(event: FormEvent) {
    event.preventDefault();

    if (!memberId) {
      setError("Choose who the message is for.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      await api.post("/communications/messages", {
        member_id: memberId,
        channel: channel || null,
        subject: channel === "email" ? subject : null,
        body,
      });

      await onCreated();
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not create the message."),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Write a message" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <Field label="Member">
          {chosen ? (
            <div className="flex items-center justify-between rounded-lg border border-slate-300 px-4 py-3 text-sm">
              <span>
                {chosen.first_name} {chosen.last_name} ·{" "}
                {chosen.member_number}
              </span>

              <button
                type="button"
                aria-label="Choose someone else"
                onClick={() => setMemberId("")}
                className="rounded p-1 text-slate-500 hover:bg-slate-100"
              >
                <X size={16} />
              </button>
            </div>
          ) : (
            <>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by name or member number"
                className={inputClass}
              />

              {loadingMembers ? (
                <p className="mt-2 text-sm text-slate-500">Loading…</p>
              ) : (
                <ul className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200">
                  {matches.length === 0 && (
                    <li className="px-4 py-3 text-sm text-slate-500">
                      No members match.
                    </li>
                  )}

                  {matches.map((member) => (
                    <li key={member.id}>
                      <button
                        type="button"
                        onClick={() => setMemberId(member.id)}
                        className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50"
                      >
                        {member.first_name} {member.last_name}
                        <span className="text-slate-500">
                          {" "}
                          · {member.member_number}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Field>

        <Field
          label="Send by"
          hint="Leave this on automatic to use how the member likes to be contacted."
        >
          <select
            value={channel}
            onChange={(event) =>
              setChannel(event.target.value as Channel | "")
            }
            className={inputClass}
          >
            <option value="">Automatic</option>

            {CHANNELS.map((value) => (
              <option key={value} value={value}>
                {CHANNEL_LABELS[value]}
              </option>
            ))}
          </select>
        </Field>

        {channel === "email" && (
          <Field label="Subject">
            <input
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              maxLength={200}
              className={inputClass}
            />
          </Field>
        )}

        <Field label="Message">
          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={5}
            maxLength={1000}
            required
            className={inputClass}
          />
        </Field>

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Create message"
        />
      </form>
    </Dialog>
  );
}

// ------------------------------------------------------------
// Cancel a queued message
// ------------------------------------------------------------

function CancelDialog({
  message,
  onClose,
  onCancelled,
}: {
  message: CommunicationMessage;
  onClose: () => void;
  onCancelled: () => void | Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();

    try {
      setSaving(true);
      setError("");

      await api.post(`/communications/messages/${message.id}/cancel`, {
        reason,
      });

      await onCancelled();
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not cancel the message."),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Cancel this message?" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <p className="text-sm text-slate-600">
          The {KIND_LABELS[message.kind].toLowerCase()} message for{" "}
          {message.member_name ?? "this member"} will not be sent. It
          is kept in the Cancelled list, and the same reminder will
          not be queued again.
        </p>

        <Field label="Reason (optional)">
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className={inputClass}
            placeholder="For example: paid by EFT this morning"
          />
        </Field>

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Cancel message"
          danger
        />
      </form>
    </Dialog>
  );
}

// ------------------------------------------------------------
// Wording of each reminder
// ------------------------------------------------------------

function WordingTab({
  onError,
  onNotice,
}: {
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const [data, setData] = useState<TemplateList | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Template | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await api.get<TemplateList>(
        "/communications/templates",
      );

      setData(response.data);
    } catch (err) {
      onError(
        getApiErrorMessage(err, "Could not load the wording."),
      );
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </p>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">
        This is the wording used when reminders are made. Changes
        apply to reminders made from now on.
      </p>

      {data.templates.map((template) => (
        <div
          key={template.kind}
          className="space-y-2 rounded-xl border border-slate-200 bg-white p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="flex items-center gap-2 font-semibold text-slate-900">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${KIND_STYLE[template.kind]}`}
                >
                  {KIND_LABELS[template.kind]}
                </span>

                {!template.is_active && (
                  <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                    Switched off
                  </span>
                )}

                {template.is_default && (
                  <span className="text-xs font-normal text-slate-500">
                    Standard wording
                  </span>
                )}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                {KIND_HELP[template.kind]}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setEditing(template)}
              className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <Pencil size={14} />
              Edit
            </button>
          </div>

          <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
            {template.body}
          </p>
        </div>
      ))}

      {editing && (
        <TemplateDialog
          template={editing}
          placeholders={data.placeholders}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            onNotice("The wording was saved.");
            await load();
          }}
        />
      )}
    </div>
  );
}

function TemplateDialog({
  template,
  placeholders,
  onClose,
  onSaved,
}: {
  template: Template;
  placeholders: { name: string; description: string }[];
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const [subject, setSubject] = useState(template.subject);
  const [body, setBody] = useState(template.body);
  const [active, setActive] = useState(template.is_active);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();

    try {
      setSaving(true);
      setError("");

      await api.put(`/communications/templates/${template.kind}`, {
        subject,
        body,
        is_active: active,
      });

      await onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save the wording."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      title={`Wording · ${KIND_LABELS[template.kind]}`}
      onClose={onClose}
      wide
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <label className="flex items-start gap-3 rounded-lg border border-slate-200 p-3">
          <input
            type="checkbox"
            checked={active}
            onChange={(event) => setActive(event.target.checked)}
            className="mt-1"
          />
          <span>
            <span className="block text-sm font-medium text-slate-900">
              Send this kind of reminder
            </span>
            <span className="block text-xs text-slate-500">
              Switch off to stop these reminders being made at all.
            </span>
          </span>
        </label>

        <Field label="Subject" hint="Only used for email.">
          <input
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            maxLength={200}
            required
            className={inputClass}
          />
        </Field>

        <Field label="Message">
          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={6}
            maxLength={1000}
            required
            className={inputClass}
          />
        </Field>

        <div>
          <p className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
            <Settings2 size={14} />
            Add a detail (it is filled in for each member)
          </p>

          <div className="flex flex-wrap gap-2">
            {placeholders.map((placeholder) => (
              <button
                key={placeholder.name}
                type="button"
                title={placeholder.description}
                onClick={() =>
                  setBody((current) =>
                    `${current}${current.endsWith(" ") || !current ? "" : " "}{${placeholder.name}}`,
                  )
                }
                className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 hover:bg-slate-50"
              >
                {`{${placeholder.name}}`}
              </button>
            ))}
          </div>
        </div>

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Save wording"
        />
      </form>
    </Dialog>
  );
}
