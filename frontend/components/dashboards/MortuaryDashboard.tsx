"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  DoorOpen,
  Loader2,
  Search,
  Snowflake,
  Thermometer,
  UserRound,
} from "lucide-react";

import api from "@/lib/api";
import { formatDate, getApiErrorMessage } from "@/lib/format";
import { formatDateTime, formatTime } from "@/lib/datetime";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, Field, inputClass } from "@/components/Dialog";
import { Banner } from "@/components/Notices";
import {
  DashboardHeader,
  EmptyRow,
  Panel,
  QuickActions,
} from "@/components/dashboards/Shared";

/* ============================================================
   TYPES
============================================================ */

type Occupant = {
  remains_id: string;
  case_id: string;
  case_number: string;
  name: string;
  tag_number: string;
  received_at: string;
  stage: Stage;
  days_in_care: number;
  funeral_date: string | null;
  blockers: string[];
};

type Stage =
  | "awaiting_identification"
  | "awaiting_preparation"
  | "awaiting_paperwork"
  | "ready_for_release";

type Unit = {
  id: string;
  name: string;
  zone: string;
  capacity: number | null;
  occupied: number;
  status: "available" | "occupied" | "full" | "out_of_range";
  temperature_c: number | null;
  temperature_at: string | null;
  occupants: Occupant[];
};

type Attention = {
  reason: string;
  message: string;
  name: string;
  case_id?: string;
  location_id?: string;
};

type Overview = {
  occupancy: {
    occupied: number;
    capacity: number;
    percent: number | null;
    unlimited_places: number;
  };
  in_care: number;
  pending_releases: number;
  ready_for_release: Occupant[];
  admissions_today: number;
  admissions_today_list: Occupant[];
  stages: Record<Stage, number>;
  temperature: {
    hours: number;
    max_safe_c: number;
    points: { at: string; temperature_c: number }[];
    readings: number;
    average_c: number | null;
    min_c: number | null;
    max_c: number | null;
    out_of_range: number;
  };
  units: Unit[];
  not_in_a_cold_place: {
    remains_id: string;
    case_id: string;
    name: string;
    tag_number: string;
  }[];
  attention: Attention[];
};

type Task = {
  id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  title: string;
  due_date: string | null;
  assigned_to: string | null;
  completed_at: string | null;
};

const PAGE_SIZE = 12;

const ZONE_LABEL: Record<string, string> = {
  fridge: "Fridges",
  cold_room: "Cold rooms",
};

const STATUS_STYLE: Record<
  Unit["status"],
  { label: string; chip: string }
> = {
  available: {
    label: "Available",
    chip: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  },
  occupied: {
    label: "Occupied",
    chip: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  },
  full: {
    label: "Full",
    chip: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  },
  out_of_range: {
    label: "Too warm",
    chip: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  },
};

const STAGES: { id: Stage; label: string; hint: string }[] = [
  {
    id: "awaiting_identification",
    label: "To identify",
    hint: "Formal identification by family",
  },
  {
    id: "awaiting_preparation",
    label: "To prepare",
    hint: "Washing, dressing, preparation",
  },
  {
    id: "awaiting_paperwork",
    label: "Paperwork",
    hint: "Permits and release papers",
  },
  {
    id: "ready_for_release",
    label: "Ready to release",
    hint: "Checks complete",
  },
];

/* ============================================================
   TEMPERATURE CHART
============================================================ */

