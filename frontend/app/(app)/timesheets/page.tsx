"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Download, Timer } from "lucide-react";

import api from "@/lib/api";
import { categoryLabel, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { ErrorNote } from "@/components/Notices";

type Day = {
  date: string;
  weekday: string;
  worked_seconds: number;
  break_seconds: number;
  net_seconds: number;
  first_in: string | null;
  last_out: string | null;
  leave: string | null;
  still_clocked_in: boolean;
};
type Week = { week_start: string; days: Day[]; net_seconds: number; break_seconds: number; user_name: string };
type Team = {
  week_start: string;
  dates: string[];
  people: {
    user_id: string;
    user_name: string;
    job_title: string | null;
    days: number[];
    leave_days: (string | null)[];
    net_seconds: number;
  }[];
};

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function mondayOf(d: Date) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}

function hours(seconds: number) {
  if (!seconds) return "-";
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m === 60 ? `${h + 1}h 00m` : `${h}h ${String(m).padStart(2, "0")}m`;
}

export default function TimesheetsPage() {
  const { can } = useCurrentUser();
  const manage = can("timesheets.manage");
  const [monday, setMonday] = useState(mondayOf(new Date()));
  const [mine, setMine] = useState<Week | null>(null);
  const [team, setTeam] = useState<Team | null>(null);
  const [error, setError] = useState("");
  const [person, setPerson] = useState<string>("");

  const weekOf = iso(monday);

  useEffect(() => {
    let live = true;
    api
      .get<Week>("/timesheets/week", { params: { week_of: weekOf, ...(person && { user_id: person }) } })
      .then((r) => live && (setMine(r.data), setError("")))
      .catch((err) => live && setError(getApiErrorMessage(err, "Could not load your hours.")));
    if (manage) {
      api
        .get<Team>("/timesheets/team", { params: { week_of: weekOf } })
        .then((r) => live && setTeam(r.data))
        .catch(() => live && setTeam(null));
    }
    return () => {
      live = false;
    };
  }, [weekOf, manage, person]);

  function shift(weeks: number) {
    const next = new Date(monday);
    next.setDate(next.getDate() + weeks * 7);
    setMonday(next);
  }

  async function download() {
    try {
      const r = await api.get("/timesheets/export", { params: { week_of: weekOf }, responseType: "blob" });
      const url = URL.createObjectURL(r.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `timesheet-${weekOf}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not download."));
    }
  }

  const sunday = new Date(monday);
  sunday.setDate(sunday.getDate() + 6);

  return (
    <main className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <Timer size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Timesheets</h1>
            <p className="text-sm text-slate-500">Hours worked, from clock-in and clock-out, minus breaks.</p>
          </div>
        </div>
        {manage && (
          <button
            type="button"
            onClick={download}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"
          >
            <Download size={16} /> Download week (CSV)
          </button>
        )}
      </header>

      <div className="flex items-center gap-2">
        <button type="button" aria-label="Previous week" onClick={() => shift(-1)} className="rounded-lg border p-2 hover:bg-slate-50">
          <ChevronLeft size={16} />
        </button>
        <span className="min-w-48 text-center text-sm font-medium">
          {monday.toLocaleDateString("en-ZA", { day: "numeric", month: "short" })} –{" "}
          {sunday.toLocaleDateString("en-ZA", { day: "numeric", month: "short", year: "numeric" })}
        </span>
        <button type="button" aria-label="Next week" onClick={() => shift(1)} className="rounded-lg border p-2 hover:bg-slate-50">
          <ChevronRight size={16} />
        </button>
        <button type="button" onClick={() => setMonday(mondayOf(new Date()))} className="rounded-lg border px-3 py-2 text-xs font-medium hover:bg-slate-50">
          This week
        </button>
      </div>

      {error && <ErrorNote message={error} />}

      {mine && (
        <section className="overflow-x-auto rounded-2xl border bg-white">
          <h2 className="px-4 pt-4 font-semibold">{person ? mine.user_name : "My week"}</h2>
          <table className="mt-2 w-full min-w-[34rem] text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Day</th>
                <th className="px-4 py-2">In</th>
                <th className="px-4 py-2">Out</th>
                <th className="px-4 py-2 text-right">Breaks</th>
                <th className="px-4 py-2 text-right">Worked</th>
              </tr>
            </thead>
            <tbody>
              {mine.days.map((d) => (
                <tr key={d.date} className="border-t">
                  <td className="px-4 py-2">
                    {d.weekday} {d.date.slice(8)}
                    {d.leave && (
                      <span className="ml-2 rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-800">
                        {categoryLabel(d.leave)} leave
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2">{d.first_in ?? "-"}</td>
                  <td className="px-4 py-2">{d.still_clocked_in ? "working now" : (d.last_out ?? "-")}</td>
                  <td className="px-4 py-2 text-right">{hours(d.break_seconds)}</td>
                  <td className="px-4 py-2 text-right font-medium">{hours(d.net_seconds)}</td>
                </tr>
              ))}
              <tr className="border-t bg-slate-50 font-semibold">
                <td className="px-4 py-3" colSpan={3}>Total</td>
                <td className="px-4 py-3 text-right">{hours(mine.break_seconds)}</td>
                <td className="px-4 py-3 text-right">{hours(mine.net_seconds)}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      {manage && team && (
        <section className="overflow-x-auto rounded-2xl border bg-white">
          <h2 className="px-4 pt-4 font-semibold">Everyone</h2>
          <table className="mt-2 w-full min-w-[40rem] text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Name</th>
                {team.dates.map((d) => (
                  <th key={d} className="px-2 py-2 text-right">
                    {new Date(d).toLocaleDateString("en-ZA", { weekday: "short" })}
                  </th>
                ))}
                <th className="px-4 py-2 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {team.people.map((p) => (
                <tr
                  key={p.user_id}
                  tabIndex={0}
                  onClick={() => setPerson(p.user_id === person ? "" : p.user_id)}
                  onKeyDown={(e) => e.key === "Enter" && setPerson(p.user_id === person ? "" : p.user_id)}
                  className={`cursor-pointer border-t hover:bg-slate-50 ${p.user_id === person ? "bg-slate-50" : ""}`}
                >
                  <td className="px-4 py-2 font-medium">
                    {p.user_name}
                    {p.job_title && <div className="text-xs font-normal text-slate-500">{p.job_title}</div>}
                  </td>
                  {p.days.map((s, i) => (
                    <td key={i} className="px-2 py-2 text-right text-xs">
                      {p.leave_days[i] && !s ? <span className="text-sky-700">Leave</span> : hours(s)}
                    </td>
                  ))}
                  <td className="px-4 py-2 text-right font-semibold">{hours(p.net_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-4 py-3 text-xs text-slate-500">Click a name to see that person&apos;s week above.</p>
        </section>
      )}
    </main>
  );
}
