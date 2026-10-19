"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ArrowLeft,
  Check,
  AtSign,
  Bell,
  BellOff,
  CalendarPlus,
  CornerUpLeft,
  Hash,
  Loader2,
  Pencil,
  Plus,
  Paperclip,
  Search,
  SendHorizontal,
  Smile,
  Trash2,
  Video,
  X,
} from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { dayKey, formatDayHeading, formatTime } from "@/lib/datetime";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { UserAvatar } from "@/components/UserAvatar";
import { Dialog, Field, inputClass } from "@/components/Dialog";
import { Banner } from "@/components/Notices";
import { AttachmentView } from "@/components/chat/AttachmentView";
import { MeetingCard } from "@/components/chat/MeetingCard";
import ScheduleDialog from "@/components/chat/ScheduleDialog";
import {
  type Attachment,
  type Conversation,
  type Message,
  type Person,
  REACTIONS,
  fileSize,
  presenceColor,
  presenceLabel,
} from "@/components/chat/types";

const LIST_POLL_MS = 6000;
const THREAD_POLL_MS = 3000;

function visible() {
  return typeof document === "undefined" || !document.hidden;
}

function PresenceDot({
  status,
  size = 10,
}: {
  status: Person["status"] | undefined;
  size?: number;
}) {
  return (
    <span
      title={presenceLabel(status)}
      className="absolute bottom-0 right-0 rounded-full ring-2 ring-[var(--fos-surface)]"
      style={{
        width: size,
        height: size,
        background: presenceColor(status),
      }}
    />
  );
}

function Avatar({
  name,
  status,
  channel,
  size = 40,
}: {
  name: string;
  status?: Person["status"];
  channel?: boolean;
  size?: number;
}) {
  if (channel) {
    return (
      <span
        className="flex shrink-0 items-center justify-center rounded-xl bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)]"
        style={{ width: size, height: size }}
      >
        <Hash size={Math.round(size * 0.45)} />
      </span>
    );
  }

  return (
    <span className="relative shrink-0">
      <UserAvatar name={name} size={size} />
      {status && <PresenceDot status={status} />}
    </span>
  );
}

/* ============================================================
   NEW CHAT / NEW CHANNEL
============================================================ */

function NewChatDialog({
  people,
  onClose,
  onOpened,
}: {
  people: Person[];
  onClose: () => void;
  onOpened: (conversation: Conversation) => void;
}) {
  const [mode, setMode] = useState<"direct" | "channel">("direct");
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const shown = people.filter((p) =>
    p.name.toLowerCase().includes(query.trim().toLowerCase())
  );

  async function open(body: Record<string, unknown>) {
    setBusy(true);
    setError("");

    try {
      const response = await api.post<Conversation>(
        "/chat/conversations",
        body
      );
      onOpened(response.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not start the chat."));
      setBusy(false);
    }
  }

  return (
    <Dialog title="New conversation" onClose={onClose}>
      <div className="space-y-4">
        <div
          role="tablist"
          className="inline-flex rounded-lg border border-[var(--fos-border)] p-1"
        >
          {(
            [
              ["direct", "Message someone"],
              ["channel", "New channel"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={mode === id}
              onClick={() => setMode(id)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                mode === id
                  ? "bg-[var(--fos-primary)] text-[var(--fos-on-primary)]"
                  : "text-[var(--fos-text-secondary)]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === "channel" && (
          <Field label="Channel name">
            <input
              className={inputClass}
              value={name}
              maxLength={120}
              placeholder="e.g. Mortuary team, Drivers, Front office"
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
        )}

        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fos-text-muted)]"
          />
          <input
            className={`${inputClass} pl-9`}
            placeholder="Search colleagues"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <ul className="max-h-64 divide-y divide-[var(--fos-border)] overflow-y-auto rounded-lg border border-[var(--fos-border)]">
          {shown.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-[var(--fos-text-muted)]">
              No colleagues found.
            </li>
          )}
          {shown.map((person) => {
            const on = picked.includes(person.id);

            return (
              <li key={person.id}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    mode === "direct"
                      ? open({ kind: "direct", user_id: person.id })
                      : setPicked((p) =>
                          on
                            ? p.filter((id) => id !== person.id)
                            : [...p, person.id]
                        )
                  }
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-[var(--fos-surface-muted)]"
                >
                  <Avatar
                    name={person.name}
                    status={person.status}
                    size={34}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-[var(--fos-text)]">
                      {person.name}
                    </span>
                    <span className="block truncate text-xs text-[var(--fos-text-muted)]">
                      {person.job_title || person.role.replace("_", " ")}
                    </span>
                  </span>
                  {mode === "channel" && on && (
                    <Check
                      size={18}
                      className="text-[var(--fos-primary)]"
                    />
                  )}
                </button>
              </li>
            );
          })}
        </ul>

        {error && (
          <Banner tone="error" onDismiss={() => setError("")}>
            {error}
          </Banner>
        )}
      </div>

      {mode === "channel" && (
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--fos-border)] px-4 py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy || !name.trim()}
            onClick={() =>
              open({
                kind: "channel",
                name: name.trim(),
                user_ids: picked,
              })
            }
            className="rounded-lg bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-[var(--fos-on-primary)] disabled:opacity-50"
          >
            Create channel
            {picked.length > 0 ? ` (${picked.length + 1} people)` : ""}
          </button>
        </div>
      )}
    </Dialog>
  );
}

