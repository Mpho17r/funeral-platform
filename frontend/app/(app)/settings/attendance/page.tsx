"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  Clock3,
  Loader2,
  Save,
} from "lucide-react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

type BreakExpiryBehavior =
  | "auto_return"
  | "keep_active"
  | "notify_and_keep_active";

type User = {
  id: string;
  business_id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
};

type Business = {
  id: string;
  name: string;
  slug: string;
  tea_break_minutes: number;
  lunch_break_minutes: number;
  idle_timeout_minutes: number;
  break_expiry_behavior: BreakExpiryBehavior;
  break_warning_enabled: boolean;
  break_warning_minutes: number;
  break_expiry_notification_enabled: boolean;
};

function asRecord(
  value: unknown,
): Record<string, unknown> | undefined {
  return value !== null && typeof value === "object"
    ? (value as Record<string, unknown>)
    : undefined;
}

function getErrorMessage(
  error: unknown,
  fallback: string,
): string {
  const errorRecord = asRecord(error);
  const responseRecord = asRecord(errorRecord?.response);
  const dataRecord = asRecord(responseRecord?.data);
  const detail = dataRecord?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (typeof item === "string") {
          return item;
        }

        const itemRecord = asRecord(item);
        if (typeof itemRecord?.msg === "string") {
          const location = Array.isArray(itemRecord.loc)
            ? itemRecord.loc.join(".")
            : "";
          return location
            ? `${location}: ${itemRecord.msg}`
            : itemRecord.msg;
        }

        return null;
      })
      .filter((item): item is string => item !== null)
      .join(" | ");
  }

  const detailRecord = asRecord(detail);
  if (typeof detailRecord?.msg === "string") {
    return detailRecord.msg;
  }

  if (typeof errorRecord?.message === "string") {
    return errorRecord.message;
  }

  return fallback;
}

