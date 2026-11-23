"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { Plan, Subscription, rands } from "@/lib/pricing";

export default function SubscriptionPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    const { data } = await api.get<Subscription>("/subscription");
    setSubscription(data);
    setSelected(data.plan.code);
  }

  useEffect(() => {
    load().catch(() => setError("We could not load your subscription details. Please try again."));
  }, []);

  async function savePlan() {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      await api.put("/subscription/plan", { plan_code: selected });
      await load();
    } catch {
      setError("We could not update your plan. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const expired = subscription?.status === "trial" && subscription.trial_ends_at
    ? new Date(subscription.trial_ends_at).getTime() <= Date.now()
    : false;

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6 py-12">
      <header>
        <p className="text-sm font-semibold tracking-widest text-slate-500">LINDA BILLING</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Your subscription</h1>
        <p className="mt-2 text-sm text-slate-600">Manage your plan and keep your business workspace active.</p>
      </header>

      {expired && (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-5 text-amber-950">
          <h2 className="font-semibold">Your 7-day free trial has ended</h2>
          <p className="mt-2 text-sm">Choose your plan below. Your business data is safe, and access will be restored after a successful payment.</p>
        </section>
      )}

      {subscription && (
        <section className="space-y-4 rounded-xl border border-slate-200 p-5">
          <div>
            <p className="text-sm text-slate-500">Current plan</p>
            <p className="text-xl font-semibold">{subscription.plan.name}</p>
            <p className="text-sm text-slate-600">{rands(subscription.plan.base_price_cents)} per month</p>
          </div>
          <label className="block text-sm font-medium">
            Change plan
            <select className="mt-2 w-full rounded-lg border border-slate-300 p-3" value={selected} onChange={(e) => setSelected(e.target.value)}>
              {subscription.plans.map((plan: Plan) => (
                <option key={plan.code} value={plan.code}>{plan.name} — {rands(plan.base_price_cents)} / month</option>
              ))}
            </select>
          </label>
          <button type="button" onClick={savePlan} disabled={saving || selected === subscription.plan.code} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {saving ? "Saving…" : "Save plan"}
          </button>
          {subscription.trial_ends_at && (
            <p className="text-xs text-slate-500">Trial ended / ends: {new Date(subscription.trial_ends_at).toLocaleString("en-ZA")}</p>
          )}
        </section>
      )}

      <section className="rounded-xl border border-slate-200 p-5">
        <h2 className="font-semibold text-slate-900">Payment setup</h2>
        <p className="mt-2 text-sm text-slate-600">Secure online checkout is not connected yet. LINDA will only activate a paid subscription after the payment provider confirms the transaction. No payment has been taken on this page.</p>
        <p className="mt-2 text-xs text-slate-500">Your workspace data is retained while access is paused.</p>
      </section>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <Link href="/pricing" className="text-sm font-medium underline">View all plans</Link>
    </main>
  );
}
