"use client";

import ChatPanel from "@/components/chat/ChatPanel";
import MeetingsPanel from "@/components/chat/MeetingsPanel";
import WorkdayCard from "@/components/workday/WorkdayCard";
import { useCurrentUser } from "@/components/CurrentUserProvider";

import {
  Clock3,
  RefreshCw,
  UserCheck,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";

import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";


type ApiErrorResponse = {
  detail?: string;
};

function getApiError(err: unknown): {
  status?: number;
  detail?: string;
} {
  if (!axios.isAxiosError<ApiErrorResponse>(err)) {
    return {};
  }

  return {
    status: err.response?.status,
    detail: err.response?.data?.detail,
  };
}

type PresenceStatus =
  | "online"
  | "away"
  | "offline"
  | "checked_in";

type StaffPresence = {
  id: string;
  business_id: string;
  user_id: string;
  user_name: string;
  role: string;
  status: PresenceStatus;
  last_seen_at: string | null;
  checked_in_at: string | null;
  checked_out_at: string | null;
  created_at: string;
  updated_at: string;
};

type AttendanceSession = {
  id: string;
  business_id: string;
  user_id: string;
  status: string;
  checked_in_at: string;
  checked_out_at: string | null;
  created_at: string;
  updated_at: string;
};

type BreakSession = {
  id: string;
  attendance_session_id: string;
  business_id: string;
  user_id: string;
  break_type: "tea" | "lunch";
  started_at: string;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
};

type AttendanceMe = {
  attendance: AttendanceSession | null;
  current_break: BreakSession | null;
  break_warning_active: boolean;
  break_expires_at: string | null;
  presence: PresenceStatus;
  last_seen_at: string | null;
};

function getStatusLabel(status: PresenceStatus) {
  switch (status) {
    case "online":
      return "Online";

    case "away":
      return "Away";

    case "checked_in":
      return "Checked in";

    default:
      return "Offline";
  }
}

function getStatusClasses(status: PresenceStatus) {
  switch (status) {
    case "online":
      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300";

    case "away":
      return "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300";

    case "checked_in":
      return "bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300";

    default:
      return "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] dark:bg-slate-800 dark:text-slate-300";
  }
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}


type WorkspaceTab = "chat" | "meetings" | "team";

export default function StaffWorkspacePage() {
  const { user } = useCurrentUser();
  const [tab, setTab] = useState<WorkspaceTab>("chat");
  const router = useRouter();

  const [attendance, setAttendance] =
    useState<AttendanceMe | null>(null);

  const [presence, setPresence] = useState<StaffPresence[]>([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState("");

  const mountedRef = useRef(true);

  const loadWorkspace = useCallback(
    async (showRefreshState = false) => {
      if (showRefreshState) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");

      try {
        const [attendanceResponse, presenceResponse] =
          await Promise.all([
            api.get<AttendanceMe>("/attendance/me"),
            api.get<StaffPresence[]>("/presence"),
          ]);

        if (!mountedRef.current) {
          return;
        }

        setAttendance(attendanceResponse.data);
        setPresence(presenceResponse.data);
      } catch (err: unknown) {
        const apiError = getApiError(err);
        if (apiError.status === 401) {
          router.push("/login");
          return;
        }

        if (mountedRef.current) {
          setError(
            apiError.detail ||
              "Unable to load staff workspace."
          );
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [router]
  );

  const performAction = useCallback(
    async (
      key: string,
      request: () => Promise<void>
    ) => {
      setAction(key);
      setError("");

      try {
        await request();
        await loadWorkspace(true);
      } catch (err: unknown) {
        const apiError = getApiError(err);
        if (apiError.status === 401) {
          router.push("/login");
          return;
        }

        setError(
          apiError.detail ||
            "Unable to complete that action."
        );
      } finally {
        if (mountedRef.current) {
          setAction(null);
        }
      }
    },
    [loadWorkspace, router]
  );

  const checkIn = useCallback(async () => {
    await performAction("check-in", async () => {
      await api.post("/attendance/check-in");
    });
  }, [performAction]);

  const checkOut = useCallback(async () => {
    await performAction("check-out", async () => {
      await api.post("/attendance/check-out");
    });
  }, [performAction]);

  const startBreak = useCallback(
    async (breakType: "tea" | "lunch") => {
      await performAction(breakType, async () => {
        await api.post("/attendance/breaks/start", {
          break_type: breakType,
        });
      });
    },
    [performAction]
  );

  const endBreak = useCallback(async () => {
    await performAction("end-break", async () => {
      await api.post("/attendance/breaks/end");
    });
  }, [performAction]);

  const sendHeartbeat = useCallback(async () => {
    if (!attendance?.attendance) {
      return;
    }

    try {
      const response = await api.post<AttendanceMe>(
        "/attendance/heartbeat"
      );

      if (mountedRef.current) {
        setAttendance(response.data);
      }
    } catch (err: unknown) {
        const apiError = getApiError(err);
      if (apiError.status === 401) {
        router.push("/login");
        return;
      }

      if (apiError.status === 409) {
        await loadWorkspace();
      }
    }
  }, [attendance?.attendance, loadWorkspace, router]);

  useEffect(() => {
    mountedRef.current = true;

    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    // The initial workspace fetch belongs in this authentication effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadWorkspace();

    return () => {
      mountedRef.current = false;
    };
  }, [loadWorkspace, router]);

  useEffect(() => {
    if (!attendance?.attendance) {
      return;
    }

    const heartbeatTimer = window.setInterval(
      sendHeartbeat,
      60_000
    );

    return () => {
      window.clearInterval(heartbeatTimer);
    };
  }, [attendance?.attendance, sendHeartbeat]);

  useEffect(() => {
    if (!attendance?.attendance) {
      return;
    }

    const refreshTimer = window.setInterval(
      () => loadWorkspace(),
      30_000
    );

    return () => {
      window.clearInterval(refreshTimer);
    };
  }, [attendance?.attendance, loadWorkspace]);


  const currentBreak = attendance?.current_break ?? null;

  const onlineCount = presence.filter(
    (person) => person.status === "online"
  ).length;

  const awayCount = presence.filter(
    (person) => person.status === "away"
  ).length;

  const checkedInCount = presence.filter(
    (person) =>
      person.status === "checked_in" ||
      person.status === "online" ||
      person.status === "away"
  ).length;

  const breakExpiresAt = attendance?.break_expires_at ?? null;
  const breakWarningActive =
    attendance?.break_warning_active ?? false;

  return (
    <main className="space-y-6 p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--fos-text)] dark:text-white">
            Staff Workspace
          </h1>

          <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
            Manage your attendance and see your team&apos;s current availability.
          </p>
        </div>

        <button
          type="button"
          onClick={() => loadWorkspace(true)}
          disabled={refreshing}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-2.5 text-sm font-medium text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)] disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          <RefreshCw
            size={16}
            className={refreshing ? "animate-spin" : ""}
          />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300">
          {error}
        </div>
      )}

      <WorkdayCard
        firstName={(user?.full_name ?? "").split(" ")[0]}
        loaded={attendance !== null}
        checkedInAt={attendance?.attendance?.checked_in_at ?? null}
        currentBreak={currentBreak}
        breakExpiresAt={breakExpiresAt}
        warning={breakWarningActive}
        action={action}
        onCheckIn={checkIn}
        onCheckOut={checkOut}
        onStartBreak={startBreak}
        onEndBreak={endBreak}
      />

      <div
        role="tablist"
        className="inline-flex rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-1"
      >
        {(
          [
            ["chat", "Chat"],
            ["meetings", "Meetings"],
            ["team", "Team"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-lg px-4 py-1.5 text-sm font-medium transition ${
              tab === id
                ? "bg-[var(--fos-primary)] text-[var(--fos-on-primary)]"
                : "text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "chat" && <ChatPanel />}
      {tab === "meetings" && <MeetingsPanel />}

      {tab === "team" && (
        <>
      {/* SUMMARY */}
      <section className="grid gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-[var(--fos-surface-muted)] p-2.5 dark:bg-slate-800">
              <Users size={19} />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                Team
              </p>

              <p className="text-2xl font-bold text-[var(--fos-text)] dark:text-white">
                {loading ? "—" : presence.length}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-emerald-100 p-2.5 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
              <UserCheck size={19} />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                Online
              </p>

              <p className="text-2xl font-bold text-[var(--fos-text)] dark:text-white">
                {loading ? "—" : onlineCount}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-blue-100 p-2.5 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
              <Clock3 size={19} />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                At work
              </p>

              <p className="text-2xl font-bold text-[var(--fos-text)] dark:text-white">
                {loading ? "—" : checkedInCount}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-amber-100 p-2.5 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
              <Clock3 size={19} />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                Away
              </p>

              <p className="text-2xl font-bold text-[var(--fos-text)] dark:text-white">
                {loading ? "—" : awayCount}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* TEAM PRESENCE */}
      <section className="overflow-hidden rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-[var(--fos-border)] px-5 py-4 dark:border-slate-800">
          <h2 className="font-semibold text-[var(--fos-text)] dark:text-white">
            Team Presence
          </h2>

          <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
            Current availability across this funeral business.
          </p>
        </div>

        {loading ? (
          <div className="px-5 py-10 text-center text-sm text-[var(--fos-text-muted)]">
            Loading staff presence...
          </div>
        ) : presence.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-[var(--fos-text-muted)]">
            No staff presence records found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--fos-page)] text-xs uppercase tracking-wide text-[var(--fos-text-muted)] dark:bg-slate-950/40">
                <tr>
                  <th className="px-5 py-3 font-medium">
                    Staff member
                  </th>

                  <th className="px-5 py-3 font-medium">
                    Role
                  </th>

                  <th className="px-5 py-3 font-medium">
                    Status
                  </th>

                  <th className="px-5 py-3 font-medium">
                    Last seen
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {presence.map((person) => (
                  <tr
                    key={person.id}
                    className="hover:bg-[var(--fos-page)] dark:hover:bg-slate-800/40"
                  >
                    <td className="px-5 py-4 font-medium text-[var(--fos-text)] dark:text-white">
                      {person.user_name}
                    </td>

                    <td className="px-5 py-4 capitalize text-[var(--fos-text-secondary)] dark:text-slate-300">
                      {person.role.replaceAll("_", " ")}
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusClasses(
                          person.status
                        )}`}
                      >
                        {getStatusLabel(person.status)}
                      </span>
                    </td>

                    <td className="px-5 py-4 text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                      {formatDateTime(person.last_seen_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="flex items-center gap-2 text-xs text-[var(--fos-text-muted)]">
        <Clock3 size={14} />
        <span>
          Attendance status is updated automatically from your activity.
        </span>
      </div>
        </>
      )}
    </main>
  );
}
