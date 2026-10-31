"use client";

import { FormEvent, useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { Dialog } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Person = {
  id: string;
  name: string;
  job_title: string | null;
  detected: string[];
  open: number;
  present: boolean;
};

/** A task for a general business. KAI can choose who does it: it reads
 *  what the task needs, then looks at each person's job title and role. */
export default function NewWorkTaskDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");
  const [kai, setKai] = useState(true);
  const [chosen, setChosen] = useState<string[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Person[]>("/work/people")
      .then((r) => setPeople(r.data))
      .catch(() => setPeople([]));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setBusy(true);
      setError("");
      const r = await api.post<{
        assignees: string[];
        chosen_by_kai: boolean;
        reason: string | null;
      }>("/work/tasks", {
        title,
        description: description.trim() || null,
        due_at: due ? new Date(due).toISOString() : null,
        assignee_ids: kai ? [] : chosen,
        let_kai_choose: kai,
      });
      const who = r.data.assignees.join(", ");
      onSaved(
        r.data.chosen_by_kai
          ? `KAI gave it to ${who}. ${r.data.reason ?? ""}`
          : who
            ? `Task given to ${who}.`
            : "Task created. Nobody is responsible for it yet.",
      );
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not create the task."));
      setBusy(false);
    }
  }

  const input = "w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-slate-900";
  return (
    <Dialog title="New task" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <label className="block text-sm">
          What needs doing?
          <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} placeholder="Chase the supplier invoices" />
        </label>
        <label className="block text-sm">
          Details (optional)
          <textarea className={input} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={4000} />
        </label>
        <label className="block text-sm">
          Due (optional)
          <input className={input} type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>

        <label className="flex items-start gap-2 rounded-lg bg-slate-50 p-3 text-sm">
          <input type="checkbox" className="mt-1" checked={kai} onChange={(e) => setKai(e.target.checked)} />
          <span>
            <span className="flex items-center gap-1 font-medium text-slate-900">
              <Sparkles size={14} /> Let KAI choose who does it
            </span>
            <span className="text-xs text-slate-500">
              KAI works out what kind of job this is, matches it to people&apos;s job titles and roles, then prefers whoever has the least on.
            </span>
          </span>
        </label>

        {!kai && (
          <fieldset className="space-y-1 text-sm">
            <legend className="mb-1 font-medium">Give it to</legend>
            {people.map((p) => (
              <label key={p.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={chosen.includes(p.id)}
                  onChange={(e) =>
                    setChosen((c) => (e.target.checked ? [...c, p.id] : c.filter((x) => x !== p.id)))
                  }
                />
                <span>
                  {p.name}
                  {p.job_title ? <span className="text-slate-500"> · {p.job_title}</span> : null}
                  <span className="text-xs text-slate-500"> · {p.open} open</span>
                </span>
              </label>
            ))}
            <p className="text-xs text-slate-500">Choose more than one to share the task.</p>
          </fieldset>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">
            Cancel
          </button>
          <button type="submit" disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
            {busy ? "Creating…" : "Create task"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
