"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ClipboardList, Loader2, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
import axios from "axios";
import { isAuthenticated } from "@/lib/auth";

type WorkspaceTask = {
  id: string;
  business_id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  title: string;
  description: string | null;
  status: "pending" | "in_progress" | "completed";
  due_date: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

type ApiErrorResponse = {
  detail?: unknown;
};

function getApiErrorMessage(err: unknown, fallback: string): string {
  const detail = axios.isAxiosError<ApiErrorResponse>(err)
    ? err.response?.data?.detail
    : undefined;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (typeof item === "string") {
          return item;
        }

        if (
          item !== null &&
          typeof item === "object" &&
          "msg" in item &&
          typeof item.msg === "string"
        ) {
          return item.msg;
        }

        return "Invalid request.";
      })
      .join(" ");
  }

  if (err instanceof Error && typeof err.message === "string") {
    return err.message;
  }

  return fallback;
}

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null) {
  if (!value) {
    return "No due date";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getStatusClass(status: string) {
  switch (status) {
    case "completed":
      return "bg-emerald-50 text-emerald-700";
    case "in_progress":
      return "bg-blue-50 text-blue-700";
    case "pending":
    default:
      return "bg-amber-50 text-amber-700";
  }
}

export default function TasksWorkspacePage() {
  const router = useRouter();

  const [tasks, setTasks] = useState<WorkspaceTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [assigneeFilter, setAssigneeFilter] = useState("all");

  const loadTasks = useCallback(async () => {
    try {
      setLoading(true);
      setPageError("");
      const response = await api.get<WorkspaceTask[]>("/tasks");
      setTasks(response.data);
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        getApiErrorMessage(
          err,
          "Unable to load the task workspace."
        )
      );
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    async function initializeTasks() {
      if (!isAuthenticated()) {
        router.push("/login");
        return;
      }

      await loadTasks();
    }

    void initializeTasks();
  }, [router, loadTasks]);

  const assignees = useMemo(() => {
    const names = tasks
      .map((task) => task.assigned_to_name)
      .filter((name): name is string => Boolean(name));

    return Array.from(new Set(names)).sort();
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      const matchesStatus =
        statusFilter === "all" ||
        task.status === statusFilter;

      const matchesAssignee =
        assigneeFilter === "all" ||
        task.assigned_to_name === assigneeFilter;

      return matchesStatus && matchesAssignee;
    });
  }, [tasks, statusFilter, assigneeFilter]);

  return (
    <main className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-[var(--fos-surface-muted)] p-3">
              <ClipboardList className="h-6 w-6 text-[var(--fos-text-secondary)]" />
            </div>

            <div>
              <h1 className="text-2xl font-semibold text-[var(--fos-text)]">
                Tasks
              </h1>
              <p className="text-sm text-[var(--fos-text-muted)]">
                Business-wide task workspace
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={loadTasks}
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-2 text-sm font-medium text-[var(--fos-text-secondary)] shadow-sm transition hover:bg-[var(--fos-page)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <section className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-4 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-end">
          <div className="w-full md:w-56">
            <label
              htmlFor="status-filter"
              className="mb-1 block text-sm font-medium text-[var(--fos-text-secondary)]"
            >
              Status
            </label>

            <select
              id="status-filter"
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value)
              }
              className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-2 text-sm outline-none focus:border-slate-500"
            >
              <option value="all">All statuses</option>
              <option value="pending">Pending</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
            </select>
          </div>

          <div className="w-full md:w-64">
            <label
              htmlFor="assignee-filter"
              className="mb-1 block text-sm font-medium text-[var(--fos-text-secondary)]"
            >
              Assigned to
            </label>

            <select
              id="assignee-filter"
              value={assigneeFilter}
              onChange={(event) =>
                setAssigneeFilter(event.target.value)
              }
              className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-2 text-sm outline-none focus:border-slate-500"
            >
              <option value="all">Everyone</option>

              {assignees.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div className="text-sm text-[var(--fos-text-muted)]">
            Showing{" "}
            <span className="font-semibold text-[var(--fos-text)]">
              {filteredTasks.length}
            </span>{" "}
            of{" "}
            <span className="font-semibold text-[var(--fos-text)]">
              {tasks.length}
            </span>{" "}
            tasks
          </div>
        </div>
      </section>

      {pageError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {pageError}
        </div>
      )}

      <section className="overflow-hidden rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-[var(--fos-text-muted)]">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading tasks...
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <ClipboardList className="mx-auto mb-3 h-10 w-10 text-slate-300" />
            <h2 className="text-lg font-semibold text-[var(--fos-text)]">
              No tasks found
            </h2>
            <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
              There are no tasks matching the current filters.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-[var(--fos-page)]">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Task
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Case
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Assigned to
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Due
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Status
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {filteredTasks.map((task) => (
                  <tr
                    key={task.id}
                    className="transition hover:bg-[var(--fos-page)]"
                  >
                    <td className="px-6 py-4">
                      <div className="font-medium text-[var(--fos-text)]">
                        {task.title}
                      </div>

                      {task.description && (
                        <div className="mt-1 max-w-md text-sm text-[var(--fos-text-muted)]">
                          {task.description}
                        </div>
                      )}
                    </td>

                    <td className="px-6 py-4">
                      <button
                        type="button"
                        onClick={() =>
                          router.push(
                            `/cases/${task.case_id}`
                          )
                        }
                        className="text-left"
                      >
                        <div className="font-medium text-[var(--fos-text)] hover:underline">
                          {task.case_number}
                        </div>
                        <div className="text-sm text-[var(--fos-text-muted)]">
                          {task.deceased_full_name}
                        </div>
                      </button>
                    </td>

                    <td className="px-6 py-4 text-sm text-[var(--fos-text-secondary)]">
                      {task.assigned_to_name || "Unassigned"}
                    </td>

                    <td className="px-6 py-4 text-sm text-[var(--fos-text-secondary)]">
                      {formatDate(task.due_date)}
                    </td>

                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusClass(
                          task.status
                        )}`}
                      >
                        {formatStatus(task.status)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
