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
};

const TIERS = ["starter", "growth", "professional", "enterprise"];
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

      {rows.map((r) => (
        <section key={r.id} className="space-y-3 rounded-2xl border bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold text-slate-900">{r.name}</p>
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
        </section>
      ))}
    </main>
  );
}