function TemperatureChart({
  data,
}: {
  data: Overview["temperature"];
}) {
  const W = 560;
  const H = 170;
  const pad = { l: 34, r: 10, t: 10, b: 22 };

  const points = data.points;

  if (points.length === 0) {
    return (
      <p className="px-5 py-10 text-center text-sm text-[var(--fos-text-muted)]">
        No temperatures recorded in this period. Use{" "}
        <strong>Log temperature</strong> to record one.
      </p>
    );
  }

  const values = points.map((p) => p.temperature_c);
  const lo = Math.min(-2, Math.floor(Math.min(...values)) - 1);
  const hi = Math.max(data.max_safe_c + 2, Math.ceil(Math.max(...values)) + 1);

  const t0 = new Date(points[0].at).getTime();
  const t1 = new Date(points[points.length - 1].at).getTime();
  const span = Math.max(t1 - t0, 1);

  const x = (at: string) =>
    pad.l +
    (points.length === 1
      ? (W - pad.l - pad.r) / 2
      : ((new Date(at).getTime() - t0) / span) * (W - pad.l - pad.r));
  const y = (v: number) =>
    pad.t + ((hi - v) / (hi - lo)) * (H - pad.t - pad.b);

  const line = points
    .map((p, i) => `${i ? "L" : "M"}${x(p.at)},${y(p.temperature_c)}`)
    .join(" ");

  const ticks = [lo, 0, data.max_safe_c, hi].filter(
    (v, i, all) => all.indexOf(v) === i
  );

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-44 w-full"
      role="img"
      aria-label={`Cold room temperatures. Average ${data.average_c}°C, lowest ${data.min_c}°C, highest ${data.max_c}°C. Safe limit ${data.max_safe_c}°C.`}
    >
      {/* the safe zone: at or below the limit */}
      <rect
        x={pad.l}
        y={y(data.max_safe_c)}
        width={W - pad.l - pad.r}
        height={y(lo) - y(data.max_safe_c)}
        fill="var(--fos-primary)"
        opacity={0.06}
      />
      {ticks.map((v) => (
        <g key={v}>
          <line
            x1={pad.l}
            x2={W - pad.r}
            y1={y(v)}
            y2={y(v)}
            stroke="var(--fos-border)"
            strokeDasharray={v === data.max_safe_c ? "5 4" : undefined}
          />
          <text
            x={pad.l - 6}
            y={y(v) + 4}
            textAnchor="end"
            fontSize="10"
            fill="var(--fos-text-muted)"
          >
            {v}°
          </text>
        </g>
      ))}
      <text
        x={W - pad.r}
        y={y(data.max_safe_c) - 4}
        textAnchor="end"
        fontSize="10"
        fill="var(--fos-text-muted)"
      >
        Limit {data.max_safe_c}°C
      </text>
      <path
        d={line}
        fill="none"
        stroke="var(--fos-primary)"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {points.map((p) => (
        <circle
          key={p.at}
          cx={x(p.at)}
          cy={y(p.temperature_c)}
          r={3.5}
          fill={
            p.temperature_c > data.max_safe_c
              ? "#dc2626"
              : "var(--fos-primary)"
          }
        >
          <title>
            {formatDateTime(p.at)}: {p.temperature_c}°C
          </title>
        </circle>
      ))}
      <text
        x={pad.l}
        y={H - 4}
        fontSize="10"
        fill="var(--fos-text-muted)"
      >
        {formatTime(points[0].at)}
      </text>
      <text
        x={W - pad.r}
        y={H - 4}
        textAnchor="end"
        fontSize="10"
        fill="var(--fos-text-muted)"
      >
        {formatTime(points[points.length - 1].at)}
      </text>
    </svg>
  );
}

/* ============================================================
   LOG TEMPERATURE
============================================================ */

