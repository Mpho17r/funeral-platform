"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";

import { useParams, useRouter } from "next/navigation";
import axios from "axios";

import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

/* ============================================================
   TYPES
============================================================ */

type CaseTask = {
  id: string;
  business_id: string;
  case_id: string;
  title: string;
  description: string | null;
  status: "pending" | "in_progress" | "completed";
  due_date: string | null;
  due_at?: string | null;
  assigned_to: string | null;
  assignee_ids?: string[];
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

type User = {
  id: string;
  business_id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
};

type TaskForm = {
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed";
  due_date: string;
  due_time: string;
  assignee_ids: string[];
};

/* ============================================================
   HELPERS
============================================================ */

function getApiErrorStatus(err: unknown): number | undefined {
  return axios.isAxiosError(err) ? err.response?.status : undefined;
}

function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError<{ detail?: unknown }>(err)) {
    const detail = err.response?.data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      const messages = detail.map((item: unknown) => {
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
      });

      return messages.join(" ");
    }
  }

  return err instanceof Error ? err.message : fallback;
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

function isValidUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value
  );
}

function localDate(value: string) {
  const d = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function localTime(value: string) {
  const d = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/* ============================================================
   EMPTY FORM
============================================================ */

const emptyForm: TaskForm = {
  title: "",
  description: "",
  status: "pending",
  due_date: "",
  due_time: "",
  assignee_ids: [],
};

/* ============================================================
   MAIN PAGE
============================================================ */

export default function TasksPage() {
  const router = useRouter();
  const params = useParams();

  const caseId = String(params.case_id || "");

  const [tasks, setTasks] = useState<CaseTask[]>([]);
  const [users, setUsers] = useState<User[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [deletingId, setDeletingId] = useState<string | null>(
    null
  );

  const [pageError, setPageError] = useState("");
  const [formError, setFormError] = useState("");

  const [showForm, setShowForm] = useState(false);

  const [editingTask, setEditingTask] =
    useState<CaseTask | null>(null);

  const [form, setForm] = useState<TaskForm>(emptyForm);

  /* ==========================================================
     AUTH + INITIAL LOAD
  ========================================================== */

  const loadTasks = useCallback(async () => {
    try {
      setLoading(true);
      setPageError("");

      const response = await api.get<CaseTask[]>(
        `/cases/${caseId}/tasks`
      );

      setTasks(response.data);
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        getApiErrorMessage(err, "Unable to load case tasks.")
      );
    } finally {
      setLoading(false);
    }
  }, [caseId, router]);

  const loadUsers = useCallback(async () => {
    try {
      const response = await api.get<User[]>("/users");

      setUsers(
        response.data.filter(
          (user) =>
            user.is_active &&
            (user.role === "manager" || user.role === "staff")
        )
      );
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        router.push("/login");
        return;
      }

      setUsers([]);
    }
  }, [router]);

  useEffect(() => {
    async function initializeCaseTasks() {
      if (!isAuthenticated()) {
        router.push("/login");
        return;
      }

      if (!caseId) {
        setPageError("Case ID is missing from the URL.");
        setLoading(false);
        return;
      }

      if (!isValidUuid(caseId)) {
        setPageError(
          "Invalid case ID. Please open Tasks from an actual funeral case."
        );
        setLoading(false);
        return;
      }

      await Promise.all([loadTasks(), loadUsers()]);
    }

    void initializeCaseTasks();
  }, [caseId, router, loadTasks, loadUsers]);

  /* ==========================================================
     FORM HELPERS
  ========================================================== */

  function updateForm(
    field: keyof TaskForm,
    value: string
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function resetForm() {
    setForm(emptyForm);
    setFormError("");
    setEditingTask(null);
  }

  function openAddForm() {
    resetForm();
    setShowForm(true);
  }

  function openEditForm(task: CaseTask) {
    setEditingTask(task);

    setForm({
      title: task.title,
      description: task.description || "",
      status: task.status,
      due_date: task.due_at
        ? localDate(task.due_at)
        : task.due_date
          ? task.due_date.slice(0, 10)
          : "",
      due_time: task.due_at ? localTime(task.due_at) : "",
      assignee_ids:
        task.assignee_ids ?? (task.assigned_to ? [task.assigned_to] : []),
    });

    setFormError("");
    setShowForm(true);
  }

  function closeForm() {
    if (saving) {
      return;
    }

    setShowForm(false);
    resetForm();
  }

  /* ==========================================================
     CREATE / UPDATE TASK
  ========================================================== */

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setSaving(true);
    setFormError("");

    try {
      const title = form.title.trim();

      if (!title) {
        setFormError("Task title is required.");
        return;
      }

      const payload = {
        title,
        description:
          form.description.trim() || null,
        status: form.status,
        due_date: form.due_date && !form.due_time ? form.due_date : null,
        due_at:
          form.due_date && form.due_time
            ? new Date(`${form.due_date}T${form.due_time}`).toISOString()
            : null,
        assignee_ids: form.assignee_ids,
      };

      if (editingTask) {
        const response = await api.patch<CaseTask>(
          `/cases/tasks/${editingTask.id}`,
          payload
        );

        setTasks((current) =>
          current.map((task) =>
            task.id === editingTask.id
              ? response.data
              : task
          )
        );
      } else {
        const response = await api.post<CaseTask>(
          `/cases/${caseId}/tasks`,
          payload
        );

        setTasks((current) => [
          response.data,
          ...current,
        ]);
      }

      setShowForm(false);
      resetForm();
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        router.push("/login");
        return;
      }

      setFormError(
        getApiErrorMessage(
          err,
          editingTask
            ? "Unable to update task."
            : "Unable to create task."
        )
      );
    } finally {
      setSaving(false);
    }
  }

  /* ==========================================================
     DELETE TASK
  ========================================================== */

  async function handleDeleteTask(taskId: string) {
    const confirmed = window.confirm(
      "Are you sure you want to delete this task?"
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingId(taskId);
      setPageError("");

      await api.delete(`/cases/tasks/${taskId}`);

      setTasks((current) =>
        current.filter((task) => task.id !== taskId)
      );
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        getApiErrorMessage(
          err,
          "Unable to delete task."
        )
      );
    } finally {
      setDeletingId(null);
    }
  }

  /* ==========================================================
     SUMMARY
  ========================================================== */

  const summary = useMemo(() => {
    const total = tasks.length;

    const pending = tasks.filter(
      (task) => task.status === "pending"
    ).length;

    const inProgress = tasks.filter(
      (task) => task.status === "in_progress"
    ).length;

    const completed = tasks.filter(
      (task) => task.status === "completed"
    ).length;

    return {
      total,
      pending,
      inProgress,
      completed,
    };
  }, [tasks]);

  /* ==========================================================
     LOADING
  ========================================================== */

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--fos-surface-muted)]">
        <div className="flex items-center gap-3 text-sm text-[var(--fos-text-muted)]">
          <Loader2
            size={20}
            className="animate-spin"
          />
          Loading tasks...
        </div>
      </main>
    );
  }

  /* ==========================================================
     PAGE
  ========================================================== */

  return (
    <main className="min-h-screen bg-[var(--fos-surface-muted)]">
      {/* HEADER */}

      <header className="border-b bg-[var(--fos-surface)]">
        <div className="mx-auto max-w-7xl px-6 py-5 md:px-8">
          <button
            type="button"
            onClick={() =>
              router.push(`/cases/${caseId}`)
            }
            className="mb-5 flex items-center gap-2 text-sm font-medium text-[var(--fos-text-muted)] hover:text-[var(--fos-text)]"
          >
            <ArrowLeft size={17} />
            Back to Case
          </button>

          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-slate-900 p-3 text-white">
                <ClipboardList size={22} />
              </div>

              <div>
                <h1 className="text-2xl font-bold text-[var(--fos-text)]">
                  Tasks
                </h1>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                  Manage tasks and follow-ups for this
                  funeral case.
                </p>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={loadTasks}
                className="flex items-center justify-center gap-2 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-2.5 text-sm font-medium text-[var(--fos-text-secondary)] hover:bg-[var(--fos-page)]"
              >
                <RefreshCw size={16} />
                Refresh
              </button>

              <button
                type="button"
                onClick={openAddForm}
                className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                <Plus size={17} />
                Add Task
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* CONTENT */}

      <section className="mx-auto max-w-7xl p-6 md:p-8">
        {pageError && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-700">
              {pageError}
            </p>
          </div>
        )}

        {/* SUMMARY */}

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <SummaryCard
            title="Total Tasks"
            value={summary.total}
            description="Tasks on this case"
            icon={<ClipboardList size={20} />}
          />

          <SummaryCard
            title="Pending"
            value={summary.pending}
            description="Awaiting action"
            icon={<Loader2 size={20} />}
          />

          <SummaryCard
            title="In Progress"
            value={summary.inProgress}
            description="Currently being handled"
            icon={<RefreshCw size={20} />}
          />

          <SummaryCard
            title="Completed"
            value={summary.completed}
            description="Finished tasks"
            icon={<CheckCircle2 size={20} />}
          />
        </div>

        {/* TASK LIST */}

        <div className="mt-8 rounded-2xl border bg-[var(--fos-surface)] shadow-sm">
          <div className="border-b px-6 py-5">
            <h2 className="text-lg font-bold text-[var(--fos-text)]">
              Case Tasks
            </h2>

            <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
              Tasks and follow-ups associated with this
              case.
            </p>
          </div>

          {tasks.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--fos-surface-muted)] text-[var(--fos-text-muted)]">
                <ClipboardList size={25} />
              </div>

              <h3 className="mt-5 text-base font-semibold text-[var(--fos-text)]">
                No tasks yet
              </h3>

              <p className="mx-auto mt-2 max-w-md text-sm text-[var(--fos-text-muted)]">
                Add tasks and follow-ups required for
                this case.
              </p>

              <button
                type="button"
                onClick={openAddForm}
                className="mt-6 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                <Plus size={17} />
                Add First Task
              </button>
            </div>
          ) : (
            <div className="divide-y">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="p-6"
                >
                  <div className="flex flex-col justify-between gap-5 lg:flex-row">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="text-base font-bold text-[var(--fos-text)]">
                          {task.title}
                        </h3>

                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${getStatusClass(
                            task.status
                          )}`}
                        >
                          {formatStatus(task.status)}
                        </span>
                      </div>

                      {task.description && (
                        <p className="mt-3 text-sm text-[var(--fos-text-secondary)]">
                          {task.description}
                        </p>
                      )}

                      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        <InfoItem
                          label="Status"
                          value={formatStatus(
                            task.status
                          )}
                        />

                        <InfoItem
                          label="Due"
                          value={
                            task.due_at
                              ? new Date(task.due_at).toLocaleString("en-ZA", {
                                  day: "2-digit",
                                  month: "short",
                                  year: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : formatDate(task.due_date)
                          }
                        />

                        <InfoItem
                          label="Given To"
                          value={
                            (task.assignee_ids ??
                              (task.assigned_to ? [task.assigned_to] : [])
                            )
                              .map(
                                (id) =>
                                  users.find((user) => user.id === id)
                                    ?.full_name || "Colleague"
                              )
                              .join(", ") || "Unassigned"
                          }
                        />
                      </div>

                      {task.completed_at && (
                        <div className="mt-4 rounded-lg bg-emerald-50 p-4">
                          <p className="text-xs font-medium uppercase tracking-wide text-emerald-600">
                            Completed
                          </p>

                          <p className="mt-1 text-sm text-emerald-700">
                            {formatDate(
                              task.completed_at
                            )}
                          </p>
                        </div>
                      )}
                    </div>

                    <div className="flex items-start gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          openEditForm(task)
                        }
                        className="inline-flex items-center gap-2 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-2 text-sm font-medium text-[var(--fos-text-secondary)] hover:bg-[var(--fos-page)]"
                      >
                        <Pencil size={15} />
                        Edit
                      </button>

                      <button
                        type="button"
                        disabled={
                          deletingId === task.id
                        }
                        onClick={() =>
                          handleDeleteTask(task.id)
                        }
                        className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-[var(--fos-surface)] px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {deletingId === task.id ? (
                          <Loader2
                            size={15}
                            className="animate-spin"
                          />
                        ) : (
                          <Trash2 size={15} />
                        )}
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* FORM MODAL */}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/40 p-4">
          <div className="m-auto w-full max-w-2xl rounded-2xl bg-[var(--fos-surface)] shadow-xl">
            <div className="flex items-center justify-between border-b px-6 py-5">
              <div>
                <h2 className="text-lg font-bold text-[var(--fos-text)]">
                  {editingTask
                    ? "Edit Task"
                    : "Add Task"}
                </h2>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                  {editingTask
                    ? "Update the task details."
                    : "Create a task for this funeral case."}
                </p>
              </div>

              <button
                type="button"
                onClick={closeForm}
                disabled={saving}
                className="rounded-lg p-2 text-[var(--fos-text-muted)] hover:bg-[var(--fos-surface-muted)] hover:text-[var(--fos-text-secondary)]"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="space-y-5 p-6"
            >
              {formError && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3">
                  <p className="text-sm text-red-700">
                    {formError}
                  </p>
                </div>
              )}

              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                  Task Title
                </label>

                <input
                  type="text"
                  value={form.title}
                  onChange={(event) =>
                    updateForm(
                      "title",
                      event.target.value
                    )
                  }
                  placeholder="e.g. Confirm burial date"
                  maxLength={200}
                  required
                  className="w-full rounded-lg border border-[var(--fos-border)] px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                  Description
                </label>

                <textarea
                  value={form.description}
                  onChange={(event) =>
                    updateForm(
                      "description",
                      event.target.value
                    )
                  }
                  placeholder="Add any details about this task..."
                  rows={4}
                  className="w-full resize-none rounded-lg border border-[var(--fos-border)] px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                />
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Status
                  </label>

                  <select
                    value={form.status}
                    onChange={(event) =>
                      updateForm(
                        "status",
                        event.target.value
                      )
                    }
                    className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  >
                    <option value="pending">
                      Pending
                    </option>

                    <option value="in_progress">
                      In Progress
                    </option>

                    <option value="completed">
                      Completed
                    </option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Due Date
                  </label>

                  <input
                    type="date"
                    value={form.due_date}
                    onChange={(event) =>
                      updateForm(
                        "due_date",
                        event.target.value
                      )
                    }
                    className="w-full rounded-lg border border-[var(--fos-border)] px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  />
                  <input
                    type="time"
                    value={form.due_time}
                    onChange={(event) =>
                      updateForm("due_time", event.target.value)
                    }
                    aria-label="Due time"
                    className="mt-2 w-full rounded-lg border border-[var(--fos-border)] px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  />
                </div>
              </div>

              <div>
                <p className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                  Given to
                </p>
                <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border border-[var(--fos-border)] p-2">
                  {users.map((user) => (
                    <label
                      key={user.id}
                      className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-[var(--fos-page)]"
                    >
                      <input
                        type="checkbox"
                        checked={form.assignee_ids.includes(user.id)}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            assignee_ids: event.target.checked
                              ? [...current.assignee_ids, user.id]
                              : current.assignee_ids.filter(
                                  (id) => id !== user.id
                                ),
                          }))
                        }
                      />
                      {user.full_name} ({user.role})
                    </label>
                  ))}
                </div>
                <p className="mt-1.5 text-xs text-[var(--fos-text-muted)]">
                  Tick more than one person to share the task. Each of them
                  is alerted and can update its status, write a report and
                  upload files.
                </p>
              </div>
              <div className="flex justify-end gap-3 border-t pt-5">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={saving}
                  className="rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-2.5 text-sm font-medium text-[var(--fos-text-secondary)] hover:bg-[var(--fos-page)] disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving && (
                    <Loader2
                      size={16}
                      className="animate-spin"
                    />
                  )}

                  {editingTask
                    ? "Save Changes"
                    : "Add Task"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

/* ============================================================
   COMPONENTS
============================================================ */

function SummaryCard({
  title,
  value,
  description,
  icon,
}: {
  title: string;
  value: string | number;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border bg-[var(--fos-surface)] p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-[var(--fos-text-muted)]">
            {title}
          </p>

          <p className="mt-2 text-2xl font-bold text-[var(--fos-text)]">
            {value}
          </p>

          <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
            {description}
          </p>
        </div>

        <div className="rounded-xl bg-[var(--fos-surface-muted)] p-3 text-[var(--fos-text-secondary)]">
          {icon}
        </div>
      </div>
    </div>
  );
}

function InfoItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
        {label}
      </p>

      <p className="mt-1 text-sm font-medium text-[var(--fos-text-secondary)]">
        {value}
      </p>
    </div>
  );
}