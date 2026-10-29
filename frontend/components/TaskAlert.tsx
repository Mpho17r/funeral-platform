"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BellRing, X } from "lucide-react";

import api from "@/lib/api";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { playTone } from "@/lib/sound";
import { whenDue } from "@/components/TaskDrawer";

type Summary = {
  open: number;
  overdue: number;
  due_today: number;
  not_started: number;
  items: { id: string; title: string; due_at: string | null; due_date: string | null }[];
};

const SHOWN = "fos.taskalert.shown";

/** Once per sign-in: tell the person about the tasks given to them. */
export default function TaskAlert() {
  const { user, access } = useCurrentUser();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [serviceCount, setServiceCount] = useState(0);
  const userId = user?.user_id;

  useEffect(() => {
    if (!userId || !access) return;
    try {
      if (window.sessionStorage.getItem(SHOWN) === userId) return;
      window.sessionStorage.setItem(SHOWN, userId);
    } catch {
      /* storage blocked: show it anyway */
    }
    Promise.all([
      api.get<Summary>("/tasks/summary").then((r) => r.data).catch(() => null),
      api
        .get<{ open: number; overdue: number; not_started: number }>("/service-work/summary")
        .then((r) => r.data)
        .catch(() => null),
    ]).then(([tasks, services]) => {
      const open = (tasks?.open ?? 0) + (services?.open ?? 0);
      if (open > 0) {
        setSummary(
          tasks ?? { open: 0, overdue: 0, due_today: 0, not_started: 0, items: [] },
        );
        setServiceCount(services?.open ?? 0);
        playTone("task");
      }
    });
  }, [userId, access]);

  if (!summary) return null;

  const parts: string[] = [];
  if (summary.open) parts.push(`${summary.open} open ${summary.open === 1 ? "task" : "tasks"}`);
  if (serviceCount) parts.push(`${serviceCount} ${serviceCount === 1 ? "service" : "services"} to update`);
  if (summary.overdue) parts.push(`${summary.overdue} overdue`);
  if (summary.due_today) parts.push(`${summary.due_today} due today`);
  if (summary.not_started) parts.push(`${summary.not_started} not started`);

  return (
    <div
      role="alert"
      className="fixed right-4 top-4 z-[180] w-[min(92vw,24rem)] rounded-2xl border bg-white p-4 shadow-2xl"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="flex items-center gap-2 font-semibold text-slate-900">
          <BellRing size={18} className="text-amber-500" />
          You have work waiting
        </p>
        <button type="button" onClick={() => setSummary(null)} aria-label="Dismiss" className="rounded p-1 text-slate-500 hover:bg-slate-100">
          <X size={16} />
        </button>
      </div>
      <p className="mt-1 text-sm text-slate-600">{parts.join(" · ")}</p>
      <ul className="mt-2 space-y-1 text-sm">
        {summary.items.slice(0, 3).map((t) => (
          <li key={t.id} className="truncate text-slate-800">
            {t.title} <span className="text-xs text-slate-500">· {whenDue(t.due_at, t.due_date)}</span>
          </li>
        ))}
      </ul>
      <Link
        href="/tasks"
        onClick={() => setSummary(null)}
        className="mt-3 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        Open my work
      </Link>
    </div>
  );
}
