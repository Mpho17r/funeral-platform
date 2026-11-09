"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Loader2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const KEY = "platform_token";

type Row = {
  id: string;
  name: string;
  status: string;
  tier: string;
  trial_ends_at: string | null;
  limits: Record<string, number | null>;
  usage: Record<string, number>;
  base_price_override_cents: number | null;
  monthly_cents: number;
  plan: string;
};

type Plan = {
  id: string;
  code: string;
  business_type: string;
  name: string;
  tagline: string | null;
  base_price_cents: number;
  included_staff: number;
  included_branches: number;
  extra_staff_cents: number;
  extra_branch_cents: number;
  is_active: boolean;
};

type Pricing = { vat_percent: number; price_note: string | null };

type HealthComponent = {
  state: string;
  message?: string;
  last_backup_at?: string | null;
  age_hours?: number | null;
  size_mb?: number | null;
  enabled?: boolean;
  last_ok_at?: string | null;
  finished_at?: string | null;
  heartbeat_at?: string | null;
  failing?: string[];
  jobs?: Record<string, { ok?: boolean; last_run_at?: string | null }>;
};

type PlatformHealth = {
  state: string;
  checked_at: string;
  local_backup: HealthComponent;
  offsite_backup: HealthComponent;
  scheduler: HealthComponent;
};

type Incident = {
  component: string;
  label: string;
  status: "active" | "resolved";
  state: string;
  opened_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
  alert_notified: boolean;
  recovery_notified: boolean;
};

type IncidentResponse = {
  active: number;
  total: number;
  incidents: Incident[];
};

function formatDate(value?: string | null) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleString("en-ZA");
}

function stateLabel(value?: string) {
  return value ? value.replaceAll("_", " ") : "unknown";
}

function stateStyle(value?: string) {
  if (value === "ok" || value === "resolved") {
    return "bg-green-100 text-green-800";
  }
  if (value === "failed" || value === "active") {
    return "bg-red-100 text-red-800";
  }
  if (value === "degraded" || value === "stale" || value === "unknown") {
    return "bg-amber-100 text-amber-800";
  }
  return "bg-slate-100 text-slate-700";
}

const rands = (c: number) => `R${(c / 100).toLocaleString("en-ZA")}`;

const TIERS = ["standard", "starter", "growth", "professional", "enterprise"];
const STATUSES = ["trial", "active", "suspended", "cancelled"];
const LIMIT_KEYS: [string, string][] = [
  ["max_branches", "branches"],
  ["max_users", "staff accounts"],
  ["max_members", "members"],
  ["max_active_cases", "active cases"],
];

