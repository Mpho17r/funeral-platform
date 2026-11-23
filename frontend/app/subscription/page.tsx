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
  const [checkout, setCheckout] = useState<{ action: string; fields: Record<string, string>; amount_cents: number } | null>(null);
  const [startingPayment, setStartingPayment] = useState(false);
  const [paymentNotice, setPaymentNotice] = useState("");

  async function load() {
    const { data } = await api.get<Subscription>("/subscription");
    setSubscription(data);
    setSelected(data.plan.code);
  }

  useEffect(() => {
    load().catch(() => setError("We could not load your subscription details. Please try again."));
    const query = new URLSearchParams(window.location.search);
    if (query.get("payment") === "returned") setPaymentNotice("Thank you. We are waiting for PayFast to confirm your payment. Access will update only after server verification.");
    if (query.get("payment") === "cancelled") setPaymentNotice("Payment was cancelled. Your subscription has not been activated.");
  }, []);

  async function startPayment() {
    setStartingPayment(true);
    setError("");
    setCheckout(null);
    try {
      const { data } = await api.post("/subscription/payfast/checkout");
      setCheckout(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "We could not start PayFast checkout. Please try again.");
    } finally {
      setStartingPayment(false);
    }
  }

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
        <h2 className="font-semibold text-slate-900">Pay your LINDA subscription</h2>
        <p className="mt-2 text-sm text-slate-600">Your monthly amount is calculated by LINDA from your selected plan, staff and branch usage. You will complete payment on PayFast's secure hosted checkout.</p>
        <button type="button" onClick={startPayment} disabled={startingPayment} className="mt-4 rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">
          {startingPayment ? "Preparing secure checkout…" : "Continue to PayFast"}
        </button>
        {checkout && (
          <form action={checkout.action} method="POST" className="mt-4">
            {Object.entries(checkout.fields).map(([name, value]) => (
              <input key={name} type="hidden" name={name} value={value} />
            ))}
            <p className="mb-3 text-sm text-slate-700">Amount to pay: <strong>{rands(checkout.amount_cents)} ZAR</strong></p>
            <button type="submit" className="rounded-lg bg-emerald-700 px-4 py-3 text-sm font-semibold text-white">Open PayFast secure payment</button>
          </form>
        )}
        {paymentNotice && <p role="status" className="mt-3 text-sm text-blue-800">{paymentNotice}</p>}
        <p className="mt-3 text-xs text-slate-500">Returning from PayFast does not itself activate your subscription. LINDA waits for a verified payment notification. Your workspace data is retained while access is paused.</p>
      </section>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <Link href="/pricing" className="text-sm font-medium underline">View all plans</Link>
    </main>
  );
}