/* ============================================================
   THREAD
============================================================ */

function Thread({
  conversation,
  me,
  people,
  onBack,
  onActivity,
}: {
  conversation: Conversation;
  me: string;
  people: Person[];
  onBack: () => void;
  onActivity: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [editing, setEditing] = useState<Message | null>(null);
  const [sending, setSending] = useState(false);
  const [files, setFiles] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [mentions, setMentions] = useState<{ id: string; name: string }[]>(
    []
  );
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [pickerFor, setPickerFor] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const stickRef = useRef(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const latestRef = useRef("");
  const id = conversation.id;

  const other = people.find((p) => p.id === conversation.other_user_id);

  const markRead = useCallback(() => {
    api.post(`/chat/conversations/${id}/read`).then(onActivity).catch(() => {});
  }, [id, onActivity]);

  const fetchLatest = useCallback(
    async (first = false) => {
      try {
        const { data } = await api.get<{
          messages: Message[];
          has_more: boolean;
        }>(`/chat/conversations/${id}/messages`, {
          params: { limit: 50 },
        });

        const newest = data.messages[data.messages.length - 1];
        const signature = data.messages
          .map(
            (m) =>
              `${m.id}${m.edited_at ?? ""}${m.deleted}${m.reactions
                .map((r) => r.emoji + r.count)
                .join("")}`
          )
          .join("|");

        if (first || signature !== latestRef.current) {
          const fresh = latestRef.current !== "" && !first;
          latestRef.current = signature;

          setMessages((current) => {
            // Keep older pages the person already scrolled back to.
            const firstId = data.messages[0]?.id;
            const older = current.filter(
              (m) =>
                firstId &&
                m.created_at < data.messages[0].created_at &&
                m.id !== firstId
            );
            return [...older, ...data.messages];
          });
          if (first) setHasMore(data.has_more);

          if (fresh && newest?.sender_id !== me) {
            markRead();
          }
        }
        setError("");
      } catch (err) {
        if (first) {
          setError(getApiErrorMessage(err, "Could not load messages."));
        }
      } finally {
        if (first) setLoading(false);
      }
    },
    [id, me, markRead]
  );

  useEffect(() => {
    latestRef.current = "";
    stickRef.current = true;
    /* eslint-disable react-hooks/set-state-in-effect */
    setMessages([]);
    setLoading(true);
    setReplyTo(null);
    setEditing(null);
    setDraft("");
    setFiles([]);
    setMentions([]);
    setMentionQuery(null);
    /* eslint-enable react-hooks/set-state-in-effect */
    fetchLatest(true).then(markRead);

    const timer = window.setInterval(() => {
      if (visible()) fetchLatest();
    }, THREAD_POLL_MS);

    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    const down = () => {
      if (stickRef.current) {
        bottomRef.current?.scrollIntoView({ block: "end" });
      }
    };

    down();
    // Cards and pictures finish loading a moment later and grow the page.
    const timer = window.setTimeout(down, 400);

    return () => window.clearTimeout(timer);
  }, [messages]);

  async function loadOlder() {
    const oldest = messages[0];
    if (!oldest) return;

    const box = scrollRef.current;
    const before = box?.scrollHeight ?? 0;

    const { data } = await api.get<{
      messages: Message[];
      has_more: boolean;
    }>(`/chat/conversations/${id}/messages`, {
      params: { limit: 50, before: oldest.created_at },
    });

    stickRef.current = false;
    setMessages((current) => [...data.messages, ...current]);
    setHasMore(data.has_more);

    requestAnimationFrame(() => {
      if (box) box.scrollTop = box.scrollHeight - before;
    });
  }

  async function send() {
    const body = draft.trim();
    if ((!body && files.length === 0) || sending || uploading) return;

    setSending(true);
    setError("");

    try {
      if (editing) {
        const { data } = await api.patch<Message>(
          `/chat/messages/${editing.id}`,
          { body }
        );
        setMessages((m) => m.map((x) => (x.id === data.id ? data : x)));
        latestRef.current = "";
      } else {
        const { data } = await api.post<Message>(
          `/chat/conversations/${id}/messages`,
          {
            body,
            reply_to_id: replyTo?.id ?? null,
            mention_ids: mentions
              .filter((m) => body.includes(`@${m.name}`))
              .map((m) => m.id),
            attachment_ids: files.map((f) => f.id),
          }
        );
        stickRef.current = true;
        setMessages((m) =>
          m.some((x) => x.id === data.id) ? m : [...m, data]
        );
        latestRef.current = "";
      }

      setDraft("");
      setFiles([]);
      setMentions([]);
      setReplyTo(null);
      setEditing(null);
      onActivity();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not send that."));
    } finally {
      setSending(false);
    }
  }

  async function remove(message: Message) {
    try {
      await api.delete(`/chat/messages/${message.id}`);
      setMessages((m) =>
        m.map((x) =>
          x.id === message.id ? { ...x, deleted: true, body: "" } : x
        )
      );
      latestRef.current = "";
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not delete that."));
    }
  }

  async function attach(list: FileList | null) {
    if (!list || list.length === 0) return;
    setUploading(true);
    setError("");

    try {
      for (const file of Array.from(list)) {
        if (files.length >= 5) break;
        const form = new FormData();
        form.append("file", file);
        const { data } = await api.post<Attachment>(
          `/chat/conversations/${id}/attachments`,
          form
        );
        setFiles((cur) => [...cur, data]);
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not upload that file."));
    } finally {
      setUploading(false);
    }
  }

  async function react(message: Message, emoji: string) {
    setPickerFor(null);
    try {
      const { data } = await api.post(
        `/chat/messages/${message.id}/reactions`,
        { emoji }
      );
      setMessages((cur) =>
        cur.map((x) => (x.id === message.id ? { ...x, reactions: data } : x))
      );
      latestRef.current = "";
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not react."));
    }
  }

  async function startCall() {
    try {
      const { data } = await api.post<{ join_url: string }>(
        "/meetings/huddle",
        { conversation_id: id }
      );
      window.open(data.join_url, "_blank", "noopener,noreferrer");
      stickRef.current = true;
      latestRef.current = "";
      fetchLatest();
      onActivity();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not start the call."));
    }
  }

  function onDraftChange(value: string) {
    setDraft(value);
    const match = /(?:^|\s)@([^\s@]{0,30})$/.exec(value);
    setMentionQuery(match ? match[1].toLowerCase() : null);
  }

  function pickMention(person: { id: string; name: string }) {
    setDraft((d) => d.replace(/@([^\s@]{0,30})$/, `@${person.name} `));
    setMentions((cur) =>
      cur.some((m) => m.id === person.id) ? cur : [...cur, person]
    );
    setMentionQuery(null);

    requestAnimationFrame(() => {
      const box = inputRef.current;
      if (box) {
        box.focus();
        box.setSelectionRange(box.value.length, box.value.length);
      }
    });
  }

  const mentionable = conversation.participants.filter(
    (p) =>
      p.id !== me &&
      mentionQuery !== null &&
      p.name.toLowerCase().includes(mentionQuery)
  );

  const byId = useMemo(
    () => new Map(messages.map((m) => [m.id, m])),
    [messages]
  );

  const rows = useMemo(() => {
    const out: React.ReactNode[] = [];
    let lastDay = "";
    let prev: Message | null = null;

    for (const m of messages) {
      const day = dayKey(m.created_at);

      if (day !== lastDay) {
        out.push(
          <div
            key={`d-${day}`}
            className="my-4 flex items-center gap-3 text-xs text-[var(--fos-text-muted)]"
          >
            <span className="h-px flex-1 bg-[var(--fos-border)]" />
            {formatDayHeading(day)}
            <span className="h-px flex-1 bg-[var(--fos-border)]" />
          </div>
        );
        lastDay = day;
        prev = null;
      }

      if (m.kind === "system") {
        out.push(
          <p
            key={m.id}
            className="my-2 text-center text-xs text-[var(--fos-text-muted)]"
          >
            {m.sender_name} {m.body}
          </p>
        );
        prev = null;
        continue;
      }

      if (m.kind === "meeting" || m.kind === "call") {
        const meetingId = (m.meta?.meeting_id as string | undefined) ?? null;
        const joinUrl = (m.meta?.join_url as string | undefined) ?? null;

        out.push(
          <div
            key={m.id}
            className="my-4 flex flex-col items-center gap-2"
          >
            <p className="text-xs text-[var(--fos-text-muted)]">
              {m.sender_name} {m.body} · {formatTime(m.created_at)}
            </p>
            {meetingId ? (
              <MeetingCard meetingId={meetingId} />
            ) : (
              <div className="flex w-72 items-center gap-3 rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500 text-white">
                  <Video size={20} />
                </span>
                <span className="min-w-0 flex-1 text-sm font-semibold text-[var(--fos-text)]">
                  Call in progress
                </span>
                {joinUrl && (
                  <a
                    href={joinUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-lg bg-[var(--fos-primary)] px-3 py-1.5 text-sm font-semibold text-[var(--fos-on-primary)]"
                  >
                    Join
                  </a>
                )}
              </div>
            )}
          </div>
        );
        prev = null;
        continue;
      }

      const mine = m.sender_id === me;
      const grouped =
        prev !== null &&
        prev.sender_id === m.sender_id &&
        new Date(m.created_at).getTime() -
          new Date(prev.created_at).getTime() <
          5 * 60 * 1000;
      const parent = m.reply_to_id ? byId.get(m.reply_to_id) : undefined;

      out.push(
        <div
          key={m.id}
          className={`group flex gap-3 px-1 ${
            grouped ? "mt-0.5" : "mt-4"
          } ${mine ? "flex-row-reverse" : ""}`}
        >
          <div className="w-9 shrink-0">
            {!grouped && !mine && (
              <UserAvatar name={m.sender_name} size={36} />
            )}
          </div>

          <div
            className={`flex max-w-[78%] flex-col ${
              mine ? "items-end" : "items-start"
            }`}
          >
            {!grouped && (
              <p className="mb-1 text-xs text-[var(--fos-text-muted)]">
                {!mine && (
                  <span className="mr-2 font-semibold text-[var(--fos-text-secondary)]">
                    {m.sender_name}
                  </span>
                )}
                {formatTime(m.created_at)}
              </p>
            )}

            <div className="relative flex items-center gap-1">
              {mine && !m.deleted && (
                <Actions
                  onReply={() => setReplyTo(m)}
                  onReact={() =>
                    setPickerFor((cur) => (cur === m.id ? null : m.id))
                  }
                  onEdit={
                    m.body
                      ? () => {
                          setEditing(m);
                          setReplyTo(null);
                          setDraft(m.body);
                        }
                      : undefined
                  }
                  onDelete={() => remove(m)}
                />
              )}

              <div
                className={`rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                  m.deleted
                    ? "border border-dashed border-[var(--fos-border)] italic text-[var(--fos-text-muted)]"
                    : mine
                      ? "rounded-br-md bg-[var(--fos-primary)] text-[var(--fos-on-primary)]"
                      : "rounded-bl-md bg-[var(--fos-surface-muted)] text-[var(--fos-text)]"
                } ${
                  !m.deleted && m.mention_ids.includes(me)
                    ? "ring-2 ring-amber-400"
                    : ""
                }`}
              >
                {parent && !m.deleted && (
                  <p className="mb-1.5 line-clamp-2 border-l-2 border-current/40 pl-2 text-xs opacity-75">
                    <span className="font-semibold">
                      {parent.sender_name}
                    </span>
                    : {parent.deleted ? "Message deleted" : parent.body}
                  </p>
                )}
                {m.attachments.length > 0 && (
                  <div className="mb-1 flex flex-col gap-2">
                    {m.attachments.map((f) => (
                      <AttachmentView key={f.id} file={f} />
                    ))}
                  </div>
                )}
                {(m.deleted || m.body) && (
                  <span className="whitespace-pre-wrap break-words">
                    {m.deleted
                      ? "This message was deleted"
                      : withMentions(m.body, conversation.participants)}
                  </span>
                )}
                {m.edited_at && !m.deleted && (
                  <span className="ml-2 text-[10px] opacity-60">
                    edited
                  </span>
                )}
              </div>

              {!mine && !m.deleted && (
                <Actions
                  onReply={() => setReplyTo(m)}
                  onReact={() =>
                    setPickerFor((cur) => (cur === m.id ? null : m.id))
                  }
                />
              )}

              {pickerFor === m.id && (
                <div
                  className={`absolute -top-11 z-10 flex gap-1 rounded-full border border-[var(--fos-border)] bg-[var(--fos-surface)] px-2 py-1 shadow-lg ${
                    mine ? "right-0" : "left-0"
                  }`}
                >
                  {REACTIONS.map((emoji) => (
                    <button
                      key={emoji}
                      type="button"
                      onClick={() => react(m, emoji)}
                      className="rounded-full px-1 text-lg transition hover:scale-125"
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {m.reactions.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {m.reactions.map((r) => (
                  <button
                    key={r.emoji}
                    type="button"
                    onClick={() => react(m, r.emoji)}
                    className={`rounded-full border px-2 py-0.5 text-xs ${
                      r.mine
                        ? "border-[var(--fos-primary)] bg-[var(--fos-surface-muted)] font-semibold"
                        : "border-[var(--fos-border)] bg-[var(--fos-surface)]"
                    }`}
                  >
                    {r.emoji} {r.count}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      );
      prev = m;
    }

    return out;
  }, [messages, me, byId, pickerFor, conversation.participants]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-3 border-b border-[var(--fos-border)] px-4 py-3">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to conversations"
          className="rounded-lg p-1.5 text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)] md:hidden"
        >
          <ArrowLeft size={20} />
        </button>
        <Avatar
          name={conversation.title}
          status={other?.status}
          channel={conversation.kind === "channel"}
        />
        <div className="min-w-0">
          <h2 className="truncate font-semibold text-[var(--fos-text)]">
            {conversation.title}
          </h2>
          <p className="truncate text-xs text-[var(--fos-text-muted)]">
            {conversation.kind === "channel"
              ? `${conversation.participants.length} members`
              : other
                ? `${presenceLabel(other.status)}${
                    other.job_title ? ` · ${other.job_title}` : ""
                  }`
                : ""}
          </p>
        </div>
        <div className="ml-auto flex gap-1">
          <button
            type="button"
            onClick={startCall}
            aria-label="Start a call"
            title="Start a call"
            className="rounded-lg p-2 text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
          >
            <Video size={20} />
          </button>
          <button
            type="button"
            onClick={() => setScheduling(true)}
            aria-label="Schedule a meeting"
            title="Schedule a meeting"
            className="rounded-lg p-2 text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
          >
            <CalendarPlus size={20} />
          </button>
        </div>
      </header>

      <div
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          stickRef.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="min-h-0 flex-1 overflow-y-auto px-4 py-2"
      >
        {loading ? (
          <div className="flex justify-center py-12 text-[var(--fos-text-muted)]">
            <Loader2 className="animate-spin" size={20} />
          </div>
        ) : (
          <>
            {hasMore && (
              <div className="py-2 text-center">
                <button
                  type="button"
                  onClick={loadOlder}
                  className="text-xs font-medium text-[var(--fos-primary)] hover:underline"
                >
                  Show earlier messages
                </button>
              </div>
            )}
            {messages.length === 0 && (
              <p className="py-16 text-center text-sm text-[var(--fos-text-muted)]">
                No messages yet. Say hello.
              </p>
            )}
            {rows}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <div className="px-4 pb-2">
          <Banner tone="error" onDismiss={() => setError("")}>
            {error}
          </Banner>
        </div>
      )}

      <div className="border-t border-[var(--fos-border)] p-3">
        {(replyTo || editing) && (
          <div className="mb-2 flex items-center gap-2 rounded-lg bg-[var(--fos-surface-muted)] px-3 py-2 text-xs text-[var(--fos-text-secondary)]">
            {editing ? <Pencil size={14} /> : <CornerUpLeft size={14} />}
            <span className="min-w-0 flex-1 truncate">
              {editing
                ? "Editing your message"
                : `Replying to ${replyTo?.sender_name}: ${replyTo?.body}`}
            </span>
            <button
              type="button"
              aria-label="Cancel"
              onClick={() => {
                setReplyTo(null);
                setEditing(null);
                setDraft("");
              }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        {files.length > 0 && (
          <ul className="mb-2 flex flex-wrap gap-2">
            {files.map((f) => (
              <li
                key={f.id}
                className="flex items-center gap-2 rounded-lg bg-[var(--fos-surface-muted)] px-2.5 py-1.5 text-xs text-[var(--fos-text-secondary)]"
              >
                <Paperclip size={13} />
                <span className="max-w-40 truncate">{f.filename}</span>
                <span className="opacity-60">{fileSize(f.size_bytes)}</span>
                <button
                  type="button"
                  aria-label={`Remove ${f.filename}`}
                  onClick={() =>
                    setFiles((cur) => cur.filter((x) => x.id !== f.id))
                  }
                >
                  <X size={13} />
                </button>
              </li>
            ))}
          </ul>
        )}

        {mentionQuery !== null && mentionable.length > 0 && (
          <ul className="mb-2 max-h-40 overflow-y-auto rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-lg">
            {mentionable.slice(0, 6).map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => pickMention(p)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--fos-surface-muted)]"
                >
                  <AtSign size={14} className="text-[var(--fos-text-muted)]" />
                  {p.name}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex items-end gap-2">
          <label
            title="Attach a file"
            className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-xl text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
          >
            {uploading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Paperclip size={18} />
            )}
            <input
              type="file"
              multiple
              className="sr-only"
              aria-label="Attach a file"
              disabled={uploading || files.length >= 5 || !!editing}
              onChange={(e) => {
                attach(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
          <textarea
            ref={inputRef}
            rows={1}
            value={draft}
            maxLength={4000}
            placeholder={`Message ${conversation.title}`}
            onChange={(e) => onDraftChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none focus:border-[var(--fos-primary)]"
          />
          <button
            type="button"
            onClick={send}
            disabled={
              (!draft.trim() && files.length === 0) || sending || uploading
            }
            aria-label="Send"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--fos-primary)] text-[var(--fos-on-primary)] transition hover:opacity-90 disabled:opacity-40"
          >
            {sending ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <SendHorizontal size={18} />
            )}
          </button>
        </div>
        <p className="mt-1 hidden text-[11px] text-[var(--fos-text-muted)] md:block">
          Enter to send · Shift+Enter for a new line · @ to mention
        </p>
      </div>

      {scheduling && (
        <ScheduleDialog
          people={people}
          conversationId={conversation.id}
          conversationTitle={conversation.title}
          onClose={() => setScheduling(false)}
          onCreated={() => {
            setScheduling(false);
            stickRef.current = true;
            latestRef.current = "";
            fetchLatest();
            onActivity();
          }}
        />
      )}
    </div>
  );
}

/** Message text with @Name marked where it names someone in the chat. */
function withMentions(
  text: string,
  people: { id: string; name: string }[]
): React.ReactNode {
  const names = people
    .map((p) => p.name)
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

  if (names.length === 0 || !text.includes("@")) return text;

  const escaped = names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(@(?:${escaped.join("|")}))`, "g");

  return text.split(pattern).map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="rounded bg-amber-300/30 px-0.5">
        {part}
      </strong>
    ) : (
      part
    )
  );
}

function Actions({
  onReply,
  onReact,
  onEdit,
  onDelete,
}: {
  onReply: () => void;
  onReact?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  const base =
    "rounded-md p-1.5 text-[var(--fos-text-muted)] hover:bg-[var(--fos-surface-muted)] hover:text-[var(--fos-text)]";

  return (
    <span className="flex opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
      <button type="button" aria-label="Reply" onClick={onReply} className={base}>
        <CornerUpLeft size={14} />
      </button>
      {onReact && (
        <button type="button" aria-label="React" onClick={onReact} className={base}>
          <Smile size={14} />
        </button>
      )}
      {onEdit && (
        <button type="button" aria-label="Edit" onClick={onEdit} className={base}>
          <Pencil size={14} />
        </button>
      )}
      {onDelete && (
        <button type="button" aria-label="Delete" onClick={onDelete} className={base}>
          <Trash2 size={14} />
        </button>
      )}
    </span>
  );
}

/* ============================================================
   PANEL
============================================================ */

export default function ChatPanel() {
  const { user } = useCurrentUser();
  const me = user?.user_id ?? "";

  const [conversations, setConversations] = useState<Conversation[] | null>(
    null
  );
  const [people, setPeople] = useState<Person[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showList, setShowList] = useState(true);
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const [notify, setNotify] = useState<
    "on" | "off" | "unsupported" | "unknown"
  >("unknown");

  useEffect(() => {
    // Browser support is only known after the page has loaded.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNotify(
      !("Notification" in window)
        ? "unsupported"
        : Notification.permission === "granted"
          ? "on"
          : "off"
    );
  }, []);
  const seenUnread = useRef<Map<string, number> | null>(null);

  const loadConversations = useCallback(async () => {
    try {
      const { data } = await api.get<Conversation[]>("/chat/conversations");

      // Desktop alert when something new arrives and the tab is hidden.
      const before = seenUnread.current;
      const next = new Map(data.map((c) => [c.id, c.unread]));
      if (
        before &&
        typeof window !== "undefined" &&
        "Notification" in window &&
        Notification.permission === "granted" &&
        document.hidden
      ) {
        for (const c of data) {
          if (c.unread > (before.get(c.id) ?? 0) && c.last_message) {
            new Notification(c.title, {
              body: `${c.last_message.sender_name}: ${c.last_message.body}`,
              tag: c.id,
            });
          }
        }
      }
      seenUnread.current = next;

      setConversations(data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load your chats."));
      setConversations((c) => c ?? []);
    }
  }, []);

  const loadPeople = useCallback(async () => {
    try {
      const { data } = await api.get<Person[]>("/chat/people");
      setPeople(data);
    } catch {
      /* the list still works without presence */
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadConversations();
    loadPeople();

    const timer = window.setInterval(() => {
      if (visible()) {
        loadConversations();
        loadPeople();
      }
    }, LIST_POLL_MS);

    return () => window.clearInterval(timer);
  }, [loadConversations, loadPeople]);

  const active = conversations?.find((c) => c.id === activeId) ?? null;
  const personById = useMemo(
    () => new Map(people.map((p) => [p.id, p])),
    [people]
  );

  const filtered = (conversations ?? []).filter((c) =>
    c.title.toLowerCase().includes(query.trim().toLowerCase())
  );
  const totalUnread = (conversations ?? []).reduce(
    (sum, c) => sum + c.unread,
    0
  );

  async function toggleNotifications() {
    if (notify === "unsupported" || notify === "unknown") return;
    if (Notification.permission === "default") {
      const result = await Notification.requestPermission();
      setNotify(result === "granted" ? "on" : "off");
      return;
    }
    if (Notification.permission === "denied") {
      setError(
        "Notifications are blocked. Allow them for this site in your browser settings."
      );
      return;
    }
    setNotify("on");
  }

  function select(id: string) {
    setActiveId(id);
    setShowList(false);
  }

  return (
    <div className="flex h-[calc(100vh-11rem)] min-h-[480px] overflow-hidden rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-sm">
      {/* LIST */}
      <aside
        className={`${
          showList ? "flex" : "hidden"
        } w-full flex-col border-r border-[var(--fos-border)] md:flex md:w-80 md:shrink-0`}
      >
        <div className="flex items-center gap-2 p-3">
          <div className="relative flex-1">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fos-text-muted)]"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search chats"
              className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] py-2 pl-9 pr-3 text-sm text-[var(--fos-text)] outline-none focus:border-[var(--fos-primary)]"
            />
          </div>
          {(notify === "on" || notify === "off") && (
            <button
              type="button"
              onClick={toggleNotifications}
              aria-label={
                notify === "on"
                  ? "Desktop alerts are on"
                  : "Turn on desktop alerts"
              }
              title={
                notify === "on"
                  ? "Desktop alerts are on"
                  : "Turn on desktop alerts"
              }
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--fos-border)] text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
            >
              {notify === "on" ? <Bell size={16} /> : <BellOff size={16} />}
            </button>
          )}
          <button
            type="button"
            onClick={() => setCreating(true)}
            aria-label="New conversation"
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--fos-primary)] text-[var(--fos-on-primary)] hover:opacity-90"
          >
            <Plus size={18} />
          </button>
        </div>

        {totalUnread > 0 && (
          <p className="px-4 pb-1 text-xs font-medium text-[var(--fos-primary)]">
            {totalUnread} unread
          </p>
        )}

        <ul className="min-h-0 flex-1 overflow-y-auto">
          {conversations === null && (
            <li className="flex justify-center py-10 text-[var(--fos-text-muted)]">
              <Loader2 className="animate-spin" size={18} />
            </li>
          )}

          {conversations !== null && filtered.length === 0 && (
            <li className="px-5 py-10 text-center text-sm text-[var(--fos-text-muted)]">
              {conversations.length === 0
                ? "No chats yet. Press + to message a colleague or start a channel."
                : "No chats match."}
            </li>
          )}

          {filtered.map((c) => {
            const person = c.other_user_id
              ? personById.get(c.other_user_id)
              : undefined;

            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => select(c.id)}
                  className={`flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-[var(--fos-surface-muted)] ${
                    c.id === activeId
                      ? "bg-[var(--fos-surface-muted)]"
                      : ""
                  }`}
                >
                  <Avatar
                    name={c.title}
                    status={person?.status}
                    channel={c.kind === "channel"}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-2">
                      <span
                        className={`truncate text-sm ${
                          c.unread
                            ? "font-bold text-[var(--fos-text)]"
                            : "font-medium text-[var(--fos-text)]"
                        }`}
                      >
                        {c.title}
                      </span>
                      {c.last_message && (
                        <span className="shrink-0 text-[11px] text-[var(--fos-text-muted)]">
                          {formatTime(c.last_message.created_at)}
                        </span>
                      )}
                    </span>
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs text-[var(--fos-text-muted)]">
                        {c.last_message
                          ? `${
                              c.last_message.sender_name.split(" ")[0]
                            }: ${c.last_message.body}`
                          : "No messages yet"}
                      </span>
                      {c.mentioned && (
                        <span
                          title="You were mentioned"
                          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-400 text-[11px] font-bold text-black"
                        >
                          @
                        </span>
                      )}
                      {c.unread > 0 && (
                        <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-[var(--fos-primary)] px-1.5 text-[11px] font-bold text-[var(--fos-on-primary)]">
                          {c.unread > 99 ? "99+" : c.unread}
                        </span>
                      )}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>

        {error && (
          <div className="p-3">
            <Banner tone="error" onDismiss={() => setError("")}>
              {error}
            </Banner>
          </div>
        )}
      </aside>

      {/* THREAD */}
      <section
        className={`${
          showList ? "hidden" : "flex"
        } min-w-0 flex-1 flex-col md:flex`}
      >
        {active && me ? (
          <Thread
            key={active.id}
            conversation={active}
            me={me}
            people={people}
            onBack={() => setShowList(true)}
            onActivity={loadConversations}
          />
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--fos-surface-muted)] text-[var(--fos-text-muted)]">
              <Hash size={26} />
            </span>
            <p className="font-semibold text-[var(--fos-text)]">
              Pick a chat
            </p>
            <p className="max-w-xs text-sm text-[var(--fos-text-muted)]">
              Message a colleague or open a channel to keep the whole team
              in one place.
            </p>
          </div>
        )}
      </section>

      {creating && (
        <NewChatDialog
          people={people}
          onClose={() => setCreating(false)}
          onOpened={(conversation) => {
            setCreating(false);
            setConversations((list) =>
              list && !list.some((c) => c.id === conversation.id)
                ? [conversation, ...list]
                : list
            );
            select(conversation.id);
            loadConversations();
          }}
        />
      )}
    </div>
  );
}