function detail(e: unknown, fallback: string) {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

export default function PlatformPage() {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pricing, setPricing] = useState<Pricing | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [priceSaved, setPriceSaved] = useState(false);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));

  const [health, setHealth] = useState<PlatformHealth | null>(null);
  const [incidents, setIncidents] = useState<IncidentResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState("");
  const [lastHealthRefresh, setLastHealthRefresh] = useState<string | null>(null);

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setToken(sessionStorage.getItem(KEY));
    } catch {
      setToken(null);
    }
    setReady(true);
  }, []);

  const auth = useCallback(
    () => ({ headers: { Authorization: `Bearer ${token}` } }),
    [token],
  );

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const r = await axios.get<Row[]>(`${API}/platform/businesses`, auth());
      const p = await axios.get<Pricing>(`${API}/pricing`);
      const pl = await axios.get<Plan[]>(`${API}/platform/plans`, auth());
      setPricing(p.data);
      setPlans(pl.data);
      setRows(r.data);
      setError("");
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.status === 401) {
        sessionStorage.removeItem(KEY);
        setToken(null);
      } else setError(detail(e, "Could not load businesses."));
    }
  }, [token, auth]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const loadHealth = useCallback(async () => {
    if (!token) return;

    setHealthLoading(true);
    setHealthError("");

    try {
      const [healthResponse, incidentResponse] = await Promise.all([
        axios.get<PlatformHealth>(`${API}/platform/health`, auth()),
        axios.get<IncidentResponse>(`${API}/platform/incidents`, auth()),
      ]);
      setHealth(healthResponse.data);
      setIncidents(incidentResponse.data);
      setLastHealthRefresh(new Date().toISOString());
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.status === 401) {
        sessionStorage.removeItem(KEY);
        setToken(null);
      } else {
        setHealthError(detail(e, "Could not load operational health."));
      }
    } finally {
      setHealthLoading(false);
    }
  }, [token, auth]);

  useEffect(() => {
    if (!token) return;

    const initialLoad = window.setTimeout(() => {
      void loadHealth();
    }, 0);

    const interval = window.setInterval(() => {
      void loadHealth();
    }, 60_000);

    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(interval);
    };
  }, [token, loadHealth]);

  async function login(e: FormEvent) {


    e.preventDefault();
    try {
      setError("");
      const r = await axios.post(`${API}/platform/login`, { email, password });
      sessionStorage.setItem(KEY, r.data.access_token);
      setToken(r.data.access_token);
      setPassword("");
    } catch (err) {
      setError(detail(err, "Could not sign in."));
    }
  }

  async function save(row: Row, body: Record<string, unknown>) {
    try {
      setBusy(row.id);
      setError("");
      await axios.patch(
        `${API}/platform/businesses/${row.id}/subscription`,
        body,
        auth(),
      );
      await load();
    } catch (err) {
      setError(detail(err, "Could not save."));
    } finally {
      setBusy("");
    }
  }

  async function savePricing(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      setError("");
      await axios.put(
        `${API}/platform/pricing`,
        {
          vat_percent: Math.round(Number(f.get("vat"))),
          price_note: String(f.get("note") ?? ""),
        },
        auth(),
      );
      setPriceSaved(true);
      await load();
    } catch (err) {
      setError(detail(err, "Could not save the prices."));
    }
  }

  async function savePlan(e: FormEvent<HTMLFormElement>, plan: Plan) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const cents = (k: string) => Math.round(Number(f.get(k)) * 100);
    const count = (k: string) => Math.round(Number(f.get(k)));
    try {
      setError("");
      await axios.put(
        `${API}/platform/plans/${plan.id}`,
        {
          name: String(f.get("name") ?? ""),
          base_price_cents: cents("base"),
          included_staff: count("staff"),
          included_branches: count("branches"),
          extra_staff_cents: cents("xstaff"),
          extra_branch_cents: cents("xbranch"),
          is_active: f.get("active") === "on",
        },
        auth(),
      );
      setPriceSaved(true);
      await load();
    } catch (err) {
      setError(detail(err, "Could not save the plan."));
    }
  }

  async function downloadStatements() {
    try {
      setError("");
      const r = await axios.get(`${API}/platform/statements`, {
        ...auth(),
        params: { month, format: "csv" },
        responseType: "blob",
      });
      const url = URL.createObjectURL(r.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `linda-statements-${month}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(detail(err, "Could not download the statements."));
    }
  }

  if (!ready) return null;

  if (!token) {
    return (
      <main className="mx-auto max-w-sm p-6">
        <h1 className="mb-1 text-xl font-bold">Platform operator</h1>
        <p className="mb-4 text-sm text-slate-500">
          For Saccharum Technologies only. This is separate from business sign-in.
        </p>
        <form onSubmit={login} className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className="w-full rounded-lg border px-3 py-2.5 text-sm"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full rounded-lg border px-3 py-2.5 text-sm"
          />
          {error && <p className="text-sm text-red-700">{error}</p>}

      <section className="space-y-4 rounded-2xl border bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Operational Health
            </h2>
            <p className="text-xs text-slate-500">
              LINDA services, backups and background jobs
            </p>
          </div>
          <div className="flex items-center gap-3">
            {health && (
              <span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${stateStyle(health.state)}`}>
                {stateLabel(health.state)}
              </span>
            )}
            <button
              type="button"
              onClick={() => void loadHealth()}
              disabled={healthLoading}
              className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
            >
              {healthLoading && <Loader2 size={15} className="animate-spin" />}
              {healthLoading ? "Refreshing" : "Refresh"}
            </button>
          </div>
        </div>

        {healthError && (
          <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {healthError}
          </p>
        )}

        {!health && !healthError && (
          <p className="text-sm text-slate-500">Loading operational health…</p>
        )}

        {health && (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border p-3">
                <p className="text-xs font-medium uppercase text-slate-500">Local backups</p>
                <span className={`mt-2 inline-block rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${stateStyle(health.local_backup.state)}`}>
                  {stateLabel(health.local_backup.state)}
                </span>
                <p className="mt-3 text-xs text-slate-600">
                  Last backup: {formatDate(health.local_backup.last_backup_at)}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  Age: {health.local_backup.age_hours == null
                    ? "Not available"
                    : `${health.local_backup.age_hours.toFixed(1)} hours`}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  Size: {health.local_backup.size_mb == null
                    ? "Not available"
                    : `${health.local_backup.size_mb.toFixed(2)} MB`}
                </p>
              </div>

              <div className="rounded-xl border p-3">
                <p className="text-xs font-medium uppercase text-slate-500">Off-site backups</p>
                <span className={`mt-2 inline-block rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${stateStyle(health.offsite_backup.state)}`}>
                  {stateLabel(health.offsite_backup.state)}
                </span>
                <p className="mt-3 text-xs text-slate-600">
                  Enabled: {health.offsite_backup.enabled == null
                    ? "Unknown"
                    : health.offsite_backup.enabled ? "Yes" : "No"}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  Last successful backup: {formatDate(health.offsite_backup.last_ok_at)}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  Last attempt: {formatDate(health.offsite_backup.finished_at)}
                </p>
              </div>

              <div className="rounded-xl border p-3">
                <p className="text-xs font-medium uppercase text-slate-500">Scheduler</p>
                <span className={`mt-2 inline-block rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${stateStyle(health.scheduler.state)}`}>
                  {stateLabel(health.scheduler.state)}
                </span>
                <p className="mt-3 text-xs text-slate-600">
                  Heartbeat: {formatDate(health.scheduler.heartbeat_at)}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  Failing jobs: {health.scheduler.failing?.length ?? 0}
                </p>
                {health.scheduler.failing && health.scheduler.failing.length > 0 && (
                  <p className="mt-2 break-words text-xs text-red-700">
                    {health.scheduler.failing.join(", ")}
                  </p>
                )}
              </div>
            </div>

            <div className="border-t pt-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold text-slate-900">Incident history</h3>
                <span className="text-xs text-slate-500">
                  {incidents?.active ?? 0} active · {incidents?.total ?? 0} recorded
                </span>
              </div>

              {!incidents || incidents.incidents.length === 0 ? (
                <p className="mt-3 text-sm text-slate-500">
                  No incidents recorded.
                </p>
              ) : (
                <div className="mt-3 space-y-2">
                  {incidents.incidents.map((incident) => (
                    <div
                      key={`${incident.component}-${incident.opened_at}`}
                      className="rounded-xl border p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-slate-900">
                          {incident.label}
                        </p>
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${stateStyle(incident.status)}`}>
                          {incident.status}
                        </span>
                      </div>
                      <p className="mt-1 text-xs capitalize text-slate-600">
                        State: {stateLabel(incident.state)}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Opened: {formatDate(incident.opened_at)}
                        {incident.resolved_at
                          ? ` · Resolved: ${formatDate(incident.resolved_at)}`
                          : ""}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Alert email: {incident.alert_notified ? "Sent" : "Not sent"}
                        {incident.status === "resolved"
                          ? ` · Recovery email: ${incident.recovery_notified ? "Sent" : "Not sent"}`
                          : ""}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <p className="text-right text-xs text-slate-400">
              Last refreshed: {formatDate(lastHealthRefresh)}
              {" · "}Automatic refresh every 60 seconds
            </p>
          </>
        )}
      </section>
          <button className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white">
            Sign in
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-4 sm:p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Businesses</h1>
        <button
          onClick={() => {
            sessionStorage.removeItem(KEY);
            setToken(null);
          }}
          className="text-sm text-slate-600 hover:underline"
        >
          Sign out
        </button>
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}

      {pricing && (
        <section className="space-y-4 rounded-2xl border bg-white p-4">
          <h2 className="font-semibold text-slate-900">
            Plans (rands per month, before VAT)
          </h2>
          {plans.map((pl) => (
            <form
              key={pl.id + JSON.stringify(pl)}
              onSubmit={(e) => void savePlan(e, pl)}
              onChange={() => setPriceSaved(false)}
              className="grid grid-cols-2 gap-3 rounded-xl border p-3 sm:grid-cols-6"
            >
              <p className="col-span-2 text-xs font-semibold uppercase text-slate-500 sm:col-span-6">
                {pl.business_type === "funeral" ? "Funeral" : "Other business"}
              </p>
              {[
                ["name", "Name", pl.name, "text"],
                ["base", "Price excl. VAT", pl.base_price_cents / 100, "number"],
                ["staff", "Staff included", pl.included_staff, "number"],
                ["branches", "Branches included", pl.included_branches, "number"],
                ["xstaff", "Each extra staff", pl.extra_staff_cents / 100, "number"],
                ["xbranch", "Each extra branch", pl.extra_branch_cents / 100, "number"],
              ].map(([name, label, value, type]) => (
                <label key={name as string} className="text-xs text-slate-500">
                  {label}
                  <input
                    name={name as string}
                    type={type as string}
                    min={0}
                    step="0.01"
                    defaultValue={value as string | number}
                    className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm text-slate-900"
                  />
                </label>
              ))}
              <label className="flex items-center gap-2 text-xs text-slate-500">
                <input name="active" type="checkbox" defaultChecked={pl.is_active} />
                Offered
              </label>
              <button className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white">
                Save plan
              </button>
            </form>
          ))}

          <form
            key={JSON.stringify(pricing)}
            onSubmit={savePricing}
            onChange={() => setPriceSaved(false)}
            className="grid grid-cols-2 gap-3 border-t pt-3 sm:grid-cols-4"
          >
            <label className="text-xs text-slate-500">
              VAT %
              <input
                name="vat"
                type="number"
                min={0}
                max={100}
                defaultValue={pricing.vat_percent}
                className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm text-slate-900"
              />
            </label>
            <label className="col-span-2 text-xs text-slate-500 sm:col-span-3">
              Note shown under the prices
              <input
                name="note"
                maxLength={200}
                defaultValue={pricing.price_note ?? ""}
                className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm text-slate-900"
              />
            </label>
            <div className="col-span-2 flex items-center gap-3 sm:col-span-4">
              <button className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
                Save VAT and note
              </button>
              {priceSaved && <span className="text-sm text-green-700">Saved</span>}
            </div>
          </form>

          <div className="flex flex-wrap items-end gap-3 border-t pt-3">
            <label className="text-xs text-slate-500">
              Statements for
              <input
                type="month"
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className="mt-1 block rounded-lg border px-2 py-1.5 text-sm text-slate-900"
              />
            </label>
            <button
              type="button"
              onClick={() => void downloadStatements()}
              className="rounded-lg border px-4 py-2 text-sm font-semibold text-slate-900"
            >
              Download CSV
            </button>
          </div>
        </section>
      )}

      {rows.map((r) => (
        <section key={r.id} className="space-y-3 rounded-2xl border bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold text-slate-900">
              {r.name}
              <span className="ml-2 text-sm font-normal text-slate-500">
                {r.plan} · {rands(r.monthly_cents)} / month excl. VAT
              </span>
            </p>
            <div className="flex gap-2">
              <select
                aria-label="Plan"
                value={r.tier}
                disabled={busy === r.id}
                onChange={(e) =>
                  void save(r, { tier: e.target.value, apply_tier_defaults: true })
                }
                className="rounded-lg border px-2 py-1.5 text-sm"
              >
                {TIERS.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
              <select
                aria-label="Status"
                value={r.status}
                disabled={busy === r.id}
                onChange={(e) => void save(r, { status: e.target.value })}
                className="rounded-lg border px-2 py-1.5 text-sm"
              >
                {STATUSES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
              {busy === r.id && <Loader2 className="animate-spin" size={18} />}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {LIMIT_KEYS.map(([key, label]) => (
              <label key={key} className="text-xs text-slate-500">
                {label}: {r.usage[label] ?? 0} used / limit
                <input
                  type="number"
                  min={1}
                  defaultValue={r.limits[label] ?? ""}
                  placeholder="unlimited"
                  onBlur={(e) => {
                    const v = e.target.value === "" ? null : Number(e.target.value);
                    if (v !== (r.limits[label] ?? null)) void save(r, { [key]: v });
                  }}
                  className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm text-slate-900"
                />
              </label>
            ))}
          </div>
          <label className="block text-xs text-slate-500">
            Special standard price in rands (blank = normal price)
            <input
              type="number"
              min={0}
              step="0.01"
              defaultValue={
                r.base_price_override_cents === null
                  ? ""
                  : r.base_price_override_cents / 100
              }
              placeholder="normal price"
              onBlur={(e) => {
                const v =
                  e.target.value === "" ? null : Math.round(Number(e.target.value) * 100);
                if (v !== r.base_price_override_cents)
                  void save(r, { base_price_override_cents: v });
              }}
              className="mt-1 w-40 rounded-lg border px-2 py-1.5 text-sm text-slate-900"
            />
          </label>
        </section>
      ))}
    </main>
  );
}
