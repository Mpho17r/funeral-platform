"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Check, Minus, Plus } from "lucide-react";

import api from "@/lib/api";
import { LindaLockup } from "@/components/LindaLogo";
import {
  PLATFORM_OWNER,
  PLATFORM_SLOGAN,
} from "@/lib/platform";
import { Pricing, Quote, rands } from "@/lib/pricing";

export default function PricingPage() {
  const [pricing, setPricing] = useState<Pricing | null>(null);
  const [staff, setStaff] = useState(5);
  const [branches, setBranches] = useState(1);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api
      .get<Pricing>("/pricing")
      .then((r) => {
        setPricing(r.data);
        setStaff(r.data.included_staff);
        setBranches(Math.max(1, r.data.included_branches));
      })
      .catch(() => setFailed(true));
  }, []);

  useEffect(() => {
    if (!pricing) return;
    const timer = setTimeout(() => {
      api
        .get<Quote>("/pricing/quote", { params: { staff, branches } })
        .then((r) => setQuote(r.data))
        .catch(() => setFailed(true));
    }, 200);
    return () => clearTimeout(timer);
  }, [pricing, staff, branches]);

  const clamp = (n: number, max: number) =>
    Math.max(0, Math.min(max, Number.isFinite(n) ? Math.floor(n) : 0));

  return (
    <div className="min-h-screen bg-[#f5f6f8] px-4 py-10 dark:bg-slate-950">
      <div className="mx-auto max-w-3xl">
        <div className="mb-10 flex items-center justify-between text-[var(--linda-navy)] dark:text-white">
          <LindaLockup markSize={36} />
          <Link
            href="/login"
            className="text-sm font-medium underline-offset-4 hover:underline"
          >
            Sign in
          </Link>
        </div>

        <h1 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
          Simple, honest pricing
        </h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          One monthly price for the whole platform. Grow your team or add
          branches and only pay a little more for each one. Nothing is ever
          locked or switched off.
        </p>

        {failed && !pricing && (
          <p className="mt-8 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            We could not load the prices right now. Please try again shortly.
          </p>
        )}

        {pricing && (
          <>
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
                <p className="text-sm text-slate-500">Standard plan</p>
                <p className="mt-1 text-3xl font-semibold text-slate-900 dark:text-white">
                  {rands(pricing.base_price_cents)}
                  <span className="text-base font-normal text-slate-500">
                    {" "}
                    / month
                  </span>
                </p>
                <ul className="mt-4 space-y-2 text-sm text-slate-700 dark:text-slate-300">
                  <li className="flex gap-2">
                    <Check size={16} className="mt-0.5 shrink-0" />
                    {pricing.included_staff} staff accounts
                  </li>
                  <li className="flex gap-2">
                    <Check size={16} className="mt-0.5 shrink-0" />
                    {pricing.included_branches} branch
                    {pricing.included_branches === 1 ? "" : "es"}
                  </li>
                  <li className="flex gap-2">
                    <Check size={16} className="mt-0.5 shrink-0" />
                    Every feature included
                  </li>
                </ul>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
                <p className="text-sm text-slate-500">Each extra staff account</p>
                <p className="mt-1 text-3xl font-semibold text-slate-900 dark:text-white">
                  +{rands(pricing.extra_staff_cents)}
                  <span className="text-base font-normal text-slate-500">
                    {" "}
                    / month
                  </span>
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
                <p className="text-sm text-slate-500">Each extra branch</p>
                <p className="mt-1 text-3xl font-semibold text-slate-900 dark:text-white">
                  +{rands(pricing.extra_branch_cents)}
                  <span className="text-base font-normal text-slate-500">
                    {" "}
                    / month
                  </span>
                </p>
              </div>
            </div>

            <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                Work out your price
              </h2>

              <div className="mt-4 grid gap-5 sm:grid-cols-2">
                <Stepper
                  label="Staff accounts"
                  value={staff}
                  onChange={(n) => setStaff(clamp(n, 10000))}
                />
                <Stepper
                  label="Branches"
                  value={branches}
                  onChange={(n) => setBranches(Math.max(1, clamp(n, 1000)))}
                />
              </div>

              {quote && (
                <div className="mt-6 border-t border-slate-200 pt-4 dark:border-slate-800">
                  <ul className="space-y-1.5 text-sm text-slate-700 dark:text-slate-300">
                    {quote.lines.map((line) => (
                      <li
                        key={line.label}
                        className="flex justify-between gap-4"
                      >
                        <span>
                          {line.label}
                          <span className="text-slate-500">
                            {" "}
                            · {line.detail}
                          </span>
                        </span>
                        <span>{rands(line.amount_cents)}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-4 flex items-baseline justify-between text-lg font-semibold text-slate-900 dark:text-white">
                    <span>Per month</span>
                    <span data-testid="quote-total">
                      {rands(quote.total_cents)}
                    </span>
                  </p>
                </div>
              )}
            </div>

            {pricing.price_note && (
              <p className="mt-4 text-sm text-slate-500">
                {pricing.price_note}
              </p>
            )}
            <p className="mt-2 text-sm text-slate-500">
              The bill follows the busiest day of the month, so a short spike
              in staff is counted but removing people later brings next
              month&apos;s price back down.
            </p>
          </>
        )}

        <p className="mt-10 text-center text-xs text-slate-500">
          LINDA | {PLATFORM_SLOGAN} Powered by {PLATFORM_OWNER}.
        </p>
      </div>
    </div>
  );
}

function Stepper({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
}) {
  const button =
    "flex h-10 w-10 items-center justify-center rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800";
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label={`Fewer ${label.toLowerCase()}`}
          className={button}
          onClick={() => onChange(value - 1)}
        >
          <Minus size={16} />
        </button>
        <input
          type="number"
          min={0}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-10 w-24 rounded-lg border border-slate-300 bg-white px-3 text-center text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
        />
        <button
          type="button"
          aria-label={`More ${label.toLowerCase()}`}
          className={button}
          onClick={() => onChange(value + 1)}
        >
          <Plus size={16} />
        </button>
      </div>
    </div>
  );
}
