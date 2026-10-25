"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { CalendarClock, Plus, X } from "lucide-react";

import api from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { localInputToIso } from "@/lib/datetime";
import { getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, Field, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";
import { EmptyRow, Panel } from "@/components/dashboards/Shared";

type Viewing = {
  id: string;
  case_id: string;
  deceased_name: string;
  tag_number: string | null;
  starts_at: string;
  duration_minutes: number;
  room: string | null;
  visitor_name: string | null;
  expected_visitors: number | null;
  status: string;
};

export type ViewableRemains = {
  case_id: string;
  name: string;
  tag_number: string;
};

/** Family viewings coming up, with a way to book one. */
export function ViewingsPanel({
  candidates,
}: {
  candidates: ViewableRemains[];
}) {
  const { can } = useCurrentUser();
  const canManage = can("viewings.manage");

  const [items, setItems] = useState<Viewing[]>([]);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const [reload, setReload] = useState(0);

  const [caseId, setCaseId] = useState("");
  const [when, setWhen] = useState("");
  const [minutes, setMinutes] = useState("30");
  const [room, setRoom] = useState("Chapel of rest");
  const [visitor, setVisitor] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => setReload((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    api
      .get<{ items: Viewing[] }>("/mortuary/viewings", { params: { days: 14 } })
      .then((r) => {
        if (!cancelled) {
          setItems(r.data.items);
          setFailed(false);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  async function book(event: FormEvent) {
    event.preventDefault();
    const iso = localInputToIso(when);
    if (!caseId || !iso) {
      setError("Choose who is being viewed and when.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.post("/mortuary/viewings", {
        case_id: caseId,
        starts_at: iso,
        duration_minutes: Number(minutes),
        room: room.trim() || null,
        visitor_name: visitor.trim() || null,
      });
      setOpen(false);
      setWhen("");
      setVisitor("");
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not book this viewing."));
    } finally {
      setSaving(false);
    }
  }

  async function act(id: string, what: "complete" | "cancel") {
    try {
      if (what === "cancel") {
        const reason = window.prompt("Why is it cancelled?");
        if (!reason || reason.trim().length < 3) return;
        await api.post(`/mortuary/viewings/${id}/cancel`, {
          reason: reason.trim(),
        });
      } else {
        await api.post(`/mortuary/viewings/${id}/complete`);
      }
      load();
    } catch (err) {
      window.alert(getApiErrorMessage(err, "That did not work."));
    }
  }

  return (
    <>
      <Panel title="Family viewings">
        {failed ? (
          <EmptyRow>Could not load viewings just now.</EmptyRow>
        ) : items.length === 0 ? (
          <EmptyRow>No viewings booked in the next two weeks.</EmptyRow>
        ) : (
          <ul className="divide-y divide-[var(--fos-border)]">
            {items.map((v) => (
              <li key={v.id} className="flex items-start gap-3 px-5 py-3">
                <span className="mt-0.5 text-[var(--fos-text-muted)]">
                  <CalendarClock size={18} />
                </span>
                <span className="min-w-0 flex-1 text-sm">
                  <Link
                    href={`/cases/${v.case_id}`}
                    className="font-medium text-[var(--fos-text)] hover:underline"
                  >
                    {v.deceased_name}
                  </Link>
                  <span className="block text-xs text-[var(--fos-text-muted)]">
                    {formatDateTime(v.starts_at)} · {v.duration_minutes} min
                    {v.room ? ` · ${v.room}` : ""}
                    {v.visitor_name ? ` · ${v.visitor_name}` : ""}
                  </span>
                </span>
                {canManage && (
                  <span className="flex shrink-0 gap-2 text-xs">
                    <button
                      type="button"
                      onClick={() => act(v.id, "complete")}
                      className="font-medium text-[var(--fos-primary)] hover:underline"
                    >
                      Done
                    </button>
                    <button
                      type="button"
                      aria-label="Cancel viewing"
                      onClick={() => act(v.id, "cancel")}
                      className="text-[var(--fos-text-muted)] hover:text-red-600"
                    >
                      <X size={14} />
                    </button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        {canManage && (
          <div className="border-t border-[var(--fos-border)] px-5 py-3">
            <button
              type="button"
              disabled={candidates.length === 0}
              onClick={() => {
                setCaseId(candidates[0]?.case_id ?? "");
                setError("");
                setOpen(true);
              }}
              className="flex items-center gap-1.5 text-sm font-medium text-[var(--fos-primary)] disabled:opacity-50"
            >
              <Plus size={16} /> Book a viewing
            </button>
            {candidates.length === 0 && (
              <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                Remains must be identified and in the mortuary first.
              </p>
            )}
          </div>
        )}
      </Panel>

      {open && (
        <Dialog title="Book a family viewing" onClose={() => setOpen(false)}>
          <form onSubmit={book} className="space-y-4">
            <Field label="Who is being viewed">
              <select
                className={inputClass}
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
              >
                {candidates.map((c) => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.name} · {c.tag_number}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Date and time">
              <input
                required
                type="datetime-local"
                className={inputClass}
                value={when}
                onChange={(e) => setWhen(e.target.value)}
              />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Minutes">
                <input
                  type="number"
                  min={10}
                  max={240}
                  className={inputClass}
                  value={minutes}
                  onChange={(e) => setMinutes(e.target.value)}
                />
              </Field>
              <Field label="Room">
                <input
                  className={inputClass}
                  value={room}
                  onChange={(e) => setRoom(e.target.value)}
                />
              </Field>
            </div>
            <Field label="Family contact (optional)">
              <input
                className={inputClass}
                value={visitor}
                onChange={(e) => setVisitor(e.target.value)}
              />
            </Field>
            {error && <ErrorNote message={error} />}
            <DialogFooter
              onClose={() => setOpen(false)}
              saving={saving}
              submitLabel="Book viewing"
            />
          </form>
        </Dialog>
      )}
    </>
  );
}
