"use client";

import { useState } from "react";
import { Archive, Check, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";

const STEPS = [
  { key: "open", label: "Open" },
  { key: "confirmed", label: "Confirmed" },
  { key: "in_progress", label: "In progress" },
  { key: "completed", label: "Completed" },
  { key: "closed", label: "Closed" },
];

const NEXT: Record<string, { to: string; label: string; hint: string }> = {
  open: {
    to: "confirmed",
    label: "Confirm the funeral",
    hint: "Moves on by itself when the arrangements are confirmed, the deceased is taken into care, or the funeral day arrives.",
  },
  confirmed: {
    to: "in_progress",
    label: "Start the funeral",
    hint: "Moves on by itself once the committal time has passed or the funeral day arrives.",
  },
  in_progress: {
    to: "completed",
    label: "Mark funeral completed",
    hint: "Moves on by itself when the arrangement is recorded as completed.",
  },
  completed: {
    to: "closed",
    label: "Close the case",
    hint: "Close once the paperwork and the account are finished.",
  },
};

/** Where the case is, and a button to move it to the next step by hand. */
export function CaseStatusControl({
  caseId,
  status,
  canEdit,
  canArchive = false,
  onChanged,
}: {
  caseId: string;
  status: string;
  canEdit: boolean;
  canArchive?: boolean;
  onChanged: () => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function archive() {
    if (!window.confirm("Archive this case? It leaves your lists and moves to the Archive, where you can find or restore it.")) return;
    try {
      setBusy(true);
      setError("");
      await api.post(`/cases/${caseId}/archive`);
      router.push("/cases");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not archive the case."));
      setBusy(false);
    }
  }

  async function move(to: string, ask: string) {
    if (!window.confirm(ask)) return;
    try {
      setBusy(true);
      setError("");
      await api.post(`/cases/${caseId}/lifecycle`, { status: to });
      onChanged();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not change the status."));
    } finally {
      setBusy(false);
    }
  }

  const cancelled = status === "cancelled";
  const index = STEPS.findIndex((s) => s.key === status);
  const next = NEXT[status];

  return (
    <div className="mt-5 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-4">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-xs">
        {STEPS.map((step, i) => {
          const done = !cancelled && i < index;
          const current = !cancelled && i === index;
          return (
            <li key={step.key} className="flex items-center gap-2">
              <span
                className={`flex items-center gap-1 rounded-full px-2.5 py-1 font-medium ${
                  current
                    ? "bg-slate-900 text-white"
                    : done
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-slate-100 text-slate-500"
                }`}
              >
                {done && <Check size={12} />}
                {step.label}
              </span>
              {i < STEPS.length - 1 && <span className="text-slate-300">›</span>}
            </li>
          );
        })}
        {cancelled && (
          <li className="rounded-full bg-red-100 px-2.5 py-1 font-medium text-red-700">
            Cancelled
          </li>
        )}
      </ol>

      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

      {canArchive && (status === "closed" || cancelled) && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={() => void archive()}
            className="flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold text-slate-800 disabled:opacity-60"
          >
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Archive size={15} />}
            Archive this case
          </button>
          <p className="text-xs text-slate-500">Finished cases are also archived automatically after a while.</p>
        </div>
      )}

      {canEdit && next && !cancelled && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void move(next.to, `${next.label}? This is recorded in the audit trail.`)
            }
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy && <Loader2 size={15} className="animate-spin" />}
            {next.label}
          </button>
          {status !== "completed" && (
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void move("cancelled", "Cancel this case? This cannot be undone.")
              }
              className="text-sm font-medium text-red-700 hover:underline"
            >
              Cancel case
            </button>
          )}
          <p className="text-xs text-slate-500">{next.hint}</p>
        </div>
      )}
    </div>
  );
}
