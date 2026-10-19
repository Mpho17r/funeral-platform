"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarPlus, Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { dayKey, formatDayHeading } from "@/lib/datetime";
import { Banner } from "@/components/Notices";
import { MeetingBody } from "@/components/chat/MeetingCard";
import ScheduleDialog from "@/components/chat/ScheduleDialog";
import type { Meeting, Person } from "@/components/chat/types";

export default function MeetingsPanel() {
  const [scope, setScope] = useState<"upcoming" | "past">("upcoming");
  const [meetings, setMeetings] = useState<Meeting[] | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<Meeting[]>("/meetings", {
        params: { scope },
      });
      setMeetings(data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load meetings."));
      setMeetings((m) => m ?? []);
    }
  }, [scope]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMeetings(null);
    load();
    const timer = window.setInterval(() => {
      if (!document.hidden) load();
    }, 20000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    api
      .get<Person[]>("/chat/people")
      .then((r) => setPeople(r.data))
      .catch(() => {});
  }, []);

  const groups: [string, Meeting[]][] = [];
  for (const m of meetings ?? []) {
    const day = dayKey(m.starts_at);
    const last = groups[groups.length - 1];
    if (last && last[0] === day) last[1].push(m);
    else groups.push([day, [m]]);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          role="tablist"
          className="inline-flex rounded-lg border border-[var(--fos-border)] p-1"
        >
          {(["upcoming", "past"] as const).map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={scope === id}
              onClick={() => setScope(id)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium capitalize ${
                scope === id
                  ? "bg-[var(--fos-primary)] text-[var(--fos-on-primary)]"
                  : "text-[var(--fos-text-secondary)]"
              }`}
            >
              {id}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setCreating(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-[var(--fos-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)] hover:opacity-90"
        >
          <CalendarPlus size={16} /> Schedule meeting
        </button>
      </div>

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      {meetings === null ? (
        <div className="flex justify-center py-16 text-[var(--fos-text-muted)]">
          <Loader2 className="animate-spin" />
        </div>
      ) : groups.length === 0 ? (
        <p className="py-16 text-center text-sm text-[var(--fos-text-muted)]">
          {scope === "upcoming"
            ? "No upcoming meetings. Schedule one to invite your team."
            : "No past meetings."}
        </p>
      ) : (
        groups.map(([day, list]) => (
          <section key={day} className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
              {formatDayHeading(day)}
            </h2>
            {list.map((m) => (
              <MeetingBody
                key={m.id}
                meeting={m}
                onChange={(next) =>
                  setMeetings((cur) =>
                    (cur ?? []).map((x) => (x.id === next.id ? next : x))
                  )
                }
              />
            ))}
          </section>
        ))
      )}

      {creating && (
        <ScheduleDialog
          people={people}
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            load();
          }}
        />
      )}
    </div>
  );
}
