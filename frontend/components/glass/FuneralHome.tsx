"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarX, Wallet } from "lucide-react";

import api from "@/lib/api";
import { useCurrentUser } from "@/components/CurrentUserProvider";
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

type Upcoming = { id: string; case_number: string; deceased_full_name: string; funeral_date: string; funeral_venue: string | null };
type Recent = { id: string; case_number: string; deceased_full_name: string; funeral_date: string | null; status: string };
type Summary = {
  active_cases: number;
  upcoming_funeral_count: number;
  outstanding_balance: string | null;
  total_revenue: string | null;
  amount_paid: string | null;
  total_credit: string | null;
  recent_cases: Recent[];
  upcoming_funerals: Upcoming[];
};
type TrendRow = { month: string; collected: number | string; cases_opened: number; new_members: number };
type Person = { user_id: string; user_name: string; status: string };
type Job = { report_time: string | null; pickup_address: string | null; venue: string | null; destination: string | null; label: string | null };

const rand = (n: number) =>
  `R${new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(n)}`;
const randExact = (n: number) =>
  `R${new Intl.NumberFormat("en-ZA", { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(n)}`;

function startOfDay(d: Date) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function daysFrom(dateStr: string) {
  return Math.round((startOfDay(new Date(dateStr)).getTime() - startOfDay(new Date()).getTime()) / 86_400_000);
}

function dayWords(days: number) {
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days < 0) return `${-days} days ago`;
  return `In ${days} days`;
}

const STATUS: Record<string, { dot: string; label: string }> = {
  online: { dot: "#6ee7a8", label: "Online" },
  away: { dot: "#f3c76b", label: "Away" },
  busy: { dot: "#f08a84", label: "Busy" },
  checked_in: { dot: "#8cc4f5", label: "At work" },
  offline: { dot: "#9ca3af", label: "Offline" },
};

