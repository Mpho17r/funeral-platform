"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";

import api from "@/lib/api";
import { Plan, Quote, inclVat, rands } from "@/lib/pricing";

/**
 * The plans for one kind of business, with sliders to try a team size and
 * number of branches. Prices are shown with VAT first, and without it below.
 */
export function PlanPicker({
  plans,
  vatPercent,
  selected,
  onSelect,
}: {
  plans: Plan[];
  vatPercent: number;
  selected: string;
  onSelect: (code: string) => void;
}) {
  const plan = plans.find((p) => p.code === selected) ?? plans[0];
  if (!plan) return null;

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-3">
        {plans.map((p) => {
          const active = p.code === plan.code;
          return (
            <button
              key={p.code}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(p.code)}
              className={`rounded-2xl border p-5 text-left transition ${
                active
                  ? "border-slate-900 bg-white ring-2 ring-slate-900 dark:border-white dark:bg-slate-900 dark:ring-white"
                  : "border-slate-200 bg-white hover:border-slate-400 dark:border-slate-800 dark:bg-slate-900"
              }`}
            >
              <p className="text-sm font-medium text-slate-500">{p.name}</p>
              <p className="mt-1 text-3xl font-semibold text-slate-900 dark:text-white">
                {rands(inclVat(p.base_price_cents, vatPercent))}
                <span className="block text-sm font-normal text-slate-500">
                  per month incl. VAT
                </span>
              </p>
              <p className="text-xs text-slate-500">
                {rands(p.base_price_cents)} excl. VAT
              </p>
              <ul className="mt-4 space-y-1.5 text-sm text-slate-700 dark:text-slate-300">
                <li className="flex gap-2">
                  <Check size={16} className="mt-0.5 shrink-0" />
                  {p.included_branches} branch
                  {p.included_branches === 1 ? "" : "es"}
                </li>
                <li className="flex gap-2">
                  <Check size={16} className="mt-0.5 shrink-0" />
                  Up to {p.included_staff} staff
                </li>
                <li className="flex gap-2">
                  <Check size={16} className="mt-0.5 shrink-0" />
                  Extra staff {rands(p.extra_staff_cents)} each
                </li>
                <li className="flex gap-2">
                  <Check size={16} className="mt-0.5 shrink-0" />
                  Extra branch {rands(p.extra_branch_cents)} each
                </li>
              </ul>
              {p.tagline && (
                <p className="mt-3 text-xs text-slate-500">{p.tagline}</p>
              )}
            </button>
          );
        })}
      </div>

      <Calculator key={plan.code} plan={plan} />
    </div>
  );
}

function Calculator({ plan }: { plan: Plan }) {
  const [staff, setStaff] = useState(plan.included_staff);
  const [branches, setBranches] = useState(Math.max(1, plan.included_branches));
  const [quote, setQuote] = useState<Quote | null>(null);
  const code = plan.code;

  useEffect(() => {
    const timer = setTimeout(() => {
      api
        .get<Quote>("/pricing/quote", { params: { plan: code, staff, branches } })
        .then((r) => setQuote(r.data))
        .catch(() => setQuote(null));
    }, 150);
    return () => clearTimeout(timer);
  }, [code, staff, branches]);

  const maxStaff = Math.max(30, plan.included_staff * 4);
  const maxBranches = Math.max(10, plan.included_branches * 4);

  return (
      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
          How big is your team?
        </h2>
        <p className="text-sm text-slate-500">
          Slide to see the price on the {plan.name} plan. You can change this
          later.
        </p>

        <div className="mt-5 grid gap-6 sm:grid-cols-2">
          <Slider
            label="Staff accounts"
            value={staff}
            min={1}
            max={maxStaff}
            onChange={setStaff}
          />
          <Slider
            label="Branches"
            value={branches}
            min={1}
            max={maxBranches}
            onChange={setBranches}
          />
        </div>

        {quote && (
          <div className="mt-6 border-t border-slate-200 pt-4 dark:border-slate-800">
            <ul className="space-y-1.5 text-sm text-slate-700 dark:text-slate-300">
              {quote.lines.map((line) => (
                <li key={line.label} className="flex justify-between gap-4">
                  <span>
                    {line.label}
                    {line.quantity > 1 && (
                      <span className="text-slate-500">
                        {" "}
                        · {line.quantity} × {rands(line.unit_cents)}
                      </span>
                    )}
                  </span>
                  <span>{rands(line.amount_cents)}</span>
                </li>
              ))}
              <li className="flex justify-between gap-4 border-t border-slate-200 pt-1.5 dark:border-slate-800">
                <span>Total excl. VAT</span>
                <span>{rands(quote.total_cents)}</span>
              </li>
              <li className="flex justify-between gap-4">
                <span>VAT ({quote.vat_percent}%)</span>
                <span>{rands(quote.vat_cents)}</span>
              </li>
            </ul>
            <p className="mt-3 flex items-baseline justify-between text-lg font-semibold text-slate-900 dark:text-white">
              <span>Per month incl. VAT</span>
              <span data-testid="quote-total">
                {rands(quote.total_incl_vat_cents)}
              </span>
            </p>
          </div>
        )}
      </div>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (n: number) => void;
}) {
  return (
    <div>
      <label className="flex items-baseline justify-between text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        <span className="text-lg font-semibold text-slate-900 dark:text-white">
          {value}
        </span>
      </label>
      <input
        type="range"
        aria-label={label}
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-slate-900 dark:accent-white"
      />
    </div>
  );
}
