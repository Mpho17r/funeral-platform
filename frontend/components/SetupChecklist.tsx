"use client";

import { CheckCircle2, ChevronRight, Circle, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import api from "@/lib/api";

type Step = {
  key: string;
  title: string;
  detail: string;
  path: string;
  done: boolean;
  required: boolean;
};

type Status = {
  steps: Step[];
  done: number;
  total: number;
  required_complete: boolean;
};

const HIDE_KEY = "fos-setup-hidden";

/** A "get set up" card for the dashboard. It disappears once the
 *  essentials are in place, or when the person closes it. */
export function SetupChecklist() {
  const router = useRouter();
  const [status, setStatus] = useState<Status | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    try {
      setHidden(localStorage.getItem(HIDE_KEY) === "1");
    } catch {
      // Storage can be unavailable; the card simply stays visible.
    }

    api
      .get<Status>("/onboarding/status")
      .then((response) => setStatus(response.data))
      .catch(() => setStatus(null));
  }, []);

  if (!status || status.required_complete || hidden) {
    return null;
  }

  function hide() {
    setHidden(true);

    try {
      localStorage.setItem(HIDE_KEY, "1");
    } catch {
      // Not fatal.
    }
  }

  const percent = Math.round((status.done / status.total) * 100);

  return (
    <section
      aria-label="Getting set up"
      className="mt-8 rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-serif text-xl">Getting set up</h2>
          <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
            {status.done} of {status.total} done. Work through these and
            FuneralOS is ready for your team.
          </p>
        </div>

        <button
          type="button"
          onClick={hide}
          aria-label="Hide setup guide"
          title="Hide this guide"
          className="rounded-lg p-1 text-[var(--fos-text-muted)] transition hover:bg-[var(--fos-surface-muted)]"
        >
          <X size={18} />
        </button>
      </div>

      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        className="mt-4 h-2 overflow-hidden rounded-full bg-[var(--fos-surface-muted)]"
      >
        <div
          className="h-full rounded-full bg-[var(--fos-primary)] transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>

      <ul className="mt-4 divide-y divide-[var(--fos-border)]">
        {status.steps.map((step) => (
          <li key={step.key}>
            <button
              type="button"
              onClick={() => router.push(step.path)}
              className="flex w-full items-center gap-3 py-3 text-left transition hover:opacity-80"
            >
              {step.done ? (
                <CheckCircle2
                  size={20}
                  className="shrink-0 text-emerald-600"
                  aria-label="Done"
                />
              ) : (
                <Circle
                  size={20}
                  className="shrink-0 text-[var(--fos-text-muted)]"
                  aria-label="Not done"
                />
              )}

              <span className="min-w-0 flex-1">
                <span
                  className={`block text-sm font-medium ${
                    step.done ? "text-[var(--fos-text-muted)] line-through" : ""
                  }`}
                >
                  {step.title}
                  {!step.required && !step.done && (
                    <span className="ml-2 text-xs font-normal text-[var(--fos-text-muted)]">
                      Optional
                    </span>
                  )}
                </span>

                {!step.done && (
                  <span className="block text-xs text-[var(--fos-text-muted)]">
                    {step.detail}
                  </span>
                )}
              </span>

              <ChevronRight
                size={16}
                className="shrink-0 text-[var(--fos-text-muted)]"
              />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