/** The funeral home's glass home screen. */
export default function GlassFuneralHome() {
  const { user, can } = useCurrentUser();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trend, setTrend] = useState<TrendRow[]>([]);
  const [team, setTeam] = useState<Person[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [tab, setTab] = useState<"cases" | "revenue" | "members">("cases");

  useEffect(() => {
    api.get<Summary>("/dashboard/summary").then((r) => setSummary(r.data)).catch(() => {});

    if (can("reports.view")) {
      const to = new Date();
      const from = new Date(to.getFullYear(), to.getMonth(), 1);
      const iso = (d: Date) => d.toISOString().slice(0, 10);
      api
        .get<{ trend: TrendRow[] }>("/reports/overview", { params: { date_from: iso(from), date_to: iso(to) } })
        .then((r) => setTrend(r.data.trend ?? []))
        .catch(() => {});
    }

    if (can("presence.view")) {
      api.get<Person[]>("/presence").then((r) => setTeam(r.data)).catch(() => {});
    }
  }, [can]);

  const upcoming = useMemo(
    () => [...(summary?.upcoming_funerals ?? [])].sort((a, b) => a.funeral_date.localeCompare(b.funeral_date)),
    [summary],
  );
  const next = upcoming[0];

  useEffect(() => {
    if (!next || !can("transport.view")) {
      setJobs([]);
      return;
    }
    api
      .get<Job[]>("/transport/jobs", { params: { case_id: next.id } })
      .then((r) => setJobs(r.data))
      .catch(() => setJobs([]));
  }, [next, can]);

  const weather = useWeather(null);

  const first = user?.full_name?.split(" ")[0] ?? "";
  const todayText = new Date().toLocaleDateString("en-ZA", { weekday: "long", day: "numeric", month: "long" });
  const soon = upcoming.filter((f) => daysFrom(f.funeral_date) <= 1 && daysFrom(f.funeral_date) >= 0).length;
  const sub =
    soon === 0
      ? `${todayText}. No funerals today or tomorrow.`
      : `${todayText}. ${soon === 1 ? "One funeral" : `${soon} funerals`} ${upcoming.some((f) => daysFrom(f.funeral_date) === 0) ? "today or tomorrow" : "tomorrow"}.`;

  // Money
  const billed = Number(summary?.total_revenue ?? 0);
  const paid = Number(summary?.amount_paid ?? 0);
  const owed = Number(summary?.outstanding_balance ?? 0);
  const credit = Number(summary?.total_credit ?? 0);
  const showMoney = summary?.total_revenue != null;
  const pct = billed > 0 ? (paid / billed) * 100 : 0;

  // Route: real transport stops when planned, otherwise the venue we know
  const stops: RouteStop[] = useMemo(() => {
    if (!next) return [];
    const timed = jobs.filter((j) => j.report_time).sort((a, b) => String(a.report_time).localeCompare(String(b.report_time)));
    const out: RouteStop[] = [];
    const t = (iso: string | null) =>
      iso ? new Date(iso).toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit", hour12: false }) : undefined;
    if (timed[0]?.pickup_address) out.push({ label: timed[0].pickup_address, time: t(timed[0].report_time) });
    else out.push({ label: "Family home" });
    timed.forEach((j) => {
      if (j.venue && !out.some((s) => s.label === j.venue)) out.push({ label: j.venue, time: t(j.report_time) });
    });
    if (out.length === 1) out.push({ label: next.funeral_venue ?? "Venue not set" });
    const last = timed[timed.length - 1]?.destination;
    out.push({ label: last ?? "Burial" });
    return out.slice(0, 4);
  }, [next, jobs]);

  // Chart
  const series = useMemo(() => {
    const monthLabel = (m: string) => new Date(m).toLocaleDateString("en-ZA", { month: "short" });
    return trend.map((row) => ({
      label: monthLabel(row.month),
      value: tab === "cases" ? row.cases_opened : tab === "revenue" ? Number(row.collected) : row.new_members,
    }));
  }, [trend, tab]);

  // Needs attention (only what is true)
  const attention: { icon: React.ReactNode; text: string; href: string }[] = [];
  if (showMoney && owed > 0) {
    attention.push({ icon: <Wallet size={16} />, text: `${randExact(owed)} still to collect`, href: "/cases" });
  }
  upcoming
    .filter((f) => !f.funeral_venue)
    .slice(0, 2)
    .forEach((f) =>
      attention.push({
        icon: <AlertTriangle size={16} />,
        text: `No venue set for ${f.deceased_full_name}, funeral on ${new Date(f.funeral_date).toLocaleDateString("en-ZA", { day: "numeric", month: "short" })}.`,
        href: `/cases/${f.id}`,
      }),
    );
  const undated = (summary?.recent_cases ?? []).filter((c) => !c.funeral_date && !["closed", "completed", "archived"].includes(c.status)).length;
  if (undated > 0) {
    attention.push({
      icon: <CalendarX size={16} />,
      text: `${undated} open ${undated === 1 ? "case has" : "cases have"} no funeral date yet.`,
      href: "/cases",
    });
  }

  return (
    <main className="mx-auto w-full max-w-[1280px] space-y-5 px-4 pb-10 pt-2 sm:px-6">
      <header>
        <h1 className="font-serif text-[40px] font-semibold leading-tight text-white sm:text-5xl">
          {greeting()}
          {first ? `, ${first}` : ""}
        </h1>
        <p className="mt-1 text-sm text-white/80">{sub}</p>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.35fr)_minmax(0,0.95fr)]">
        {/* Left */}
        <div className="space-y-4">
          {showMoney && (
            <GlassCard title="Collected" subtitle="Paid against everything billed">
              <Gauge percent={pct} caption="of billed" />
              <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 text-xs text-white/75">
                <div><dt>Billed</dt><dd className="mt-0.5 text-sm font-semibold text-white">{randExact(billed)}</dd></div>
                <div><dt>Paid</dt><dd className="mt-0.5 text-sm font-semibold text-white">{randExact(paid)}</dd></div>
                <div><dt>Credit held</dt><dd className="mt-0.5 text-sm font-semibold text-white">{randExact(credit)}</dd></div>
                <div><dt>Still to collect</dt><dd className="mt-0.5 text-sm font-semibold text-[#f5d58f]">{randExact(owed)}</dd></div>
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

        {/* Middle */}
        <div className="space-y-4">
          <GlassCard>
            {next ? (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <Link href={`/cases/${next.id}`} className="min-w-0">
                    <h2 className="font-serif text-3xl font-semibold leading-tight text-white">{next.deceased_full_name}</h2>
                    <p className="mt-1 text-xs text-white/80">
                      {dayWords(daysFrom(next.funeral_date))},{" "}
                      {new Date(next.funeral_date).toLocaleDateString("en-ZA", { weekday: "long", day: "numeric", month: "long" })} · {next.case_number}
                    </p>
                  </Link>
                  <WeatherChip weather={weather} />
                </div>
                <RouteTimeline stops={stops} />
              </>
            ) : (
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-serif text-3xl font-semibold text-white">No funerals coming up</h2>
                  <p className="mt-1 text-xs text-white/80">When a case gets a funeral date, the day appears here.</p>
                </div>
                <WeatherChip weather={weather} />
              </div>
            )}
          </GlassCard>

          {can("reports.view") && (
            <GlassCard
              title={tab === "cases" ? "Cases per month" : tab === "revenue" ? "Money collected per month" : "New members per month"}
              action={
                <MiniTabs
                  value={tab}
                  onChange={setTab}
                  options={[
                    { id: "cases", label: "Cases" },
                    { id: "revenue", label: "Revenue" },
                    { id: "members", label: "Members" },
                  ]}
                />
              }
            >
              {series.length > 0 ? (
                <AreaChart points={series} format={tab === "revenue" ? rand : undefined} />
              ) : (
                <p className="py-10 text-center text-sm text-white/75">Numbers appear here as the months fill in.</p>
              )}
            </GlassCard>
          )}
        </div>

        {/* Right */}
        <div className="space-y-4">
          <GlassCard title="Coming up" action={<Link href="/calendar" className="text-xs font-medium text-[#d9f0c6]">Calendar</Link>}>
            {upcoming.length === 0 ? (
              <p className="text-sm text-white/75">Nothing scheduled.</p>
            ) : (
              <ul className="space-y-3">
                {upcoming.slice(0, 3).map((f) => {
                  const d = new Date(f.funeral_date);
                  const days = daysFrom(f.funeral_date);
                  return (
                    <li key={f.id}>
                      <Link href={`/cases/${f.id}`} className="flex items-center gap-3">
                        <span className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl border border-white/25 bg-white/10 text-white">
                          <span className="font-serif text-lg font-semibold leading-none">{d.getDate()}</span>
                          <span className="text-[10px] text-white/80">{d.toLocaleDateString("en-ZA", { month: "short" })}</span>
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-white">{f.deceased_full_name}</span>
                          <span className="block truncate text-xs text-white/75">{f.funeral_venue ?? "Venue not set"}</span>
                        </span>
                        <span className={`shrink-0 text-xs ${days <= 1 ? "font-semibold text-[#f5d58f]" : "text-white/75"}`}>{dayWords(days)}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
            <Link href="/cases" className="mt-4 block border-t border-white/15 pt-3 text-center text-xs font-medium text-[#d9f0c6]">
              View all funerals
            </Link>
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
        </div>
      </div>
    </main>
  );
}
