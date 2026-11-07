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
