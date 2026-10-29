"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Archive, Loader2, RotateCcw, Search, Trash2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";
import { useCurrentUser } from "@/components/CurrentUserProvider";

type Kind = "cases" | "tasks" | "services";
type Item = {
  id: string;
  title: string;
  subtitle: string;
  status: string;
  archived_at: string;
  href: string;
};
type Settings = {
  archive_after_days: number;
  delete_archived_after_months: number | null;
  can_change: boolean;
};

const RETENTION: { value: string; label: string }[] = [
  { value: "", label: "Never delete" },
  { value: "1", label: "After 1 month" },
  { value: "3", label: "After 3 months" },
  { value: "6", label: "After 6 months" },
  { value: "12", label: "After 1 year" },
  { value: "24", label: "After 2 years" },
  { value: "60", label: "After 5 years" },
  { value: "84", label: "After 7 years" },
  { value: "120", label: "After 10 years" },
];

function day(iso: string) {
  return new Date(iso).toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function ArchiveView() {
  const { can, user } = useCurrentUser();
  const params = useSearchParams();
  const isMainAdmin = user?.role === "main_admin";
  const canCases = can("cases.view");
  const asked = params.get("kind");
  const first: Kind =
    asked === "services" ? "services" : asked === "tasks" || !canCases ? "tasks" : "cases";

  const [kind, setKind] = useState<Kind>(first);
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Item[] | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [days, setDays] = useState("14");
  const [months, setMonths] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const [version, setVersion] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api
        .get<Item[]>("/archive", { params: { kind, q: q.trim() || undefined } })
        .then((r) => setItems(r.data))
        .catch((err) => setError(getApiErrorMessage(err, "Could not load the archive.")));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [kind, q, version]);

  useEffect(() => {
    api
      .get<Settings>("/archive/settings")
      .then((r) => {
        setSettings(r.data);
        setDays(String(r.data.archive_after_days));
        setMonths(r.data.delete_archived_after_months ? String(r.data.delete_archived_after_months) : "");
      })
      .catch(() => setSettings(null));
  }, []);

  async function restore(item: Item) {
    try {
      setBusy(true);
      setError("");
      await (kind === "cases"
        ? api.post(`/cases/${item.id}/restore`)
        : api.post(`/archive/${kind}/${item.id}/restore`));
      setNotice(`"${item.title}" is back in your lists.`);
      setVersion((v) => v + 1);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not restore that."));
    } finally {
      setBusy(false);
    }
  }

  async function destroy(item: Item) {
    const typed = window.prompt(
      `Delete "${item.title}" for good? This cannot be undone.\n\nType DELETE to confirm.`,
    );
    if (typed !== "DELETE") return;
    try {
      setBusy(true);
      setError("");
      await api.delete(`/archive/${kind}/${item.id}`);
      setNotice(`"${item.title}" was deleted.`);
      setVersion((v) => v + 1);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not delete that."));
    } finally {
      setBusy(false);
    }
  }

  async function saveSettings() {
    try {
      setBusy(true);
      setError("");
      const r = await api.put<Settings>("/archive/settings", {
        archive_after_days: Number(days),
        delete_archived_after_months: months ? Number(months) : null,
      });
      setSettings(r.data);
      setNotice("Archive settings saved.");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save the settings."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <header className="flex items-center gap-3">
        <div className="rounded-xl bg-slate-900 p-3 text-white">
          <Archive size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Archive</h1>
          <p className="text-sm text-slate-500">
            Finished work is kept here, out of the way. Nothing in the archive needs attention.
          </p>
        </div>
      </header>

      {error && <ErrorNote message={error} />}
      {notice && (
        <p role="status" className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
          {notice}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {(["cases", "tasks", "services"] as Kind[])
          .filter((k) => k !== "cases" || canCases)
          .map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => {
                setItems(null);
                setKind(k);
              }}
              className={`rounded-full px-4 py-1.5 text-sm ${kind === k ? "bg-slate-900 text-white" : "border text-slate-700 hover:bg-slate-50"}`}
            >
              {k === "cases" ? "Cases" : k === "tasks" ? "Tasks" : "Services"}
            </button>
          ))}
        <div className="relative ml-auto min-w-48 flex-1 sm:max-w-xs">
          <Search size={15} className="absolute left-3 top-3 text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={kind === "cases" ? "Search name or case number" : `Search ${kind}`}
            className="w-full rounded-lg border px-9 py-2 text-sm outline-none focus:border-slate-900"
          />
        </div>
      </div>

      {items === null ? (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </p>
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-dashed p-6 text-center text-sm text-slate-500">
          Nothing archived {q ? "matches that search" : "yet"}.
        </p>
      ) : (
        <ul className="divide-y rounded-xl border bg-white">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center gap-3 p-3">
              <div className="min-w-0 flex-1">
                <Link href={item.href} className="block truncate font-medium text-slate-900 hover:underline">
                  {item.title}
                </Link>
                <p className="text-xs text-slate-500">
                  {item.subtitle} · {item.status.replace("_", " ")} · archived {day(item.archived_at)}
                </p>
              </div>
              {(kind !== "cases" || can("cases.restore")) && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void restore(item)}
                  className="flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                >
                  <RotateCcw size={14} /> Restore
                </button>
              )}
              {isMainAdmin && kind !== "services" && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void destroy(item)}
                  aria-label={`Delete ${item.title} for good`}
                  className="rounded-lg p-2 text-red-700 hover:bg-red-50 disabled:opacity-60"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {settings && (
        <section className="space-y-3 rounded-xl border bg-white p-4">
          <h2 className="font-semibold text-slate-900">How the archive works</h2>
          <label className="block text-sm text-slate-700">
            Archive finished cases and tasks automatically after
            <select
              value={days}
              disabled={!settings.can_change}
              onChange={(e) => setDays(e.target.value)}
              className="ml-2 rounded-lg border px-2 py-1"
            >
              <option value="0">Never (by hand only)</option>
              {["3", "7", "14", "30", "60", "90"].map((d) => (
                <option key={d} value={d}>
                  {d} days
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-slate-700">
            Delete archived items
            <select
              value={months}
              disabled={!settings.can_change}
              onChange={(e) => setMonths(e.target.value)}
              className="ml-2 rounded-lg border px-2 py-1"
            >
              {RETENTION.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <p className="text-xs text-slate-500">
            Cases with quotes, invoices, payments or claims are never deleted, because those records
            must be kept. Only the Main Admin can change these settings or delete from the archive.
          </p>
          {settings.can_change && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void saveSettings()}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              Save
            </button>
          )}
        </section>
      )}
    </main>
  );
}

export default function ArchivePage() {
  return (
    <Suspense fallback={null}>
      <ArchiveView />
    </Suspense>
  );
}