export default function AttendanceSettingsPage() {
  const router = useRouter();

  const [currentUser, setCurrentUser] =
    useState<User | null>(null);

  const [business, setBusiness] =
    useState<Business | null>(null);

  const [teaBreakMinutes, setTeaBreakMinutes] =
    useState(15);

  const [lunchBreakMinutes, setLunchBreakMinutes] =
    useState(60);

  const [idleTimeoutMinutes, setIdleTimeoutMinutes] =
    useState(15);

  const [breakExpiryBehavior, setBreakExpiryBehavior] =
    useState<BreakExpiryBehavior>(
      "notify_and_keep_active",
    );

  const [breakWarningEnabled, setBreakWarningEnabled] =
    useState(true);

  const [breakWarningMinutes, setBreakWarningMinutes] =
    useState(2);

  const [
    breakExpiryNotificationEnabled,
    setBreakExpiryNotificationEnabled,
  ] = useState(true);

  const [loading, setLoading] =
    useState(true);

  const [saving, setSaving] =
    useState(false);

  const [message, setMessage] =
    useState("");

  const [error, setError] =
    useState("");

  const loadBusiness = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      setMessage("");

      const [meResponse, usersResponse] = await Promise.all([
        api.get<{ business_id?: string }>("/auth/me"),
        api.get<User[]>("/users"),
      ]);

      const businessId = meResponse.data?.business_id;
      if (!businessId) {
        throw new Error(
          "Your account is not linked to a business.",
        );
      }

      const token = sessionStorage.getItem("access_token");
      let loggedInUser: User | null = null;

      if (token) {
        try {
          const payload: { sub?: string } = JSON.parse(
            atob(token.split(".")[1]),
          );
          loggedInUser =
            usersResponse.data.find(
              (user) => user.id === payload.sub,
            ) ?? null;
        } catch {
          loggedInUser = null;
        }
      }

      setCurrentUser(loggedInUser);

      if (loggedInUser?.role !== "main_admin") {
        return;
      }

      const businessResponse = await api.get<Business>(
        `/businesses/${businessId}`,
      );
      const data = businessResponse.data;

      setBusiness(data);
      setTeaBreakMinutes(data.tea_break_minutes);
      setLunchBreakMinutes(data.lunch_break_minutes);
      setIdleTimeoutMinutes(data.idle_timeout_minutes);
      setBreakExpiryBehavior(data.break_expiry_behavior);
      setBreakWarningEnabled(data.break_warning_enabled);
      setBreakWarningMinutes(data.break_warning_minutes);
      setBreakExpiryNotificationEnabled(
        data.break_expiry_notification_enabled,
      );
    } catch (err: unknown) {
      setError(
        getErrorMessage(
          err,
          "Unable to load attendance settings.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    async function initializeAttendanceSettings() {
      await loadBusiness();
    }

    void initializeAttendanceSettings();
  }, [loadBusiness]);

  async function saveSettings() {
    if (!business) {
      return;
    }

    setError("");
    setMessage("");

    if (teaBreakMinutes < 0 || teaBreakMinutes > 480) {
      setError(
        "Tea break duration must be between 0 and 480 minutes.",
      );
      return;
    }

    if (
      lunchBreakMinutes < 0 ||
      lunchBreakMinutes > 480
    ) {
      setError(
        "Lunch break duration must be between 0 and 480 minutes.",
      );
      return;
    }

    if (
      idleTimeoutMinutes < 1 ||
      idleTimeoutMinutes > 480
    ) {
      setError(
        "Idle timeout must be between 1 and 480 minutes.",
      );
      return;
    }

    if (
      breakWarningMinutes < 0 ||
      breakWarningMinutes > 120
    ) {
      setError(
        "Break warning must be between 0 and 120 minutes.",
      );
      return;
    }

    if (breakWarningEnabled) {
      if (
        teaBreakMinutes > 0 &&
        breakWarningMinutes >= teaBreakMinutes
      ) {
        setError(
          "Warning time must be less than the tea break duration.",
        );
        return;
      }

      if (
        lunchBreakMinutes > 0 &&
        breakWarningMinutes >= lunchBreakMinutes
      ) {
        setError(
          "Warning time must be less than the lunch break duration.",
        );
        return;
      }
    }

    try {
      setSaving(true);

      const response =
        await api.patch<Business>(
          `/businesses/${business.id}/attendance-policy`,
          {
            tea_break_minutes: teaBreakMinutes,
            lunch_break_minutes: lunchBreakMinutes,
            idle_timeout_minutes: idleTimeoutMinutes,
            break_expiry_behavior:
              breakExpiryBehavior,
            break_warning_enabled:
              breakWarningEnabled,
            break_warning_minutes:
              breakWarningMinutes,
            break_expiry_notification_enabled:
              breakExpiryNotificationEnabled,
          },
        );

      const updatedBusiness =
        response.data;

      setBusiness(updatedBusiness);
      setTeaBreakMinutes(
        updatedBusiness.tea_break_minutes,
      );
      setLunchBreakMinutes(
        updatedBusiness.lunch_break_minutes,
      );
      setIdleTimeoutMinutes(
        updatedBusiness.idle_timeout_minutes,
      );
      setBreakExpiryBehavior(
        updatedBusiness.break_expiry_behavior,
      );
      setBreakWarningEnabled(
        updatedBusiness.break_warning_enabled,
      );
      setBreakWarningMinutes(
        updatedBusiness.break_warning_minutes,
      );
      setBreakExpiryNotificationEnabled(
        updatedBusiness.break_expiry_notification_enabled,
      );

      setMessage(
        "Attendance settings saved successfully.",
      );
    } catch (err: unknown) {
      setError(
        getErrorMessage(
          err,
          "Unable to save attendance settings.",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--fos-surface-muted)] text-[var(--fos-text)] dark:bg-slate-950 dark:text-slate-100">
        <div className="flex min-h-screen items-center justify-center">
          <div className="flex items-center gap-3 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
            <Loader2
              size={20}
              className="animate-spin"
            />
            Loading attendance settings...
          </div>
        </div>
      </main>
    );
  }

  if (currentUser?.role !== "main_admin") {
    return (
      <main className="min-h-screen bg-[var(--fos-surface-muted)] text-[var(--fos-text)] dark:bg-slate-950 dark:text-slate-100">
        <div className="flex min-h-screen items-center justify-center p-6">
          <div className="w-full max-w-lg rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-8 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] dark:bg-slate-800 dark:text-slate-200">
              <Clock3 size={24} />
            </div>

            <h1 className="mt-5 text-xl font-bold text-[var(--fos-text)] dark:text-white">
              Main Admin access required
            </h1>

            <p className="mt-3 text-sm leading-6 text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
              Attendance and staff policy settings can only be
              configured by the Main Admin.
            </p>

            <button
              type="button"
              onClick={() => router.push("/settings")}
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-[var(--fos-surface)] dark:text-[var(--fos-text)] dark:hover:bg-[var(--fos-border)]"
            >
              <ArrowLeft size={16} />
              Back to Settings
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--fos-surface-muted)] text-[var(--fos-text)] dark:bg-slate-950 dark:text-slate-100">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-20 items-center justify-between border-b border-[var(--fos-border)] bg-[var(--fos-surface)] px-6 dark:border-slate-800 dark:bg-slate-900">
          <div>
            <h2 className="text-xl font-bold text-[var(--fos-text)] dark:text-white">
              Attendance & Staff
            </h2>

            <p className="text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
              Configure attendance, breaks and staff presence.
            </p>
          </div>
        </header>

        <section className="flex-1 p-6 md:p-8">
          <div className="mx-auto max-w-4xl">
            <button
              type="button"
              onClick={() => router.push("/settings")}
              className="mb-6 flex items-center gap-2 text-sm font-medium text-[var(--fos-text-muted)] transition hover:text-[var(--fos-text)] dark:text-[var(--fos-text-muted)] dark:hover:text-white"
            >
              <ArrowLeft size={16} />
              Back to Settings
            </button>

            <div className="mb-8">
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] dark:bg-slate-800 dark:text-slate-200">
                  <Clock3 size={24} />
                </div>

                <div>
                  <h1 className="text-2xl font-bold text-[var(--fos-text)] dark:text-white">
                    Attendance Policy
                  </h1>

                  <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                    {business?.name ??
                      "Configure staff attendance behaviour."}
                  </p>
                </div>
              </div>
            </div>

            {error && (
              <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300">
                {error}
              </div>
            )}

            {message && (
              <div className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300">
                {message}
              </div>
            )}

            <div className="space-y-6">
              <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <h2 className="text-lg font-semibold text-[var(--fos-text)] dark:text-white">
                  Workday presence
                </h2>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                  Control when checked-in staff are considered away
                  because of inactivity.
                </p>

                <div className="mt-6 max-w-md">
                  <label className="block text-sm font-medium text-[var(--fos-text-secondary)] dark:text-slate-200">
                    Idle timeout
                  </label>

                  <div className="mt-2 flex items-center gap-3">
                    <input
                      type="number"
                      min={1}
                      max={480}
                      value={idleTimeoutMinutes}
                      onChange={(event) =>
                        setIdleTimeoutMinutes(
                          Number(event.target.value),
                        )
                      }
                      className="w-32 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-800"
                    />

                    <span className="text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                      minutes
                    </span>
                  </div>
                </div>
              </section>

              <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <h2 className="text-lg font-semibold text-[var(--fos-text)] dark:text-white">
                  Break durations
                </h2>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                  Set the standard duration for staff tea and lunch
                  breaks.
                </p>

                <div className="mt-6 grid gap-6 md:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-[var(--fos-text-secondary)] dark:text-slate-200">
                      Tea break
                    </label>

                    <div className="mt-2 flex items-center gap-3">
                      <input
                        type="number"
                        min={0}
                        max={480}
                        value={teaBreakMinutes}
                        onChange={(event) =>
                          setTeaBreakMinutes(
                            Number(event.target.value),
                          )
                        }
                        className="w-32 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-800"
                      />

                      <span className="text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                        minutes
                      </span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-[var(--fos-text-secondary)] dark:text-slate-200">
                      Lunch break
                    </label>

                    <div className="mt-2 flex items-center gap-3">
                      <input
                        type="number"
                        min={0}
                        max={480}
                        value={lunchBreakMinutes}
                        onChange={(event) =>
                          setLunchBreakMinutes(
                            Number(event.target.value),
                          )
                        }
                        className="w-32 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-800"
                      />

                      <span className="text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                        minutes
                      </span>
                    </div>
                  </div>
                </div>
              </section>

              <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <h2 className="text-lg font-semibold text-[var(--fos-text)] dark:text-white">
                  Break expiry
                </h2>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                  Decide what happens when a staff break reaches its
                  configured duration.
                </p>

                <div className="mt-6">
                  <label className="block text-sm font-medium text-[var(--fos-text-secondary)] dark:text-slate-200">
                    Expiry behaviour
                  </label>

                  <select
                    value={breakExpiryBehavior}
                    onChange={(event) =>
                      setBreakExpiryBehavior(
                        event.target.value as BreakExpiryBehavior,
                      )
                    }
                    className="mt-2 w-full max-w-md rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-800"
                  >
                    <option value="auto_return">
                      Automatically return staff to attendance
                    </option>
                    <option value="keep_active">
                      Keep the break active
                    </option>
                    <option value="notify_and_keep_active">
                      Notify staff and keep the break active
                    </option>
                  </select>
                </div>
              </section>

              <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <h2 className="text-lg font-semibold text-[var(--fos-text)] dark:text-white">
                  Break warnings
                </h2>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                  Warn staff before their configured break duration
                  expires.
                </p>

                <div className="mt-6 space-y-5">
                  <label className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={breakWarningEnabled}
                      onChange={(event) =>
                        setBreakWarningEnabled(
                          event.target.checked,
                        )
                      }
                      className="h-4 w-4 rounded border-[var(--fos-border)] text-purple-600 focus:ring-purple-500 dark:border-slate-700"
                    />

                    <span className="text-sm font-medium text-[var(--fos-text-secondary)] dark:text-slate-200">
                      Enable break warnings
                    </span>
                  </label>

                  <div className="max-w-md">
                    <label className="block text-sm font-medium text-[var(--fos-text-secondary)] dark:text-slate-200">
                      Warning time
                    </label>

                    <div className="mt-2 flex items-center gap-3">
                      <input
                        type="number"
                        min={0}
                        max={120}
                        value={breakWarningMinutes}
                        disabled={!breakWarningEnabled}
                        onChange={(event) =>
                          setBreakWarningMinutes(
                            Number(event.target.value),
                          )
                        }
                        className="w-32 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-800"
                      />

                      <span className="text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                        minutes before expiry
                      </span>
                    </div>
                  </div>

                  <label className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={
                        breakExpiryNotificationEnabled
                      }
                      onChange={(event) =>
                        setBreakExpiryNotificationEnabled(
                          event.target.checked,
                        )
                      }
                      className="h-4 w-4 rounded border-[var(--fos-border)] text-purple-600 focus:ring-purple-500 dark:border-slate-700"
                    />

                    <span className="text-sm font-medium text-[var(--fos-text-secondary)] dark:text-slate-200">
                      Enable break expiry notifications
                    </span>
                  </label>
                </div>
              </section>

              <div className="flex items-center justify-end gap-4">
                <button
                  type="button"
                  onClick={() => router.push("/settings")}
                  disabled={saving}
                  className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-5 py-3 text-sm font-semibold text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)] disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={saveSettings}
                  disabled={saving || !business}
                  className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving ? (
                    <Loader2
                      size={17}
                      className="animate-spin"
                    />
                  ) : (
                    <Save size={17} />
                  )}

                  {saving
                    ? "Saving..."
                    : "Save Attendance Settings"}
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
