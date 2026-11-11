"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ClipboardList, Sparkles, Wallet } from "lucide-react";

import api from "@/lib/api";
import { useBranding } from "@/components/BrandingProvider";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { SetupChecklist } from "@/components/SetupChecklist";
import {
  AreaChart,
  Gauge,
  GlassCard,
  Initials,
  MiniTabs,
  RouteTimeline,
  type RouteStop,
  WeatherChip,
  greeting,
  useWeather,
} from "@/components/glass/primitives";

type MoneyRow = { month: string; income: number; expenses: number; profit: number };
type Money = { income: number; expenses: number; profit: number; result: "profit" | "loss"; trend: MoneyRow[] };
type Tasks = { open: number; overdue: number; due_today: number; not_started: number };
type Person = { user_id: string; user_name: string; status: string };
type Ev = { id: string; event_type: string; title: string; date: string; due_at?: string | null; case_number?: string; venue?: string | null; assigned_to_name?: string | null };

const rand = (n: number) => `R${new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(n)}`;
const randExact = (n: number) => `R${new Intl.NumberFormat("en-ZA", { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(n)}`;
const dayKey = (d: Date) => d.toISOString().slice(0, 10);

const STATUS: Record<string, { dot: string; label: string }> = {
  online: { dot: "#6ee7a8", label: "Online" },
  away: { dot: "#f3c76b", label: "Away" },
  busy: { dot: "#f08a84", label: "Busy" },
  checked_in: { dot: "#8cc4f5", label: "At work" },
  offline: { dot: "#9ca3af", label: "Offline" },
};