function LogTemperatureDialog({
  units,
  preselected,
  onClose,
  onSaved,
}: {
  units: Unit[];
  preselected: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [unitId, setUnitId] = useState(preselected ?? units[0]?.id ?? "");
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");

    try {
      await api.post(`/mortuary/locations/${unitId}/temperature`, {
        temperature_c: value,
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not record that."));
      setSaving(false);
    }
  }

  return (
    <Dialog title="Log a temperature" onClose={onClose}>
      <form onSubmit={save} className="space-y-4">
        <Field label="Fridge or cold room">
          <select
            className={inputClass}
            value={unitId}
            onChange={(e) => setUnitId(e.target.value)}
          >
            {units.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Reading (°C)" hint="Remains must be kept at 5°C or colder.">
          <input
            className={inputClass}
            type="number"
            step="0.1"
            min={-40}
            max={40}
            required
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </Field>
        {error && (
          <Banner tone="error" onDismiss={() => setError("")}>
            {error}
          </Banner>
        )}
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--fos-border)] px-4 py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !value || !unitId}
            className="rounded-lg bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-[var(--fos-on-primary)] disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save reading"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

/* ============================================================
   PAGE
============================================================ */

function Stat({
  icon,
  label,
  value,
  suffix,
  footer,
  tone = "neutral",
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  suffix?: string;
  footer?: React.ReactNode;
  tone?: "neutral" | "warn";
}) {
  return (
    <div className="flex h-full flex-col rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 shadow-sm">
      <span
        className={`flex h-10 w-10 items-center justify-center rounded-full ${
          tone === "warn"
            ? "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
            : "bg-[var(--fos-surface-muted)] text-[var(--fos-primary)]"
        }`}
      >
        {icon}
      </span>
      <p className="mt-3 text-sm text-[var(--fos-text-muted)]">{label}</p>
      <p className="mt-1 text-3xl font-bold tabular-nums text-[var(--fos-text)]">
        {value}
        {suffix && (
          <span className="text-xl font-medium text-[var(--fos-text-muted)]">
            {suffix}
          </span>
        )}
      </p>
      {footer && <div className="mt-auto pt-3 text-xs">{footer}</div>}
    </div>
  );
}

export default function MortuaryDashboard() {
  const { user, can } = useCurrentUser();

  const [hours, setHours] = useState(24);
  const [data, setData] = useState<Overview | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState("");
  const [zone, setZone] = useState("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [logFor, setLogFor] = useState<string | null | false>(false);

  const load = useCallback(async () => {
    try {
      const [o, t] = await Promise.all([
        api.get<Overview>("/mortuary/overview", { params: { hours } }),
        api.get<Task[]>("/tasks").catch(() => ({ data: [] as Task[] })),
      ]);
      setData(o.data);
      setTasks(t.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load the mortuary."));
    }
  }, [hours]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const timer = window.setInterval(() => {
      if (!document.hidden) load();
    }, 60000);
    return () => window.clearInterval(timer);
  }, [load]);

  const units = useMemo(() => data?.units ?? [], [data]);
  const zones = useMemo(
    () => Array.from(new Set(units.map((u) => u.zone))),
    [units]
  );

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return units.filter(
      (u) =>
        (zone === "all" || u.zone === zone) &&
        (!q ||
          u.name.toLowerCase().includes(q) ||
          u.occupants.some((o) => o.name.toLowerCase().includes(q)))
    );
  }, [units, zone, query]);

  const pages = Math.max(1, Math.ceil(shown.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const pageUnits = shown.slice(
    (current - 1) * PAGE_SIZE,
    current * PAGE_SIZE
  );

  const mine = tasks.filter(
    (t) => t.assigned_to === user?.user_id && !t.completed_at
  );
  const canLog = can("mortuary.manage");
  const alerts = data?.attention.length ?? 0;
  const occ = data?.occupancy;

  return (
    <main className="space-y-6 p-6 md:p-8">
      <div className="flex items-start justify-between gap-4">
        <DashboardHeader subtitle="Cold storage, who is in our care, and what each person still needs before they can go home." />
        {alerts > 0 && (
          <a
            href="#attention"
            className="flex shrink-0 items-center gap-2 rounded-full bg-amber-100 px-3 py-1.5 text-sm font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300"
          >
            <AlertTriangle size={16} />
            {alerts} {alerts === 1 ? "needs" : "need"} attention
          </a>
        )}
      </div>

      <QuickActions
        actions={[
          { label: "Mortuary board", href: "/mortuary" },
          { label: "Run sheet", href: "/run-sheet" },
          { label: "Staff workspace", href: "/staff" },
        ]}
      />

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      {!data && !error && (
        <div className="flex justify-center py-16 text-[var(--fos-text-muted)]">
          <Loader2 className="animate-spin" />
        </div>
      )}

      {data && occ && (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:col-span-7">
              <Stat
                icon={<DoorOpen size={20} />}
                label="Occupancy"
                value={occ.occupied}
                suffix={occ.capacity ? ` / ${occ.capacity}` : undefined}
                footer={
                  occ.percent !== null ? (
                    <>
                      <span className="font-medium text-[var(--fos-primary)]">
                        {occ.percent}% occupied
                      </span>
                      <span className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-[var(--fos-surface-muted)]">
                        <span
                          className="block h-full rounded-full bg-[var(--fos-primary)]"
                          style={{ width: `${Math.min(occ.percent, 100)}%` }}
                        />
                      </span>
                    </>
                  ) : (
                    <span className="text-[var(--fos-text-muted)]">
                      No limit set on these places
                    </span>
                  )
                }
              />
              <Stat
                icon={<Check size={20} />}
                label="Pending releases"
                value={data.pending_releases}
                tone={data.pending_releases ? "warn" : "neutral"}
                footer={
                  <Link
                    href="/mortuary"
                    className="inline-flex items-center gap-1 font-medium text-[var(--fos-primary)]"
                  >
                    View board <ArrowRight size={12} />
                  </Link>
                }
              />
              <Stat
                icon={<UserRound size={20} />}
                label="Today's admissions"
                value={data.admissions_today}
                footer={
                  <span className="text-[var(--fos-text-muted)]">
                    {data.in_care} in our care in total
                  </span>
                }
              />
            </div>

            <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-sm lg:col-span-5">
              <div className="flex items-center justify-between gap-2 px-5 pt-4">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--fos-text)]">
                  <Thermometer size={16} /> Temperature (°C)
                </h2>
                <select
                  value={hours}
                  onChange={(e) => setHours(Number(e.target.value))}
                  aria-label="Period"
                  className="rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-2 py-1 text-xs"
                >
                  <option value={24}>Last 24 hours</option>
                  <option value={72}>Last 3 days</option>
                  <option value={168}>Last 7 days</option>
                </select>
              </div>
              <TemperatureChart data={data.temperature} />
              <div className="grid grid-cols-3 gap-2 border-t border-[var(--fos-border)] px-5 py-3 text-xs">
                {(
                  [
                    ["Average", data.temperature.average_c],
                    ["Lowest", data.temperature.min_c],
                    ["Highest", data.temperature.max_c],
                  ] as const
                ).map(([label, v]) => (
                  <div key={label}>
                    <p className="text-[var(--fos-text-muted)]">{label}</p>
                    <p className="text-sm font-semibold text-[var(--fos-text)]">
                      {v === null ? "–" : `${v}°C`}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          </div>

          {/* THE JOURNEY */}
          <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-[var(--fos-text)]">
              From arrival to release
            </h2>
            <ol className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
              {STAGES.map((s, i) => (
                <li
                  key={s.id}
                  className="rounded-xl bg-[var(--fos-surface-muted)] p-3"
                >
                  <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Step {i + 1}
                  </p>
                  <p className="mt-0.5 flex items-baseline gap-2 text-[var(--fos-text)]">
                    <span className="text-2xl font-bold tabular-nums">
                      {data.stages[s.id]}
                    </span>
                    <span className="text-sm font-medium">{s.label}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--fos-text-muted)]">
                    {s.hint}
                  </p>
                </li>
              ))}
            </ol>
          </section>

          {/* UNITS */}
          <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--fos-border)] px-5 py-4">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--fos-text)]">
                <Snowflake size={16} /> Cold storage
              </h2>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={zone}
                  onChange={(e) => {
                    setZone(e.target.value);
                    setPage(1);
                  }}
                  aria-label="Zone"
                  className="rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-1.5 text-sm"
                >
                  <option value="all">All places</option>
                  {zones.map((z) => (
                    <option key={z} value={z}>
                      {ZONE_LABEL[z] ?? z}
                    </option>
                  ))}
                </select>
                <div className="relative">
                  <Search
                    size={14}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fos-text-muted)]"
                  />
                  <input
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setPage(1);
                    }}
                    placeholder="Search places or names"
                    className="rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] py-1.5 pl-8 pr-3 text-sm"
                  />
                </div>
                {canLog && units.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setLogFor(null)}
                    className="rounded-lg bg-[var(--fos-primary)] px-3 py-1.5 text-sm font-semibold text-[var(--fos-on-primary)]"
                  >
                    Log temperature
                  </button>
                )}
              </div>
            </div>

            {units.length === 0 ? (
              <EmptyRow>
                No fridges or cold rooms are set up yet. Add them on the
                mortuary board.
              </EmptyRow>
            ) : shown.length === 0 ? (
              <EmptyRow>Nothing matches that search.</EmptyRow>
            ) : (
              <ul className="grid grid-cols-1 gap-3 p-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                {pageUnits.map((u) => {
                  const style = STATUS_STYLE[u.status];
                  return (
                    <li
                      key={u.id}
                      className="rounded-xl border border-[var(--fos-border)] p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="flex items-center gap-2 text-sm font-semibold text-[var(--fos-text)]">
                          <DoorOpen
                            size={16}
                            className="text-[var(--fos-text-muted)]"
                          />
                          {u.name}
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${style.chip}`}
                        >
                          {style.label}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                        {u.occupied}
                        {u.capacity !== null ? ` / ${u.capacity}` : ""} in
                        use
                        {u.temperature_c !== null &&
                          ` · ${u.temperature_c}°C`}
                      </p>

                      <ul className="mt-2 space-y-1">
                        {u.occupants.length === 0 && (
                          <li className="text-xs text-[var(--fos-text-muted)]">
                            Empty
                          </li>
                        )}
                        {u.occupants.slice(0, 3).map((o) => (
                          <li key={o.remains_id}>
                            <Link
                              href={`/cases/${o.case_id}`}
                              className="block text-xs hover:underline"
                            >
                              <span className="font-medium text-[var(--fos-text)]">
                                {o.name}
                              </span>
                              <span className="block text-[var(--fos-text-muted)]">
                                {formatDateTime(o.received_at)}
                              </span>
                            </Link>
                          </li>
                        ))}
                        {u.occupants.length > 3 && (
                          <li className="text-xs text-[var(--fos-text-muted)]">
                            +{u.occupants.length - 3} more
                          </li>
                        )}
                      </ul>

                      {canLog && (
                        <button
                          type="button"
                          onClick={() => setLogFor(u.id)}
                          className="mt-2 text-xs font-medium text-[var(--fos-primary)] hover:underline"
                        >
                          Log temperature
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}

            {shown.length > PAGE_SIZE && (
              <div className="flex items-center justify-between border-t border-[var(--fos-border)] px-5 py-3 text-xs text-[var(--fos-text-muted)]">
                <span>
                  Showing {pageUnits.length} of {shown.length} places
                </span>
                <span className="flex gap-1">
                  {Array.from({ length: pages }, (_, i) => i + 1).map(
                    (n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setPage(n)}
                        aria-current={n === current}
                        className={`h-7 w-7 rounded-md ${
                          n === current
                            ? "bg-[var(--fos-primary)] text-[var(--fos-on-primary)]"
                            : "hover:bg-[var(--fos-surface-muted)]"
                        }`}
                      >
                        {n}
                      </button>
                    )
                  )}
                </span>
              </div>
            )}
          </section>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <div id="attention">
              <Panel title="Needs attention">
                {data.attention.length === 0 &&
                data.not_in_a_cold_place.length === 0 ? (
                  <EmptyRow>Everything is on track.</EmptyRow>
                ) : (
                  <ul className="divide-y divide-[var(--fos-border)]">
                    {data.attention.map((a, i) => (
                      <li key={i} className="px-5 py-3 text-sm">
                        {a.case_id ? (
                          <Link href={`/cases/${a.case_id}`}>
                            <span className="font-medium text-[var(--fos-text)]">
                              {a.name}
                            </span>
                            <span className="block text-xs text-[var(--fos-text-muted)]">
                              {a.message}
                            </span>
                          </Link>
                        ) : (
                          <>
                            <span className="font-medium text-[var(--fos-text)]">
                              {a.name}
                            </span>
                            <span className="block text-xs text-[var(--fos-text-muted)]">
                              {a.message}
                            </span>
                          </>
                        )}
                      </li>
                    ))}
                    {data.not_in_a_cold_place.map((r) => (
                      <li key={r.remains_id} className="px-5 py-3 text-sm">
                        <Link href={`/cases/${r.case_id}`}>
                          <span className="font-medium text-[var(--fos-text)]">
                            {r.name}
                          </span>
                          <span className="block text-xs text-[var(--fos-text-muted)]">
                            Not in a fridge or cold room · tag{" "}
                            {r.tag_number}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>

            <Panel title="My tasks" href="/tasks" linkLabel="All tasks">
              {mine.length === 0 ? (
                <EmptyRow>Nothing assigned to you.</EmptyRow>
              ) : (
                <ul className="divide-y divide-[var(--fos-border)]">
                  {mine.slice(0, 8).map((t) => (
                    <li key={t.id} className="px-5 py-3">
                      <Link href={`/cases/${t.case_id}`} className="block">
                        <span className="block text-sm font-medium text-[var(--fos-text)]">
                          {t.title}
                        </span>
                        <span className="block text-xs text-[var(--fos-text-muted)]">
                          {t.deceased_full_name} · {t.case_number}
                          {t.due_date
                            ? ` · due ${formatDate(t.due_date)}`
                            : ""}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </>
      )}

      {logFor !== false && data && (
        <LogTemperatureDialog
          units={units}
          preselected={logFor}
          onClose={() => setLogFor(false)}
          onSaved={() => {
            setLogFor(false);
            load();
          }}
        />
      )}
    </main>
  );
}
