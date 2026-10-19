"use client";

import { useEffect, useState } from "react";

import api from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { getApiErrorMessage } from "@/lib/format";
import { Banner } from "@/components/Notices";

type Automation = {
  enabled: boolean;
  last_run_at: string | null;
  last_count: number | null;
};

export default function AutoRemindersToggle({
  onChanged,
}: {
  onChanged?: () => void;
}) {
  const [state, setState] = useState<Automation | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/communications/reminders/automation")
      .then((response) => setState(response.data))
      .catch(() => setState(null));
  }, []);

  if (!state) {
    return null;
  }

  async function change(enabled: boolean) {
    setSaving(true);
    setError("");

    try {
      const response = await api.put(
        "/communications/reminders/automation",
        { enabled }
      );
      setState(response.data);
      onChanged?.();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not change this setting."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-900">
            Find reminders automatically every day
          </p>
          <p className="mt-0.5 text-sm text-slate-500">
            {state.enabled
              ? "Due reminders are added to the list each morning. Nothing is sent until someone sends it."
              : "Off. Someone has to press Find reminders each day."}
          </p>
          {state.enabled && state.last_run_at && (
            <p className="mt-1 text-xs text-slate-500">
              Last run {formatDateTime(state.last_run_at)}:{" "}
              {state.last_count ?? 0} added.
            </p>
          )}
          {state.enabled && !state.last_run_at && (
            <p className="mt-1 text-xs text-slate-500">
              Has not run yet. The first run is the next scheduled morning.
            </p>
          )}
        </div>

        <button
          type="button"
          role="switch"
          aria-checked={state.enabled}
          aria-label="Find reminders automatically every day"
          disabled={saving}
          onClick={() => change(!state.enabled)}
          className={`relative h-6 w-11 shrink-0 rounded-full transition disabled:opacity-60 ${
            state.enabled ? "bg-[var(--fos-primary)]" : "bg-slate-300"
          }`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
              state.enabled ? "left-5" : "left-0.5"
            }`}
          />
        </button>
      </div>

      {error && (
        <div className="mt-3">
          <Banner tone="error" onDismiss={() => setError("")}>
            {error}
          </Banner>
        </div>
      )}
    </div>
  );
}