function whenWords(dateStr: string) {
  const days = Math.round((new Date(dateStr + "T00:00").getTime() - new Date(dayKey(new Date()) + "T00:00").getTime()) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return days < 0 ? `${-days} days ago` : `In ${days} days`;
}

/** The glass home screen of a general business. */
export default function GlassBusinessHome() {
  const { user, can } = useCurrentUser();
  const { branding } = useBranding();
  const [money, setMoney] = useState<Money | null>(null);
  const [tasks, setTasks] = useState<Tasks | null>(null);
  const [team, setTeam] = useState<Person[]>([]);
  const [events, setEvents] = useState<Ev[]>([]);
  const [tab, setTab] = useState<"income" | "expenses" | "profit">("income");

  useEffect(() => {
    if (can("income.view")) api.get<Money>("/money/summary").then((r) => setMoney(r.data)).catch(() => {});
    api.get<Tasks>("/tasks/summary").then((r) => setTasks(r.data)).catch(() => {});
    if (can("presence.view")) api.get<Person[]>("/presence").then((r) => setTeam(r.data)).catch(() => {});
    api.get<Ev[]>("/calendar").then((r) => setEvents(r.data)).catch(() => {});
  }, [can]);

  const weather = useWeather(null);
  const first = user?.full_name?.split(" ")[0] ?? "";
  const todayKey = dayKey(new Date());
  const weekEnd = dayKey(new Date(new Date().getTime() + 7 * 86_400_000));
  const todayText = new Date().toLocaleDateString("en-ZA", { weekday: "long", day: "numeric", month: "long" });

  const upcoming = useMemo(
    () => events.filter((e) => e.date >= todayKey && e.event_type !== "leave").sort((a, b) => (a.due_at ?? a.date).localeCompare(b.due_at ?? b.date)),
    [events, todayKey],
  );
  const today = upcoming.filter((e) => e.date === todayKey);
  const weekAhead = upcoming.filter((e) => e.event_type === "appointment" && e.date < weekEnd).length;

  const stops: RouteStop[] = (today.length ? today : upcoming).slice(0, 4).map((e) => ({
    label: e.title,
    time: e.due_at
      ? new Date(e.due_at).toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit", hour12: false })
      : today.length
        ? undefined
        : whenWords(e.date),
  }));

  const sub = today.length
    ? `${todayText}. ${today.length === 1 ? "One thing" : `${today.length} things`} on today.`
    : `${todayText}. Nothing booked for today.`;

  const kept = money && money.income > 0 ? (Math.max(money.profit, 0) / money.income) * 100 : 0;
  const series = (money?.trend ?? []).map((row) => ({
    label: new Date(row.month).toLocaleDateString("en-ZA", { month: "short" }),
    value: tab === "income" ? row.income : tab === "expenses" ? row.expenses : row.profit,
  }));

  const attention: { icon: React.ReactNode; text: string; href: string }[] = [];
  if (tasks && tasks.overdue > 0) attention.push({ icon: <AlertTriangle size={16} />, text: `${tasks.overdue} ${tasks.overdue === 1 ? "task is" : "tasks are"} overdue.`, href: "/tasks" });
  if (tasks && tasks.due_today > 0) attention.push({ icon: <ClipboardList size={16} />, text: `${tasks.due_today} due today.`, href: "/tasks" });
  if (money && money.result === "loss") attention.push({ icon: <Wallet size={16} />, text: `Spending is ${randExact(Math.abs(money.profit))} ahead of money received this month.`, href: "/money" });

  const tiles: { label: string; value: string; href: string; tone?: string }[] = [];
  if (tasks) {
    tiles.push({ label: "Open tasks", value: String(tasks.open), href: "/tasks" });
    tiles.push({ label: "Overdue", value: String(tasks.overdue), href: "/tasks", tone: tasks.overdue ? "text-[#f6a8a2]" : "" });
    tiles.push({ label: "Due today", value: String(tasks.due_today), href: "/tasks" });
  }
  tiles.push({ label: "Appointments this week", value: String(weekAhead), href: "/appointments" });

  return (
    <main className="mx-auto w-full max-w-[1280px] space-y-5 px-4 pb-10 pt-2 sm:px-6">
      <header>
        <h1 className="font-serif text-[40px] font-semibold leading-tight text-white sm:text-5xl">
          {greeting()}
          {first ? `, ${first}` : ""}
        </h1>
        <p className="mt-1 text-sm text-white/80">{sub}</p>
      </header>

      {user && user.role !== "staff" && <SetupChecklist />}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tiles.map((t) => (
          <Link key={t.label} href={t.href} className="glass-panel rounded-[18px] px-4 py-3.5">
            <p className="text-xs text-white/75">{t.label}</p>
            <p className={`mt-1 font-serif text-3xl font-semibold text-white ${t.tone ?? ""}`}>{t.value}</p>
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.35fr)_minmax(0,0.95fr)]">
        <div className="space-y-4">
          {money && (
            <GlassCard title="Kept this month" subtitle="Share of the money received that you kept">
              <Gauge percent={kept} caption="kept" />
              <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 text-xs text-white/75">
                <div><dt>Received</dt><dd className="mt-0.5 text-sm font-semibold text-white">{randExact(money.income)}</dd></div>
                <div><dt>Spent</dt><dd className="mt-0.5 text-sm font-semibold text-white">{randExact(money.expenses)}</dd></div>
                <div className="col-span-2"><dt>{money.result === "profit" ? "Profit so far" : "Loss so far"}</dt><dd className={`mt-0.5 text-sm font-semibold ${money.result === "profit" ? "text-[#d9f0c6]" : "text-[#f6a8a2]"}`}>{randExact(Math.abs(money.profit))}</dd></div>
              </dl>
            </GlassCard>
          )}

          <GlassCard title="Team today">
            {team.length === 0 ? (
              <p className="text-sm text-white/75">No one is signed in yet.</p>
            ) : (
              <ul className="space-y-3">
                {team.slice(0, 5).map((p) => {
                  const s = STATUS[p.status] ?? STATUS.offline;
                  return (
                    <li key={p.user_id} className="flex items-center gap-3 text-sm">
                      <Initials name={p.user_name} />
                      <span className="min-w-0 flex-1 truncate text-white">{p.user_name}</span>
                      <span className="flex items-center gap-1.5 text-xs text-white/80">
                        <span className="h-2 w-2 rounded-full" style={{ background: s.dot }} />
                        {s.label}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </GlassCard>
        </div>

        <div className="space-y-4">
          <GlassCard>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="font-serif text-3xl font-semibold leading-tight text-white">{today.length ? "Your day" : "Coming up next"}</h2>
                <p className="mt-1 text-xs text-white/80">{branding?.name ?? "Your business"} · {todayText}</p>
              </div>
              <WeatherChip weather={weather} />
            </div>
            {stops.length > 0 ? (
              <RouteTimeline stops={stops} />
            ) : (
              <p className="py-14 text-center text-sm text-white/80">Nothing scheduled. Add a task or appointment and your day appears here.</p>
            )}
          </GlassCard>

          {money && (
            <GlassCard
              title={tab === "income" ? "Money received per month" : tab === "expenses" ? "Money spent per month" : "Profit per month"}
              action={
                <MiniTabs
                  value={tab}
                  onChange={setTab}
                  options={[
                    { id: "income", label: "Received" },
                    { id: "expenses", label: "Spent" },
                    { id: "profit", label: "Profit" },
                  ]}
                />
              }
            >
              {series.length > 0 ? <AreaChart points={series} format={rand} /> : <p className="py-10 text-center text-sm text-white/75">Numbers appear as the months fill in.</p>}
            </GlassCard>
          )}
        </div>

        <div className="space-y-4">
          <GlassCard title="Coming up" action={<Link href="/calendar" className="text-xs font-medium text-[#d9f0c6]">Calendar</Link>}>
            {upcoming.length === 0 ? (
              <p className="text-sm text-white/75">Nothing scheduled.</p>
            ) : (
              <ul className="space-y-3">
                {upcoming.slice(0, 4).map((e) => {
                  const d = new Date(e.date + "T00:00");
                  return (
                    <li key={e.id} className="flex items-center gap-3">
                      <span className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl border border-white/25 bg-white/10 text-white">
                        <span className="font-serif text-lg font-semibold leading-none">{d.getDate()}</span>
                        <span className="text-[10px] text-white/80">{d.toLocaleDateString("en-ZA", { month: "short" })}</span>
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-white">{e.title}</span>
                        <span className="block truncate text-xs text-white/75">{e.assigned_to_name ?? (e.event_type === "appointment" ? "Appointment" : "Task")}</span>
                      </span>
                      <span className="shrink-0 text-xs text-white/75">{whenWords(e.date)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </GlassCard>

          <GlassCard title="Needs attention">
            {attention.length === 0 ? (
              <p className="text-sm text-white/80">All clear. Nothing needs you right now.</p>
            ) : (
              <ul className="space-y-2.5">
                {attention.slice(0, 4).map((a, i) => (
                  <li key={i}>
                    <Link href={a.href} className="flex items-start gap-3 rounded-xl border border-white/20 bg-white/10 px-3.5 py-2.5 text-[13px] leading-snug text-white">
                      <span className="mt-0.5 text-[#f5d58f]">{a.icon}</span>
                      {a.text}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </GlassCard>

          <Link href="/assistant" className="glass-panel flex items-start gap-3 rounded-[22px] p-5 text-white">
            <Sparkles size={18} className="mt-0.5 shrink-0 text-[#d9f0c6]" />
            <span className="text-sm">
              <span className="font-semibold">Ask KAI</span>
              <span className="mt-1 block text-xs text-white/80">“Create a task to chase the supplier invoices” — KAI works out who does that job.</span>
            </span>
          </Link>
        </div>
      </div>
    </main>
  );
}
