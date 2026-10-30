"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Check, Loader2, Play, Undo2, X } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";

type Settings = {
  mode: "off" | "suggest" | "auto";
  create_tasks: boolean;
  assign: boolean;
  escalate: boolean;
  max_open: number;
  can_change: boolean;
};
type Item = {
  id: string;
  kind: string;
  status: string;
  summary: string;
  reason: string | null;
  case_id: string | null;
  created_at: string;
  can_undo: boolean;
};
type Workload = {
  max_open: number;
  people: { id: string; name: string; role: string; open: number; present: boolean }[];
};

const MODES: { value: Settings["mode"]; title: string; body: string }[] = [
  { value: "off", title: "Off", body: "KAI does not hand out or create work. People do it, as before." },
  {
    value: "suggest",
    title: "Suggest",
    body: "KAI works out what should happen and who should do it, then waits for a manager to approve each item.",
  },
  {
    value: "auto",
    title: "Auto",
    body: "KAI does it on its own and logs every step. Each one can be undone here.",
  },
];

function when(iso: string) {
  return new Date(iso).toLocaleString("en-ZA", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AutopilotPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [pending, setPending] = useState<Item[]>([]);
  const [done, setDone] = useState<Item[]>([]);
  const [load, setLoad] = useState<Workload | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Settings>("/autopilot/settings"),
      api.get<Item[]>("/autopilot/items", { params: { status: "pending" } }),
      api.get<Item[]>("/autopilot/items", { params: { status: "done", limit: 40 } }),
      api.get<Workload>("/autopilot/workload"),
    ])
      .then(([s, p, d, w]) => {
        setSettings(s.data);
        setDraft((cur) => cur ?? s.data);
        setPending(p.data);
        setDone(d.data);
        setLoad(w.data);
      })
      .catch((err) => setError(getApiErrorMessage(err, "Could not load KAI Autopilot.")));
  }, [version]);

  async function act(id: string, action: "approve" | "dismiss" | "undo") {
    try {
      setBusy(id);
      setError("");
      await api.post(`/autopilot/items/${id}/${action}`);
      setVersion((v) => v + 1);
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not go through."));
      setVersion((v) => v + 1);
    } finally {
      setBusy("");
    }
  }

  async function save() {
    if (!draft) return;
    try {
      setBusy("save");
      setError("");
      const r = await api.put<Settings>("/autopilot/settings", draft);
      setSettings(r.data);
      setDraft(r.data);
      setNotice("Saved.");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
    } finally {
      setBusy("");
    }
  }

  async function runNow() {
    try {
      setBusy("run");
      setError("");
      const r = await api.post<{ proposed: number; applied: number }>("/autopilot/run");
      setNotice(
        r.data.applied
          ? `KAI handled ${r.data.applied} thing(s).`
          : r.data.proposed
            ? `KAI has ${r.data.proposed} new suggestion(s) for you.`
            : "Nothing needs doing right now.",
      );
      setVersion((v) => v + 1);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not run."));
    } finally {
      setBusy("");
    }
  }

  if (!settings || !draft) {
    return (
      <main className="p-6">
        {error ? <ErrorNote message={error} /> : <Loader2 className="animate-spin" size={18} />}
      </main>
    );
  }

  const editable = settings.can_change;
  const dirty = JSON.stringify(settings) !== JSON.stringify(draft);

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <header className="flex items-center gap-3">
        <div className="rounded-xl bg-slate-900 p-3 text-white">
          <Bot size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">KAI Autopilot</h1>
          <p className="text-sm text-slate-500">
            KAI as your platform manager: it sets up the work a case needs and gives it to the right person.
          </p>
        </div>
      </header>

      {error && <ErrorNote message={error} />}
      {notice && (
        <p role="status" className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
          {notice}
        </p>
      )}

      <section className="space-y-3 rounded-xl border bg-white p-4">
        <h2 className="font-semibold text-slate-900">How much may KAI do?</h2>
        <div className="grid gap-2 sm:grid-cols-3">
          {MODES.map((m) => (
            <button
              key={m.value}
              type="button"
              disabled={!editable}
              onClick={() => setDraft({ ...draft, mode: m.value })}
              className={`rounded-xl border p-3 text-left disabled:cursor-default ${
                draft.mode === m.value ? "border-slate-900 bg-slate-900 text-white" : "hover:bg-slate-50"
              }`}
            >
              <p className="font-semibold">{m.title}</p>
              <p className={`mt-1 text-xs ${draft.mode === m.value ? "text-slate-200" : "text-slate-500"}`}>
                {m.body}
              </p>
            </button>
          ))}
        </div>

        {draft.mode !== "off" && (
          <div className="space-y-2 pt-1 text-sm text-slate-700">
            {(
              [
                ["create_tasks", "Create the tasks each case still needs (death record, paperwork, vehicle, drivers, payment follow-up, closing a finished case)"],
                ["assign", "Give unassigned tasks and services to the best person (lightest workload, in today, right branch and work area)"],
                ["escalate", "Tell managers when work is more than 12 hours late"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="flex items-start gap-2">
                <input
                  type="checkbox"
                  disabled={!editable}
                  checked={draft[key]}
                  onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })}
                  className="mt-1"
                />
                {label}
              </label>
            ))}
            <label className="flex items-center gap-2">
              Nobody is given more than
              <input
                type="number"
                min={1}
                max={50}
                disabled={!editable}
                value={draft.max_open}
                onChange={(e) => setDraft({ ...draft, max_open: Number(e.target.value) || 1 })}
                className="w-16 rounded-lg border px-2 py-1"
              />
              open tasks and services
            </label>
          </div>
        )}

        <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
          KAI can never delete anything, change money, message a family, change a case&apos;s status or change anyone&apos;s
          access. Everything it does is an ordinary task or assignment that people can edit, and it is written to the audit log.
        </p>

        {editable ? (
          <button
            type="button"
            disabled={!dirty || busy === "save"}
            onClick={() => void save()}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Save
          </button>
        ) : (
          <p className="text-xs text-slate-500">Only the Main Admin can change these settings.</p>
        )}
      </section>

      {settings.mode !== "off" && (
        <>
          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold text-slate-900">
                {settings.mode === "suggest" ? "Waiting for your approval" : "Needs a look"}
              </h2>
              <button
                type="button"
                disabled={busy === "run"}
                onClick={() => void runNow()}
                className="flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                {busy === "run" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                Check now
              </button>
            </div>
            {pending.length === 0 ? (
              <p className="rounded-xl border border-dashed p-5 text-center text-sm text-slate-500">
                Nothing is waiting. KAI checks every 15 minutes.
              </p>
            ) : (
              <ul className="divide-y rounded-xl border bg-white">
                {pending.map((i) => (
                  <li key={i.id} className="flex flex-wrap items-center gap-3 p-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-900">{i.summary}</p>
                      {i.reason && <p className="text-xs text-slate-500">Why: {i.reason}</p>}
                    </div>
                    <button
                      type="button"
                      disabled={busy === i.id}
                      onClick={() => void act(i.id, "approve")}
                      className="flex items-center gap-1 rounded-lg bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-60"
                    >
                      <Check size={14} /> Approve
                    </button>
                    <button
                      type="button"
                      disabled={busy === i.id}
                      onClick={() => void act(i.id, "dismiss")}
                      className="flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm text-slate-700 disabled:opacity-60"
                    >
                      <X size={14} /> Not needed
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="font-semibold text-slate-900">What KAI has done</h2>
            {done.length === 0 ? (
              <p className="text-sm text-slate-500">Nothing yet.</p>
            ) : (
              <ul className="divide-y rounded-xl border bg-white">
                {done.map((i) => (
                  <li key={i.id} className="flex flex-wrap items-center gap-3 p-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-slate-900">{i.summary}</p>
                      <p className="text-xs text-slate-500">
                        {i.status === "applied"
                          ? "KAI did this"
                          : i.status === "approved"
                            ? "Approved"
                            : i.status === "undone"
                              ? "Undone"
                              : "Dismissed"}{" "}
                        · {when(i.created_at)}
                        {i.case_id && (
                          <>
                            {" · "}
                            <Link href={`/cases/${i.case_id}`} className="hover:underline">
                              open case
                            </Link>
                          </>
                        )}
                      </p>
                    </div>
                    {i.can_undo && (
                      <button
                        type="button"
                        disabled={busy === i.id}
                        onClick={() => void act(i.id, "undo")}
                        className="flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                      >
                        <Undo2 size={14} /> Undo
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      {load && (
        <section className="space-y-3">
          <h2 className="font-semibold text-slate-900">Who has what</h2>
          <ul className="space-y-2 rounded-xl border bg-white p-4">
            {load.people.map((p) => (
              <li key={p.id} className="flex items-center gap-3 text-sm">
                <span className="w-40 truncate text-slate-800">
                  {p.name}
                  {p.present && <span className="ml-1 text-xs text-emerald-600">● in</span>}
                </span>
                <span className="h-2 flex-1 overflow-hidden rounded bg-slate-100">
                  <span
                    className={`block h-full ${p.open >= load.max_open ? "bg-red-500" : "bg-slate-800"}`}
                    style={{ width: `${Math.min(100, (p.open / load.max_open) * 100)}%` }}
                  />
                </span>
                <span className="w-8 text-right tabular-nums text-slate-600">{p.open}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
