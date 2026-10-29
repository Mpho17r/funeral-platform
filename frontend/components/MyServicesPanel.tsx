"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CalendarClock, HandHeart } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";

export const SERVICE_STATUS: Record<string, string> = {
  pending: "Not started",
  confirmed: "Confirmed",
  in_progress: "In progress",
  completed: "Completed",
};

export type ServiceRow = {
  id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  service_name: string;
  status: string;
  scheduled_date: string | null;
  due_at: string | null;
  assignees: { id: string; name: string }[];
  can_update: boolean;
};

export function whenService(due_at: string | null, scheduled: string | null) {
  const value = due_at ?? scheduled;
  if (!value) return "No date";
  const d = new Date(value);
  return due_at
    ? d.toLocaleString("en-ZA", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("en-ZA", { day: "numeric", month: "short" });
}

/** Services given to the signed-in person, with a status they keep up to date. */
export default function MyServicesPanel() {
  const { can } = useCurrentUser();
  const allowed = can("services.view");
  const [rows, setRows] = useState<ServiceRow[] | null>(null);
  const [error, setError] = useState("");
  const [now] = useState(() => Date.now());

  const load = useCallback(() => {
    return api
      .get<{ services: ServiceRow[] }>("/service-work/board", { params: { scope: "mine", state: "open" } })
      .then((r) => setRows(r.data.services))
      .catch(() => setRows([]));
  }, []);

  useEffect(() => {
    if (allowed) void load();
  }, [allowed, load]);

  async function setStatus(id: string, status: string) {
    try {
      setError("");
      await api.post(`/service-work/${id}/status`, { status });
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not change the status."));
    } finally {
      await load();
    }
  }

  if (!allowed || rows === null || rows.length === 0) return null;

  return (
    <section className="overflow-hidden rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--fos-border)] px-5 py-4">
        <h2 className="flex items-center gap-2 font-display text-xl font-semibold">
          <HandHeart size={19} /> My services
        </h2>
        <span className="text-xs text-[var(--fos-text-muted)]">You keep these up to date</span>
      </div>
      <div className="p-3">
        {error && <p className="px-2 pb-2 text-sm text-red-700">{error}</p>}
        <ul className="divide-y divide-[var(--fos-border)]">
          {rows.map((s) => {
            const late = s.due_at ? new Date(s.due_at).getTime() < now : false;
            return (
              <li key={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-2 py-2.5">
                <Link href={`/cases/${s.case_id}/services`} className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{s.service_name}</span>
                  <span className="flex flex-wrap items-center gap-x-2 text-xs text-[var(--fos-text-muted)]">
                    <span>{s.deceased_full_name}</span>
                    <span className={`flex items-center gap-1 ${late ? "font-semibold text-red-600" : ""}`}>
                      <CalendarClock size={12} /> {whenService(s.due_at, s.scheduled_date)}
                    </span>
                  </span>
                </Link>
                <select
                  aria-label={`Status of ${s.service_name}`}
                  value={s.status}
                  disabled={!s.can_update}
                  onChange={(e) => void setStatus(s.id, e.target.value)}
                  className="rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-2 py-1 text-xs"
                >
                  {Object.entries(SERVICE_STATUS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
