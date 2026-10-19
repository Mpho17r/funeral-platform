"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CalendarClock,
  Check,
  Loader2,
  Users,
  Video,
  X,
} from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { formatDateTime, formatTime } from "@/lib/datetime";
import type { Meeting } from "@/components/chat/types";

function stateOf(m: Meeting): "live" | "soon" | "ended" | "later" {
  const now = Date.now();
  const start = new Date(m.starts_at).getTime();
  const end = new Date(m.ends_at).getTime();

  if (now > end) return "ended";
  if (now >= start) return "live";
  if (start - now < 15 * 60 * 1000) return "soon";
  return "later";
}

export function MeetingBody({
  meeting,
  onChange,
  compact = false,
}: {
  meeting: Meeting;
  onChange: (m: Meeting) => void;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const state = stateOf(meeting);
  const accepted = meeting.invitees.filter(
    (i) => i.response === "accepted"
  ).length;

  async function act(path: string, body?: object) {
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<Meeting>(
        `/meetings/${meeting.id}/${path}`,
        body
      );
      onChange(data);
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not work."));
    } finally {
      setBusy(false);
    }
  }

  const canJoin =
    meeting.join_url && !meeting.cancelled && state !== "ended";

  return (
    <div
      className={`rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] text-[var(--fos-text)] ${
        compact ? "w-72 p-3" : "p-4"
      } ${meeting.cancelled ? "opacity-60" : ""}`}
    >
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--fos-primary)] text-[var(--fos-on-primary)]">
          <CalendarClock size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <p
            className={`font-semibold ${
              meeting.cancelled ? "line-through" : ""
            }`}
          >
            {meeting.title}
          </p>
          <p className="text-xs text-[var(--fos-text-muted)]">
            {formatDateTime(meeting.starts_at)} –{" "}
            {formatTime(meeting.ends_at)}
          </p>
          {state === "live" && !meeting.cancelled && (
            <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
              Happening now
            </span>
          )}
          {state === "soon" && !meeting.cancelled && (
            <span className="mt-1 inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
              Starting soon
            </span>
          )}
          {meeting.cancelled && (
            <span className="mt-1 inline-flex rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700">
              Cancelled
            </span>
          )}
        </div>
      </div>

      {!compact && meeting.description && (
        <p className="mt-3 whitespace-pre-wrap text-sm text-[var(--fos-text-secondary)]">
          {meeting.description}
        </p>
      )}

      <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--fos-text-muted)]">
        <Users size={14} />
        {meeting.organizer_name} · {accepted} of{" "}
        {meeting.invitees.length} going
      </p>

      {!compact && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {meeting.invitees.map((i) => (
            <li
              key={i.id}
              className="rounded-full bg-[var(--fos-surface-muted)] px-2.5 py-1 text-xs text-[var(--fos-text-secondary)]"
            >
              {i.name}
              {i.response === "accepted"
                ? " ✓"
                : i.response === "declined"
                  ? " ✕"
                  : " …"}
            </li>
          ))}
        </ul>
      )}

      {error && (
        <p className="mt-2 text-xs text-red-600">{error}</p>
      )}

      {!meeting.cancelled && state !== "ended" && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {canJoin && (
            <a
              href={meeting.join_url ?? undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--fos-primary)] px-3 py-1.5 text-sm font-semibold text-[var(--fos-on-primary)] hover:opacity-90"
            >
              <Video size={15} /> Join
            </a>
          )}

          {meeting.my_response && !meeting.is_organizer && (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => act("respond", { response: "accepted" })}
                className={`inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm ${
                  meeting.my_response === "accepted"
                    ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                    : "border-[var(--fos-border)]"
                }`}
              >
                <Check size={14} /> Going
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => act("respond", { response: "declined" })}
                className={`inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm ${
                  meeting.my_response === "declined"
                    ? "border-red-500 bg-red-50 text-red-700"
                    : "border-[var(--fos-border)]"
                }`}
              >
                <X size={14} /> Can&apos;t
              </button>
            </>
          )}

          {meeting.is_organizer && (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                if (window.confirm("Cancel this meeting for everyone?")) {
                  act("cancel");
                }
              }}
              className="rounded-lg border border-[var(--fos-border)] px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
            >
              Cancel meeting
            </button>
          )}

          {busy && <Loader2 size={14} className="animate-spin" />}
        </div>
      )}
    </div>
  );
}

/** A meeting card inside a chat, loaded from its id. */
export function MeetingCard({ meetingId }: { meetingId: string }) {
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [missing, setMissing] = useState(false);

  const load = useCallback(() => {
    api
      .get<Meeting>(`/meetings/${meetingId}`)
      .then((r) => setMeeting(r.data))
      .catch(() => setMissing(true));
  }, [meetingId]);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => {
      if (!document.hidden) load();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (missing) {
    return (
      <p className="text-sm italic opacity-70">
        A meeting you are not invited to.
      </p>
    );
  }

  if (!meeting) {
    return <Loader2 size={16} className="animate-spin" />;
  }

  return <MeetingBody meeting={meeting} onChange={setMeeting} compact />;
}
