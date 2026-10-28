"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FileText, Loader2, Paperclip, Send, Trash2, Users, X } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";

export type TaskStatus = "pending" | "in_progress" | "completed";

export type TaskEntry = {
  id: string;
  kind: "report" | "file";
  text: string | null;
  file_name: string | null;
  size_bytes: number | null;
  author_id: string | null;
  author: string;
  created_at: string;
};

export type TaskDetail = {
  id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  due_at: string | null;
  due_date: string | null;
  assignees: { id: string; name: string }[];
  shared: boolean;
  created_at: string;
  completed_at: string | null;
  entries: TaskEntry[];
  can_update: boolean;
};

export const STATUS_LABEL: Record<TaskStatus, string> = {
  pending: "Not started",
  in_progress: "In progress",
  completed: "Done",
};

export function whenDue(due_at: string | null, due_date: string | null) {
  if (due_at) {
    return new Date(due_at).toLocaleString("en-ZA", {
      weekday: "short",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  if (due_date) {
    return new Date(`${due_date}T00:00:00`).toLocaleDateString("en-ZA", {
      weekday: "short",
      day: "2-digit",
      month: "short",
    });
  }
  return "No due date";
}

function size(bytes: number | null) {
  if (!bytes) return "";
  return bytes > 1048576
    ? `${(bytes / 1048576).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function TaskDrawer({
  taskId,
  meId,
  onClose,
  onChanged,
}: {
  taskId: string;
  meId?: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState("");
  const [now] = useState(() => Date.now());
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    return api
      .get<TaskDetail>(`/tasks/${taskId}`)
      .then((r) => setTask(r.data))
      .catch((err) => setError(getApiErrorMessage(err, "Could not open this task.")));
  }, [taskId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(work: () => Promise<unknown>, failure: string) {
    try {
      setBusy(true);
      setError("");
      await work();
      await load();
      onChanged();
    } catch (err) {
      setError(getApiErrorMessage(err, failure));
    } finally {
      setBusy(false);
    }
  }

  function setStatus(status: TaskStatus) {
    void run(() => api.post(`/tasks/${taskId}/status`, { status }), "Could not change the status.");
  }

  function sendReport() {
    const text = report.trim();
    if (!text) return;
    void run(async () => {
      await api.post(`/tasks/${taskId}/report`, { text });
      setReport("");
    }, "Could not save the report.");
  }

  function upload(file: File | undefined) {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    void run(
      () => api.post(`/tasks/${taskId}/files`, form, { headers: { "Content-Type": "multipart/form-data" } }),
      "Could not upload the file.",
    );
    if (fileInput.current) fileInput.current.value = "";
  }

  async function download(entry: TaskEntry) {
    try {
      const r = await api.get(`/tasks/${taskId}/files/${entry.id}`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = entry.file_name || "file";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not download the file."));
    }
  }

  const overdue =
    task &&
    task.status !== "completed" &&
    (task.due_at
      ? new Date(task.due_at).getTime() < now
      : task.due_date
        ? new Date(`${task.due_date}T23:59:59`).getTime() < now
        : false);

  return (
    <div className="fixed inset-0 z-[150] flex justify-end bg-slate-900/40" onClick={onClose}>
      <aside
        role="dialog"
        aria-label="Task"
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b p-5">
          <div>
            <p className="text-xs text-slate-500">
              {task ? `${task.deceased_full_name} · ${task.case_number}` : "Task"}
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">{task?.title ?? "…"}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded p-1 text-slate-500 hover:bg-slate-100">
            <X size={18} />
          </button>
        </header>

        <div className="space-y-5 p-5">
          {error && <ErrorNote message={error} />}
          {!task && !error && <Loader2 className="animate-spin text-slate-400" />}

          {task && (
            <>
              {task.description && <p className="whitespace-pre-wrap text-sm text-slate-700">{task.description}</p>}

              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-slate-500">Given</dt>
                  <dd>{new Date(task.created_at).toLocaleString("en-ZA", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Due</dt>
                  <dd className={overdue ? "font-semibold text-red-600" : ""}>
                    {whenDue(task.due_at, task.due_date)}
                    {overdue ? " · overdue" : ""}
                  </dd>
                </div>
              </dl>

              <div>
                <p className="mb-1 flex items-center gap-1 text-xs text-slate-500">
                  <Users size={13} /> {task.shared ? "Shared by" : "Given to"}
                </p>
                <div className="flex flex-wrap gap-2">
                  {task.assignees.length === 0 && <span className="text-sm text-slate-500">Nobody yet</span>}
                  {task.assignees.map((a) => (
                    <span key={a.id} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                      {a.name}
                      {a.id === meId ? " (you)" : ""}
                    </span>
                  ))}
                </div>
                {task.shared && (
                  <p className="mt-1 text-xs text-slate-500">Everyone it is shared with can update it, and is told when it changes.</p>
                )}
              </div>

              <div>
                <p className="mb-1 text-xs text-slate-500">Status</p>
                <div className="flex flex-wrap gap-2">
                  {(["pending", "in_progress", "completed"] as TaskStatus[]).map((s) => (
                    <button
                      key={s}
                      type="button"
                      disabled={!task.can_update || busy}
                      onClick={() => setStatus(s)}
                      className={`rounded-lg border px-3 py-1.5 text-sm disabled:opacity-60 ${
                        task.status === s ? "border-slate-900 bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      {STATUS_LABEL[s]}
                    </button>
                  ))}
                </div>
                {!task.can_update && <p className="mt-1 text-xs text-slate-500">This task is not given to you, so you can only read it.</p>}
                {task.can_update && task.status === "completed" && (
                  <div className="mt-3 flex items-center gap-3">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        void run(() => api.post(`/archive/tasks/${taskId}/archive`), "Could not archive the task.").then(onClose);
                      }}
                      className="rounded-lg border px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    >
                      Archive this task
                    </button>
                    <p className="text-xs text-slate-500">Finished tasks are archived automatically after a while.</p>
                  </div>
                )}
              </div>

              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">Reports and files</h3>
                {task.entries.length === 0 && <p className="text-sm text-slate-500">Nothing yet.</p>}
                <ul className="space-y-3">
                  {task.entries.map((e) => (
                    <li key={e.id} className="rounded-xl border p-3 text-sm">
                      <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
                        <span>
                          {e.author} ·{" "}
                          {new Date(e.created_at).toLocaleString("en-ZA", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                        </span>
                        {e.author_id === meId && (
                          <button
                            type="button"
                            aria-label="Remove"
                            onClick={() => void run(() => api.delete(`/tasks/${taskId}/entries/${e.id}`), "Could not remove it.")}
                            className="text-slate-400 hover:text-red-600"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                      {e.kind === "report" ? (
                        <p className="mt-1 whitespace-pre-wrap">{e.text}</p>
                      ) : (
                        <button type="button" onClick={() => void download(e)} className="mt-1 flex items-center gap-2 text-slate-800 hover:underline">
                          <FileText size={16} /> {e.file_name} <span className="text-xs text-slate-500">{size(e.size_bytes)}</span>
                        </button>
                      )}
                    </li>
                  ))}
                </ul>

                {task.can_update && (
                  <div className="mt-3 space-y-2">
                    <textarea
                      value={report}
                      onChange={(e) => setReport(e.target.value)}
                      rows={3}
                      maxLength={5000}
                      placeholder="Write a report on what you did…"
                      className="w-full rounded-lg border border-slate-300 p-3 text-sm outline-none focus:border-slate-900"
                    />
                    <div className="flex items-center justify-between gap-2">
                      <label className="flex cursor-pointer items-center gap-1 rounded-lg border px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                        <Paperclip size={15} /> Upload a file
                        <input ref={fileInput} type="file" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
                      </label>
                      <button
                        type="button"
                        disabled={busy || !report.trim()}
                        onClick={sendReport}
                        className="flex items-center gap-1 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                      >
                        <Send size={14} /> Save report
                      </button>
                    </div>
                    <p className="text-xs text-slate-500">PDF, pictures, Word, Excel, text or audio, up to 15 MB.</p>
                  </div>
                )}
              </section>

              <Link href={`/cases/${task.case_id}`} className="block text-sm text-slate-700 underline">
                Open the case
              </Link>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
