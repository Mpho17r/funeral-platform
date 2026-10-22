"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AtSign,
  Bell,
  CalendarClock,
  CheckCheck,
  ClipboardCheck,
  ListTodo,
  Scale,
} from "lucide-react";

import api from "@/lib/api";

type Note = {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  created_at: string;
  read: boolean;
};

const POLL_MS = 30_000;

const ICONS: Record<string, React.ReactNode> = {
  task_assigned: <ListTodo size={16} />,
  meeting_invite: <CalendarClock size={16} />,
  meeting_changed: <CalendarClock size={16} />,
  mention: <AtSign size={16} />,
  claim_submitted: <ClipboardCheck size={16} />,
  reconciliation_difference: <Scale size={16} />,
};

function ago(value: string) {
  const seconds = Math.max(
    0,
    Math.round((Date.now() - new Date(value).getTime()) / 1000),
  );
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

/** The bell in the top bar: unread count and a short inbox. */
export function NotificationBell() {
  const router = useRouter();
  const box = useRef<HTMLDivElement>(null);

  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<Note[]>([]);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await api.get<{ unread: number; items: Note[] }>(
        "/notifications",
        { params: { limit: 15 } },
      );
      setUnread(response.data.unread);
      setItems(response.data.items);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  // Check now, then every 30 seconds while the tab is showing.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") load();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!open) return;

    function onDown(event: MouseEvent) {
      if (box.current && !box.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function openNote(note: Note) {
    setOpen(false);
    if (!note.read) {
      setItems((list) =>
        list.map((n) => (n.id === note.id ? { ...n, read: true } : n)),
      );
      setUnread((count) => Math.max(0, count - 1));
      api.post(`/notifications/${note.id}/read`).catch(() => {});
    }
    if (note.link) router.push(note.link);
  }

  async function readAll() {
    setItems((list) => list.map((n) => ({ ...n, read: true })));
    setUnread(0);
    try {
      await api.post("/notifications/read-all");
    } catch {
      load();
    }
  }

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-label={
          unread > 0 ? `Notifications, ${unread} unread` : "Notifications"
        }
        aria-expanded={open}
        onClick={() => {
          setOpen((current) => !current);
          if (!open) load();
        }}
        className="relative flex h-10 w-10 items-center justify-center rounded-lg text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
      >
        <Bell size={20} />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex min-w-[18px] items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold leading-[18px] text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute -right-[3.25rem] top-12 z-[300] sm:right-0 w-[min(92vw,24rem)] overflow-hidden rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-2xl"
        >
          <div className="flex items-center justify-between border-b border-[var(--fos-border)] px-4 py-3">
            <h2 className="text-sm font-semibold text-[var(--fos-text)]">
              Notifications
            </h2>
            {unread > 0 && (
              <button
                type="button"
                onClick={readAll}
                className="flex items-center gap-1 text-xs font-medium text-[var(--fos-primary)] hover:underline"
              >
                <CheckCheck size={14} /> Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[70vh] overflow-y-auto">
            {failed && items.length === 0 && (
              <p className="p-5 text-sm text-red-600">
                Could not load notifications just now.
              </p>
            )}
            {!failed && items.length === 0 && (
              <p className="p-5 text-sm text-[var(--fos-text-muted)]">
                You are all caught up.
              </p>
            )}

            {items.map((note) => (
              <button
                key={note.id}
                type="button"
                onClick={() => openNote(note)}
                className="flex w-full items-start gap-3 border-b border-[var(--fos-border)] px-4 py-3 text-left last:border-0 hover:bg-[var(--fos-surface-muted)]"
              >
                <span
                  className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    note.read
                      ? "bg-[var(--fos-surface-muted)] text-[var(--fos-text-muted)]"
                      : "bg-[var(--fos-primary)] text-[var(--fos-on-primary)]"
                  }`}
                >
                  {ICONS[note.kind] ?? <Bell size={16} />}
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className={`block text-sm text-[var(--fos-text)] ${
                      note.read ? "" : "font-semibold"
                    }`}
                  >
                    {note.title}
                  </span>
                  {note.body && (
                    <span className="mt-0.5 block truncate text-xs text-[var(--fos-text-muted)]">
                      {note.body}
                    </span>
                  )}
                  <span className="mt-0.5 block text-xs text-[var(--fos-text-muted)]">
                    {ago(note.created_at)}
                  </span>
                </span>
                {!note.read && (
                  <span
                    aria-hidden="true"
                    className="mt-2 h-2 w-2 shrink-0 rounded-full bg-red-600"
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
