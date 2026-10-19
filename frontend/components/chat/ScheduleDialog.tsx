"use client";

import { useState } from "react";
import { Check, Search } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { localInputToIso } from "@/lib/datetime";
import { Dialog, Field, inputClass } from "@/components/Dialog";
import { Banner } from "@/components/Notices";
import type { Meeting, Person } from "@/components/chat/types";

function localNow(addMinutes: number): string {
  const d = new Date(Date.now() + addMinutes * 60000);
  d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(
    d.getDate()
  )}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function plusHour(value: string): string {
  const d = new Date(value);
  d.setHours(d.getHours() + 1);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(
    d.getDate()
  )}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function ScheduleDialog({
  people,
  conversationId,
  conversationTitle,
  onClose,
  onCreated,
}: {
  people: Person[];
  conversationId?: string;
  conversationTitle?: string;
  onClose: () => void;
  onCreated: (meeting: Meeting) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [starts, setStarts] = useState(() => localNow(30));
  const [ends, setEnds] = useState(() => plusHour(localNow(30)));
  const [link, setLink] = useState<"make" | "own" | "none">("make");
  const [url, setUrl] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<Meeting | null>(null);

  const shown = people.filter((p) =>
    p.name.toLowerCase().includes(query.trim().toLowerCase())
  );

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");

    const startIso = localInputToIso(starts);
    const endIso = localInputToIso(ends);

    if (!title.trim()) return setError("Give the meeting a title.");
    if (!startIso || !endIso) return setError("Choose a start and end time.");
    if (!conversationId && picked.length === 0) {
      return setError("Invite at least one person.");
    }

    setBusy(true);

    try {
      const { data } = await api.post<Meeting>("/meetings", {
        title: title.trim(),
        description: description.trim() || null,
        starts_at: startIso,
        ends_at: endIso,
        make_call_link: link === "make",
        join_url: link === "own" ? url.trim() || null : null,
        user_ids: picked,
        conversation_id: conversationId ?? null,
      });

      if (data.conflicts && data.conflicts.length > 0) {
        setCreated(data);
      } else {
        onCreated(data);
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not schedule the meeting."));
    } finally {
      setBusy(false);
    }
  }

  if (created) {
    return (
      <Dialog title="Meeting scheduled" onClose={() => onCreated(created)}>
        <div className="space-y-3 text-sm">
          <p>
            <strong>{created.title}</strong> is on the calendar and the
            invitations are out.
          </p>
          <Banner tone="error" onDismiss={() => {}}>
            Heads up:{" "}
            {created.conflicts
              ?.map((c) => `${c.user_name} also has “${c.title}”`)
              .join("; ")}{" "}
            at that time.
          </Banner>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => onCreated(created)}
              className="rounded-lg bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-[var(--fos-on-primary)]"
            >
              Done
            </button>
          </div>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog title="Schedule a meeting" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Title">
          <input
            className={inputClass}
            value={title}
            maxLength={150}
            placeholder="e.g. Monday service briefing"
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Starts">
            <input
              type="datetime-local"
              className={inputClass}
              value={starts}
              onChange={(e) => {
                setStarts(e.target.value);
                if (e.target.value) setEnds(plusHour(e.target.value));
              }}
            />
          </Field>
          <Field label="Ends">
            <input
              type="datetime-local"
              className={inputClass}
              value={ends}
              min={starts}
              onChange={(e) => setEnds(e.target.value)}
            />
          </Field>
        </div>

        <Field label="Agenda (optional)">
          <textarea
            className={inputClass}
            rows={3}
            maxLength={2000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>

        <Field label="Call link">
          <div className="space-y-2 text-sm">
            {(
              [
                ["make", "Create a call link for me"],
                ["own", "I have a link (Zoom, Meet, Teams…)"],
                ["none", "No link, in person"],
              ] as const
            ).map(([id, label]) => (
              <label key={id} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="link"
                  checked={link === id}
                  onChange={() => setLink(id)}
                />
                {label}
              </label>
            ))}
            {link === "own" && (
              <input
                className={inputClass}
                value={url}
                placeholder="https://"
                onChange={(e) => setUrl(e.target.value)}
              />
            )}
          </div>
        </Field>

        {conversationId ? (
          <p className="rounded-lg bg-[var(--fos-surface-muted)] px-3 py-2 text-sm text-[var(--fos-text-secondary)]">
            Everyone in <strong>{conversationTitle}</strong> will be
            invited and see this in the chat.
          </p>
        ) : (
          <Field label={`Invite (${picked.length})`}>
            <div className="relative mb-2">
              <Search
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fos-text-muted)]"
              />
              <input
                className={`${inputClass} pl-9`}
                placeholder="Search colleagues"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <ul className="max-h-40 divide-y divide-[var(--fos-border)] overflow-y-auto rounded-lg border border-[var(--fos-border)]">
              {shown.map((p) => {
                const on = picked.includes(p.id);
                return (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() =>
                        setPicked((cur) =>
                          on ? cur.filter((x) => x !== p.id) : [...cur, p.id]
                        )
                      }
                      className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-[var(--fos-surface-muted)]"
                    >
                      {p.name}
                      {on && (
                        <Check
                          size={16}
                          className="text-[var(--fos-primary)]"
                        />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </Field>
        )}

        {error && (
          <Banner tone="error" onDismiss={() => setError("")}>
            {error}
          </Banner>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--fos-border)] px-4 py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-[var(--fos-on-primary)] disabled:opacity-50"
          >
            {busy ? "Scheduling…" : "Schedule"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
