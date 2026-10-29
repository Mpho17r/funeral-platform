"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { Dialog, inputClass } from "@/components/Dialog";

type Person = { id: string; name: string; role: string };

/** Give a service to one or more people, with an optional due time. */
export default function ServiceAssignDialog({
  serviceId,
  serviceName,
  current,
  dueAt,
  onClose,
  onSaved,
}: {
  serviceId: string;
  serviceName: string;
  current: string[];
  dueAt: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [chosen, setChosen] = useState<string[]>(current);
  const [due, setDue] = useState(dueAt ? toLocalInput(dueAt) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Person[]>("/service-work/people")
      .then((r) => setPeople(r.data))
      .catch((err) => setError(getApiErrorMessage(err, "Could not load your team.")));
  }, []);

  function toggle(id: string) {
    setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  }

  async function save() {
    try {
      setBusy(true);
      setError("");
      await api.post(`/service-work/${serviceId}/assign`, {
        assignee_ids: chosen,
        due_at: due ? new Date(due).toISOString() : null,
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save that."));
      setBusy(false);
    }
  }

  return (
    <Dialog title={`Who is responsible for ${serviceName}?`} onClose={onClose}>
      <p className="mb-3 text-sm text-slate-600">
        Choose one or more people. Each is told, and keeps the status up to date.
      </p>
      {error && <p className="mb-3 text-sm text-red-700">{error}</p>}
      {people === null ? (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={15} className="animate-spin" /> Loading…
        </p>
      ) : (
        <ul className="max-h-60 space-y-1 overflow-y-auto rounded-lg border p-2">
          {people.map((p) => (
            <li key={p.id}>
              <label className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-slate-50">
                <input
                  type="checkbox"
                  checked={chosen.includes(p.id)}
                  onChange={() => toggle(p.id)}
                />
                <span className="flex-1">{p.name}</span>
                <span className="text-xs text-slate-500">{p.role.replace("_", " ")}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <label className="mt-4 block text-sm font-medium text-slate-700">
        Due (optional)
        <input
          type="datetime-local"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          className={`${inputClass} mt-1`}
        />
      </label>
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">
          Cancel
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void save()}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </Dialog>
  );
}

function toLocalInput(iso: string) {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
