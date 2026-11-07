"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getToken } from "@/lib/auth";
import { getApiErrorMessage } from "@/lib/format";
import { LindaLockup } from "@/components/LindaLogo";
import { PlanPicker } from "@/components/PlanPicker";
import { Subscription } from "@/lib/pricing";

/** Shown right after registering: which plan fits the business. */
export default function ChoosePlanPage() {
  const router = useRouter();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api
      .get<Subscription>("/subscription")
      .then((r) => {
        setSub(r.data);
        setSelected(r.data.plan.code);
      })
      .catch((err) =>
        setError(getApiErrorMessage(err, "We could not load the plans.")),
      );
  }, [router]);

  async function confirm() {
    setSaving(true);
    setError("");
    try {
      await api.put("/subscription/plan", { plan_code: selected });
      router.push("/dashboard");
    } catch (err) {
      setError(getApiErrorMessage(err, "We could not save your plan."));
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f5f6f8] px-4 py-10 dark:bg-slate-950">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 text-[var(--linda-navy)] dark:text-white">
          <LindaLockup markSize={36} />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
          Choose your plan
        </h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Your trial is free. Pick the plan closest to your business now. You
          can change it any time in Settings.
        </p>

        {error && (
          <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </p>
        )}

        {sub && (
          <div className="mt-6">
            <PlanPicker
              plans={sub.plans}
              vatPercent={sub.vat_percent}
              selected={selected}
              onSelect={setSelected}
            />
            <div className="mt-6 flex items-center gap-4">
              <button
                type="button"
                onClick={() => void confirm()}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {saving && <Loader2 className="animate-spin" size={16} />}
                Continue with this plan
              </button>
              <button
                type="button"
                onClick={() => router.push("/dashboard")}
                className="text-sm text-slate-600 underline-offset-4 hover:underline"
              >
                Decide later
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
