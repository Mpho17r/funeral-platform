"use client";

import {
  Coffee,
  Clock3,
  LogIn,
  LogOut,
  RefreshCw,
  Utensils,
  UserCheck,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

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
      return "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
  }
}

function getBreakLabel(breakType: "tea" | "lunch") {
  return breakType === "tea" ? "Tea Break" : "Lunch Break";
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

function formatElapsed(value: string | null) {
  if (!value) {
    return "—";
  }

  const start = new Date(value).getTime();

  if (Number.isNaN(start)) {
    return "—";
  }

  const seconds = Math.max(
    0,
    Math.floor((Date.now() - start) / 1000)
  );

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }

  return `${minutes}m`;
}

export default function StaffWorkspacePage() {
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
      } catch (err: any) {
        if (err?.response?.status === 401) {
          router.push("/login");
          return;
        }

        if (mountedRef.current) {
          setError(
            err?.response?.data?.detail ||
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
      } catch (err: any) {
        if (err?.response?.status === 401) {
          router.push("/login");
          return;
        }

        setError(
          err?.response?.data?.detail ||
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
    } catch (err: any) {
      if (err?.response?.status === 401) {
        router.push("/login");
        return;
      }

      if (err?.response?.status === 409) {
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

  const isCheckedIn = Boolean(attendance?.attendance);
  const currentBreak = attendance?.current_break ?? null;
  const currentPresence = attendance?.presence ?? "offline";

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

  const breakCount = currentBreak ? 1 : 0;

  return (
    <main className="space-y-6 p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-950 dark:text-white">
            Staff Workspace
          </h1>

          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Manage your attendance and see your team&apos;s current availability.
          </p>
        </div>

        <button
          type="button"
          onClick={() => loadWorkspace(true)}
          disabled={refreshing}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
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

      {/* MY ATTENDANCE */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <UserCheck
                size={20}
                className="text-slate-500"
              />

              <h2 className="font-semibold text-slate-950 dark:text-white">
                My Attendance
              </h2>
            </div>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Check in when you start work and check out when your workday ends.
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusClasses(
                  currentPresence
                )}`}
              >
                {getStatusLabel(currentPresence)}
              </span>

              {currentBreak && (
                <span className="inline-flex rounded-full bg-purple-100 px-2.5 py-1 text-xs font-medium text-purple-700 dark:bg-purple-500/10 dark:text-purple-300">
                  {getBreakLabel(currentBreak.break_type)}
                </span>
              )}
            </div>

            {attendance?.attendance && (
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Checked in
                  </p>

                  <p className="font-medium text-slate-900 dark:text-white">
                    {formatDateTime(
                      attendance.attendance.checked_in_at
                    )}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Current session
                  </p>

                  <p className="font-medium text-slate-900 dark:text-white">
                    {formatElapsed(
                      attendance.attendance.checked_in_at
                    )}
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {!isCheckedIn ? (
              <button
                type="button"
                onClick={checkIn}
                disabled={action !== null || loading}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
              >
                {action === "check-in" ? (
                  <RefreshCw
                    size={17}
                    className="animate-spin"
                  />
                ) : (
                  <LogIn size={17} />
                )}
                Check In
              </button>
            ) : (
              <>
                {!currentBreak && (
                  <>
                    <button
                      type="button"
                      onClick={() => startBreak("tea")}
                      disabled={action !== null}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                      {action === "tea" ? (
                        <RefreshCw
                          size={17}
                          className="animate-spin"
                        />
                      ) : (
                        <Coffee size={17} />
                      )}
                      Tea Break
                    </button>

                    <button
                      type="button"
                      onClick={() => startBreak("lunch")}
                      disabled={action !== null}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                      {action === "lunch" ? (
                        <RefreshCw
                          size={17}
                          className="animate-spin"
                        />
                      ) : (
                        <Utensils size={17} />
                      )}
                      Lunch Break
                    </button>
                  </>
                )}

                {currentBreak && (
                  <button
                    type="button"
                    onClick={endBreak}
                    disabled={action !== null}
                    className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {action === "end-break" ? (
                      <RefreshCw
                        size={17}
                        className="animate-spin"
                      />
                    ) : (
                      <Clock3 size={17} />
                    )}
                    End Break
                  </button>
                )}

                <button
                  type="button"
                  onClick={checkOut}
                  disabled={action !== null}
                  className="inline-flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300 dark:hover:bg-red-950/40"
                >
                  {action === "check-out" ? (
                    <RefreshCw
                      size={17}
                      className="animate-spin"
                    />
                  ) : (
                    <LogOut size={17} />
                  )}
                  Check Out
                </button>
              </>
            )}
          </div>
        </div>
      </section>

      {/* SUMMARY */}
      <section className="grid gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-slate-100 p-2.5 dark:bg-slate-800">
              <Users size={19} />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Team
              </p>

              <p className="text-2xl font-bold text-slate-950 dark:text-white">
                {loading ? "—" : presence.length}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-emerald-100 p-2.5 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
              <UserCheck size={19} />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Online
              </p>

              <p className="text-2xl font-bold text-slate-950 dark:text-white">
                {loading ? "—" : onlineCount}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-blue-100 p-2.5 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
              <Clock3 size={19} />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                At work
              </p>

              <p className="text-2xl font-bold text-slate-950 dark:text-white">
                {loading ? "—" : checkedInCount}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-amber-100 p-2.5 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
              <Clock3 size={19} />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Away
              </p>

              <p className="text-2xl font-bold text-slate-950 dark:text-white">
                {loading ? "—" : awayCount}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CURRENT BREAK */}
      {currentBreak && (
        <section className="rounded-2xl border border-purple-200 bg-purple-50 p-5 dark:border-purple-900/50 dark:bg-purple-950/20">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-purple-900 dark:text-purple-200">
                {getBreakLabel(currentBreak.break_type)} in progress
              </p>

              <p className="mt-1 text-sm text-purple-700 dark:text-purple-300">
                Started {formatDateTime(currentBreak.started_at)}
              </p>
            </div>

            <p className="text-sm font-medium text-purple-800 dark:text-purple-200">
              {formatElapsed(currentBreak.started_at)}
            </p>
          </div>
        </section>
      )}

      {/* TEAM PRESENCE */}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
          <h2 className="font-semibold text-slate-950 dark:text-white">
            Team Presence
          </h2>

          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Current availability across this funeral business.
          </p>
        </div>

        {loading ? (
          <div className="px-5 py-10 text-center text-sm text-slate-500">
            Loading staff presence...
          </div>
        ) : presence.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-slate-500">
            No staff presence records found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-950/40">
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
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40"
                  >
                    <td className="px-5 py-4 font-medium text-slate-950 dark:text-white">
                      {person.user_name}
                    </td>

                    <td className="px-5 py-4 capitalize text-slate-600 dark:text-slate-300">
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

                    <td className="px-5 py-4 text-slate-500 dark:text-slate-400">
                      {formatDateTime(person.last_seen_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="flex items-center gap-2 text-xs text-slate-400">
        <Clock3 size={14} />
        <span>
          Attendance status is updated automatically from your activity.
        </span>
      </div>
    </main>
  );
}
