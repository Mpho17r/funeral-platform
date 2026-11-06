"use client";

import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

import { ErrorNote } from "@/components/Notices";
import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { Subscription, monthLabel, rands } from "@/lib/pricing";

export default function SubscriptionPage() {
  const router = useRouter();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Subscription>("/subscription")
      .then((r) => setSub(r.data))
      .catch((err) =>
        setError(getApiErrorMessage(err, "We could not load your plan.")),
      );
  }, []);

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
          <section className="grid gap-4 sm:grid-cols-2">
            <Tile
              label="Staff accounts"
              value={sub.usage["staff accounts"] ?? 0}
              note={`${sub.pricing.included_staff} included, then ${rands(
                sub.pricing.extra_staff_cents,
              )} each`}
            />
            <Tile
              label="Branches"
              value={sub.usage["branches"] ?? 0}
              note={`${sub.pricing.included_branches} included, then ${rands(
                sub.pricing.extra_branch_cents,
              )} each`}
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
                      <span className="text-[var(--fos-text-muted)]">
                        {" "}
                        · {line.detail}
                      </span>
                    </span>
                    <span>{rands(line.amount_cents)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 flex justify-between border-t border-[var(--fos-border)] pt-3 font-semibold text-[var(--fos-text)]">
                <span>Amount due this month</span>
                <span data-testid="amount-due">
                  {rands(bill.amount_due_cents)}
                </span>
              </p>
              <p className="mt-3 text-xs text-[var(--fos-text-muted)]">
                Based on your busiest day this month ({bill.peak_staff} staff,{" "}
                {bill.peak_branches} branch
                {bill.peak_branches === 1 ? "" : "es"}). At today&apos;s size
                the price would be {rands(bill.now.total_cents)} a month.
              </p>
              {sub.pricing.price_note && (
                <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                  {sub.pricing.price_note}
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
      <p className="mt-1 text-3xl font-semibold text-[var(--fos-text)]">
        {value}
      </p>
      <p className="mt-1 text-xs text-[var(--fos-text-muted)]">{note}</p>
    </div>
  );
}
