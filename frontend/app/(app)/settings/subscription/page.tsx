"use client";

import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

import { ErrorNote } from "@/components/Notices";
import { PlanPicker } from "@/components/PlanPicker";
import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { Subscription, monthLabel, rands } from "@/lib/pricing";

export default function SubscriptionPage() {
  const router = useRouter();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [error, setError] = useState("");
  const [changing, setChanging] = useState(false);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);

  function load() {
    api
      .get<Subscription>("/subscription")
      .then((r) => {
        setSub(r.data);
        setSelected(r.data.plan.code);
      })
      .catch((err) =>
        setError(getApiErrorMessage(err, "We could not load your plan.")),
      );
  }

  useEffect(load, []);

  async function savePlan() {
    setSaving(true);
    setError("");
    try {
      await api.put("/subscription/plan", { plan_code: selected });
      setChanging(false);
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "We could not change your plan."));
    } finally {
      setSaving(false);
    }
  }

  const bill = sub?.bill;

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
      <button
        type="button"
        onClick={() => router.push("/settings")}
        className="flex items-center gap-1.5 text-sm text-[var(--fos-text-muted)] hover:text-[var(--fos-text)]"
      >
        <ArrowLeft size={16} /> Settings
      </button>

      <header>
        <h1 className="text-2xl font-semibold text-[var(--fos-text)]">
          Plan &amp; billing
        </h1>
        <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
          What you use and what it costs each month.
        </p>
      </header>

      {error && <ErrorNote message={error} />}

      {sub && (
        <>
          <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm text-[var(--fos-text-muted)]">Your plan</p>
                <p className="text-xl font-semibold text-[var(--fos-text)]">
                  {sub.plan.name}
                </p>
                <p className="text-xs text-[var(--fos-text-muted)]">
                  {rands(sub.plan.base_price_cents)} excl. VAT ·{" "}
                  {sub.plan.included_branches} branch
                  {sub.plan.included_branches === 1 ? "" : "es"} · up to{" "}
                  {sub.plan.included_staff} staff
                </p>
              </div>
              {bill && (
                <button
                  type="button"
                  onClick={() => setChanging((v) => !v)}
                  className="rounded-lg border border-[var(--fos-border)] px-4 py-2 text-sm font-medium text-[var(--fos-text)]"
                >
                  {changing ? "Cancel" : "Change plan"}
                </button>
              )}
            </div>

            {changing && (
              <div className="mt-5">
                <PlanPicker
                  plans={sub.plans}
                  vatPercent={sub.vat_percent}
                  selected={selected}
                  onSelect={setSelected}
                />
                <button
                  type="button"
                  disabled={saving || selected === sub.plan.code}
                  onClick={() => void savePlan()}
                  className="mt-4 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Switch to this plan
                </button>
              </div>
            )}
          </section>

          <section className="grid gap-4 sm:grid-cols-2">
            <Tile
              label="Staff accounts"
              value={sub.usage["staff accounts"] ?? 0}
              note={`${sub.plan.included_staff} included, then ${rands(
                sub.plan.extra_staff_cents,
              )} each excl. VAT`}
            />
            <Tile
              label="Branches"
              value={sub.usage["branches"] ?? 0}
              note={`${sub.plan.included_branches} included, then ${rands(
                sub.plan.extra_branch_cents,
              )} each excl. VAT`}
            />
          </section>

          {bill ? (
            <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6">
              <h2 className="text-lg font-semibold text-[var(--fos-text)]">
                {monthLabel(bill.year, bill.month)}
              </h2>
              {bill.note && (
                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                  {bill.note}
                </p>
              )}
              <ul className="mt-4 space-y-1.5 text-sm text-[var(--fos-text-secondary)]">
                {bill.lines.map((line) => (
                  <li key={line.label} className="flex justify-between gap-4">
                    <span>
                      {line.label}
                      {line.quantity > 1 && (
                        <span className="text-[var(--fos-text-muted)]">
                          {" "}
                          · {line.quantity} × {rands(line.unit_cents)}
                        </span>
                      )}
                    </span>
                    <span>{rands(line.amount_cents)}</span>
                  </li>
                ))}
                <li className="flex justify-between gap-4 border-t border-[var(--fos-border)] pt-1.5">
                  <span>Total excl. VAT</span>
                  <span>{rands(bill.list_total_cents)}</span>
                </li>
                <li className="flex justify-between gap-4">
                  <span>VAT ({bill.vat_percent}%)</span>
                  <span>
                    {rands(bill.list_total_incl_vat_cents - bill.list_total_cents)}
                  </span>
                </li>
              </ul>
              <p className="mt-4 flex justify-between border-t border-[var(--fos-border)] pt-3 font-semibold text-[var(--fos-text)]">
                <span>Amount due this month (incl. VAT)</span>
                <span data-testid="amount-due">
                  {rands(bill.amount_due_incl_vat_cents)}
                </span>
              </p>
              <p className="mt-3 text-xs text-[var(--fos-text-muted)]">
                Based on your busiest day this month ({bill.peak_staff} staff,{" "}
                {bill.peak_branches} branch
                {bill.peak_branches === 1 ? "" : "es"}). At today&apos;s size
                the price would be {rands(bill.now.total_incl_vat_cents)} a
                month incl. VAT.
              </p>
              {sub.price_note && (
                <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                  {sub.price_note}
                </p>
              )}
            </section>
          ) : (
            <p className="text-sm text-[var(--fos-text-muted)]">
              The bill is shown to the people who run the business.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Tile({
  label,
  value,
  note,
}: {
  label: string;
  value: number;
  note: string;
}) {
  return (
    <div className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
      <p className="text-sm text-[var(--fos-text-muted)]">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-[var(--fos-text)]">{value}</p>
      <p className="mt-1 text-xs text-[var(--fos-text-muted)]">{note}</p>
    </div>
  );
}
