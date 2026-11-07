"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import api from "@/lib/api";
import { LindaLockup } from "@/components/LindaLogo";
import { PlanPicker } from "@/components/PlanPicker";
import { PLATFORM_OWNER, PLATFORM_SLOGAN } from "@/lib/platform";
import { PublicPricing } from "@/lib/pricing";

type Kind = "funeral" | "general";

export default function PricingPage() {
  const [pricing, setPricing] = useState<PublicPricing | null>(null);
  const [kind, setKind] = useState<Kind>("funeral");
  const [selected, setSelected] = useState<Record<Kind, string>>({
    funeral: "",
    general: "",
  });
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api
      .get<PublicPricing>("/pricing")
      .then((r) => setPricing(r.data))
      .catch(() => setFailed(true));
  }, []);

  const tab = (k: Kind, label: string) => (
    <button
      type="button"
      onClick={() => setKind(k)}
      aria-pressed={kind === k}
      className={`rounded-full px-4 py-2 text-sm font-medium ${
        kind === k
          ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
          : "bg-white text-slate-700 hover:bg-slate-100 dark:bg-slate-900 dark:text-slate-300"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-[#f5f6f8] px-4 py-10 dark:bg-slate-950">
      <div className="mx-auto max-w-4xl">
        <div className="mb-10 flex items-center justify-between text-[var(--linda-navy)] dark:text-white">
          <LindaLockup markSize={36} />
          <Link href="/login" className="text-sm font-medium underline-offset-4 hover:underline">
            Sign in
          </Link>
        </div>

        <h1 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
          Simple, honest pricing
        </h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Pick the plan that fits where you are. Every plan has every feature.
          Grow past what it includes and you only pay a little more for each
          extra person or branch. Nothing is ever locked.
        </p>

        <div className="mt-6 flex gap-2">
          {tab("funeral", "Funeral business")}
          {tab("general", "Other business")}
        </div>

        {failed && !pricing && (
          <p className="mt-8 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            We could not load the prices right now. Please try again shortly.
          </p>
        )}

        {pricing && (
          <div className="mt-6">
            <PlanPicker
              plans={pricing.plans[kind]}
              vatPercent={pricing.vat_percent}
              selected={selected[kind]}
              onSelect={(code) => setSelected((s) => ({ ...s, [kind]: code }))}
            />
            {pricing.price_note && (
              <p className="mt-4 text-sm text-slate-500">{pricing.price_note}</p>
            )}
            <p className="mt-2 text-sm text-slate-500">
              VAT is {pricing.vat_percent}%. The bill follows the busiest day of
              the month. Removing people brings next month&apos;s price back down.
            </p>
          </div>
        )}

        <p className="mt-10 text-center text-xs text-slate-500">
          LINDA | {PLATFORM_SLOGAN} Powered by {PLATFORM_OWNER}.
        </p>
      </div>
    </div>
  );
}
