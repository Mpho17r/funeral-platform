"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardList, PiggyBank, Sparkles, TrendingDown, TrendingUp, Users } from "lucide-react";

import api from "@/lib/api";
import { formatRand } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { SetupChecklist } from "@/components/SetupChecklist";

type Money = { income: number; expenses: number; profit: number; result: "profit" | "loss" };
type Tasks = { open: number; overdue: number; due_today: number; not_started: number };
type Person = { id: string; name: string; job_title?: string | null; open?: number; detected?: string[] };

/** The home screen of a general business: money, work and the team. */
export default function BusinessDashboard() {
  const { user, can } = useCurrentUser();
  const [money, setMoney] = useState<Money | null>(null);
  const [tasks, setTasks] = useState<Tasks | null>(null);
  const [team, setTeam] = useState<Person[]>([]);

  useEffect(() => {
    if (can("income.view")) {
      api.get<Money>("/money/summary").then((r) => setMoney(r.data)).catch(() => setMoney(null));
    }
    api.get<Tasks>("/tasks/summary").then((r) => setTasks(r.data)).catch(() => setTasks(null));
    if (can("tasks.manage")) {
      api.get<Person[]>("/work/people").then((r) => setTeam(r.data)).catch(() => setTeam([]));
    }
  }, [can]);

  const card = "rounded-xl border bg-white p-4";
  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">
          {user?.full_name ? `Hello, ${user.full_name.split(" ")[0]}` : "Hello"}
        </h1>
        <p className="text-sm text-slate-500">Here is how the business is doing today.</p>
      </header>

      {user && user.role !== "staff" && <SetupChecklist />}

      {money && (
        <Link href="/money" className="grid gap-3 sm:grid-cols-3">
          <div className={card}>
            <p className="text-xs text-slate-500">Received this month</p>
            <p className="mt-1 text-2xl font-bold">{formatRand(money.income)}</p>
          </div>
          <div className={card}>
            <p className="text-xs text-slate-500">Spent this month</p>
            <p className="mt-1 text-2xl font-bold">{formatRand(money.expenses)}</p>
          </div>
          <div className={`rounded-xl border p-4 ${money.result === "profit" ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
            <p className="flex items-center gap-1 text-xs text-slate-600">
              {money.result === "profit" ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              {money.result === "profit" ? "Profit" : "Loss"} so far
            </p>
            <p className="mt-1 text-2xl font-bold">{formatRand(Math.abs(money.profit))}</p>
          </div>
        </Link>
      )}

      <section className="grid gap-3 sm:grid-cols-2">
        <Link href="/tasks" className={card}>
          <p className="flex items-center gap-2 font-semibold text-slate-900">
            <ClipboardList size={18} /> My work
          </p>
          {tasks ? (
            <p className="mt-2 text-sm text-slate-600">
              {tasks.open} open
              {tasks.overdue ? ` · ${tasks.overdue} overdue` : ""}
              {tasks.due_today ? ` · ${tasks.due_today} due today` : ""}
            </p>
          ) : (
            <p className="mt-2 text-sm text-slate-500">Nothing waiting.</p>
          )}
        </Link>
        <Link href="/assistant" className={card}>
          <p className="flex items-center gap-2 font-semibold text-slate-900">
            <Sparkles size={18} /> Ask KAI
          </p>
          <p className="mt-2 text-sm text-slate-600">
            “Create a task to chase the supplier invoices” — KAI works out who does that job.
          </p>
        </Link>
        {can("income.view") && (
          <Link href="/money" className={card}>
            <p className="flex items-center gap-2 font-semibold text-slate-900">
              <PiggyBank size={18} /> Money
            </p>
            <p className="mt-2 text-sm text-slate-600">Record money received and see profit or loss.</p>
          </Link>
        )}
      </section>

      {team.length > 0 && (
        <section className={card}>
          <h2 className="mb-2 flex items-center gap-2 font-semibold text-slate-900">
            <Users size={18} /> Your team
          </h2>
          <ul className="divide-y text-sm">
            {team.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="font-medium text-slate-800">
                  {p.name}
                  {p.job_title ? <span className="font-normal text-slate-500"> · {p.job_title}</span> : null}
                </span>
                <span className="text-xs text-slate-500">
                  {p.detected && p.detected.length > 0 ? `KAI sees: ${p.detected.join(", ")}` : "No job title yet"}
                  {typeof p.open === "number" ? ` · ${p.open} open` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
