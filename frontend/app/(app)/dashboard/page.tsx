"use client";

import {
  ArrowRight,
  CalendarDays,
  ChevronRight,
  CreditCard,
  FilePlus2,
  HeartHandshake,
  RefreshCw,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
import {
  titleOf,
  useCurrentUser,
} from "@/components/CurrentUserProvider";
import { removeToken } from "@/lib/auth";

type RecentCase = {
  id: string;
  case_number: string;
  deceased_full_name: string;
  funeral_date: string | null;
  status: string;
  created_at: string;
};

type UpcomingFuneral = {
  id: string;
  case_number: string;
  deceased_full_name: string;
  funeral_date: string;
  funeral_venue: string | null;
};

type DashboardSummary = {
  total_cases: number;
  active_cases: number;
  upcoming_funeral_count: number;
  outstanding_balance: string;
  total_revenue: string;
  amount_paid: string;
  total_credit: string;
  total_families: number | null;
  recent_cases: RecentCase[];
  upcoming_funerals: UpcomingFuneral[];
};

/* ============================================================
   FORMATTING
============================================================ */

function formatCurrency(
  value: string | number | null | undefined,
) {
  const amount = Number(value ?? 0);

  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "ZAR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function parseDate(date: string | null | undefined) {
  if (!date) {
    return null;
  }

  const parsed = new Date(date);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatDate(date: string | null | undefined) {
  if (!date) {
    return "Not scheduled";
  }

  const parsed = parseDate(date);

  if (!parsed) {
    return date;
  }

  return parsed.toLocaleDateString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function daysUntil(date: string) {
  const parsed = parseDate(date);

  if (!parsed) {
    return null;
  }

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);

  const startOfTarget = new Date(parsed);
  startOfTarget.setHours(0, 0, 0, 0);

  return Math.round(
    (startOfTarget.getTime() - startOfToday.getTime()) /
      86_400_000,
  );
}

function describeDaysUntil(days: number | null) {
  if (days === null) return "";
  if (days < 0) return "Past";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return `In ${days} days`;
}

function greeting() {
  const hour = new Date().getHours();

  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function getStatusStyle(status: string) {
  switch (status) {
    case "open":
      return {
        pill: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
        dot: "bg-blue-500",
      };

    case "confirmed":
      return {
        pill: "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
        dot: "bg-indigo-500",
      };

    case "in_progress":
      return {
        pill: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
        dot: "bg-amber-500",
      };

    case "completed":
      return {
        pill: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300",
        dot: "bg-green-500",
      };

    case "cancelled":
      return {
        pill: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
        dot: "bg-red-500",
      };

    default:
      return {
        pill: "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] dark:bg-slate-800 dark:text-slate-300",
        dot: "bg-slate-400",
      };
  }
}

/* ============================================================
   PAGE
============================================================ */

export default function DashboardPage() {
  const router = useRouter();

  const [dashboard, setDashboard] =
    useState<DashboardSummary | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadDashboard() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<DashboardSummary>(
        "/dashboard/summary",
      );

      setDashboard(response.data);
    } catch (err) {
      console.error("Dashboard error:", err);

      const response = (
        err as {
          response?: { status?: number; data?: { detail?: unknown } };
        }
      ).response;

      if (response?.status === 401) {
        removeToken();
        router.push("/login");
        return;
      }

      setError(
        typeof response?.data?.detail === "string" &&
          response.data.detail
          ? response.data.detail
          : "We couldn't load the dashboard. Try refreshing.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function fetchDashboard() {
      try {
        const response = await api.get<DashboardSummary>(
          "/dashboard/summary",
        );

        if (!cancelled) {
          setDashboard(response.data);
          setError("");
        }
      } catch (err) {
        if (cancelled) return;

        console.error("Dashboard error:", err);

        const response = (
          err as {
            response?: { status?: number; data?: { detail?: unknown } };
          }
        ).response;

        if (response?.status === 401) {
          removeToken();
          router.push("/login");
          return;
        }

        setError(
          typeof response?.data?.detail === "string" &&
            response.data.detail
            ? response.data.detail
            : "We couldn't load the dashboard. Try refreshing.",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchDashboard();

    return () => {
      cancelled = true;
    };
  }, [router]);

  const { user: currentUser } = useCurrentUser();
  const firstName = currentUser?.full_name?.trim().split(/\s+/)[0];

  const today = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  const placeholder = "–";

  const upcoming = dashboard?.upcoming_funerals ?? [];
  const recent = dashboard?.recent_cases ?? [];

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
      {/* HEADER */}
      <header className="fos-rise flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-[var(--fos-text)] sm:text-4xl dark:text-white">
            {greeting()}
            {firstName ? `, ${firstName}` : ""}
          </h1>

          <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
            {currentUser ? (
              <>
                <span className="font-medium text-[var(--fos-text-secondary)]">
                  {titleOf(currentUser)}
                </span>
                <span aria-hidden="true"> · </span>
              </>
            ) : null}
            {today}
          </p>
        </div>

        <button
          type="button"
          onClick={loadDashboard}
          disabled={loading}
          className="flex h-10 items-center gap-2 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 text-sm font-medium text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)] disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          <RefreshCw
            size={16}
            className={loading ? "animate-spin" : ""}
          />
          Refresh
        </button>
      </header>

      {error && (
        <div
          role="alert"
          className="mt-6 rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300"
        >
          {error}
        </div>
      )}

      {/* COMING UP + MONEY */}
      <div
        className="fos-rise mt-8 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]"
        style={{ animationDelay: "60ms" }}
      >
        {/* Funeral schedule is the lead: it is what the day is organised around */}
        <section
          id="upcoming-funerals"
          aria-labelledby="coming-up-heading"
          className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="flex items-center justify-between gap-4 px-5 pb-3 pt-5 sm:px-6">
            <div>
              <h2
                id="coming-up-heading"
                className="font-display text-2xl text-[var(--fos-text)] dark:text-white"
              >
                Coming up
              </h2>

              <p className="mt-0.5 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                Funerals in the next 30 days
              </p>
            </div>

            <Link
              href="/calendar"
              className="flex items-center gap-1 rounded-md text-sm font-medium text-[var(--fos-text-secondary)] hover:text-[var(--fos-text)] dark:text-[var(--fos-text-muted)] dark:hover:text-white"
            >
              Calendar
              <ArrowRight size={15} />
            </Link>
          </div>

          {loading ? (
            <p className="px-6 py-10 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
              Loading funerals…
            </p>
          ) : upcoming.length ? (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {upcoming.map((funeral) => {
                const parsed = parseDate(funeral.funeral_date);
                const days = daysUntil(funeral.funeral_date);

                return (
                  <li key={funeral.id}>
                    <Link
                      href={`/cases/${funeral.id}`}
                      className="group flex items-center gap-4 px-5 py-4 transition hover:bg-[var(--fos-page)] sm:px-6 dark:hover:bg-slate-800/60"
                    >
                      <div
                        aria-hidden="true"
                        className="flex w-14 shrink-0 flex-col items-center rounded-lg bg-[var(--fos-surface-muted)] py-2 text-[var(--fos-text)] dark:bg-slate-800 dark:text-white"
                      >
                        <span className="font-display text-2xl leading-none">
                          {parsed ? parsed.getDate() : placeholder}
                        </span>

                        <span className="mt-1 text-xs font-medium text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                          {parsed
                            ? parsed.toLocaleDateString("en-ZA", {
                                month: "short",
                              })
                            : ""}
                        </span>
                      </div>

                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold text-[var(--fos-text)] dark:text-white">
                          {funeral.deceased_full_name}
                        </p>

                        <p className="mt-0.5 truncate text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                          {funeral.funeral_venue || "Venue not set"}
                          <span className="text-slate-300 dark:text-[var(--fos-text-secondary)]">
                            {"  |  "}
                          </span>
                          {funeral.case_number}
                        </p>
                      </div>

                      <span
                        className={`hidden shrink-0 rounded-full px-3 py-1 text-xs font-semibold sm:inline-block ${
                          days !== null && days <= 1
                            ? "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
                            : "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] dark:bg-slate-800 dark:text-slate-300"
                        }`}
                      >
                        {describeDaysUntil(days)}
                      </span>

                      <ChevronRight
                        size={18}
                        className="shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-[var(--fos-text-muted)] dark:text-[var(--fos-text-secondary)]"
                      />
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="px-6 pb-10 pt-6 text-center">
              <CalendarDays
                size={28}
                className="mx-auto text-slate-300 dark:text-[var(--fos-text-secondary)]"
              />

              <p className="mt-3 font-medium text-[var(--fos-text)] dark:text-slate-100">
                No funerals in the next 30 days
              </p>

              <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                When a case gets a funeral date, it appears here.
              </p>

              <Link
                href="/cases"
                className="mt-5 inline-flex h-10 items-center rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 dark:bg-[var(--fos-surface)] dark:text-[var(--fos-text)] dark:hover:bg-[var(--fos-border)]"
              >
                Open cases
              </Link>
            </div>
          )}
        </section>

        {/* Money */}
        <section
          aria-labelledby="money-heading"
          className="flex flex-col rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 sm:p-6 dark:border-slate-800 dark:bg-slate-900"
        >
          <h2
            id="money-heading"
            className="font-display text-2xl text-[var(--fos-text)] dark:text-white"
          >
            Money
          </h2>

          <div className="mt-5 rounded-xl bg-amber-50 px-4 py-4 dark:bg-amber-950/40">
            <p className="text-sm text-amber-800 dark:text-amber-300">
              Still to collect
            </p>

            <p className="mt-1 text-3xl font-semibold tracking-tight text-[var(--fos-text)] tabular-nums dark:text-white">
              {loading
                ? placeholder
                : formatCurrency(dashboard?.outstanding_balance)}
            </p>
          </div>

          <dl className="mt-5 divide-y divide-slate-100 text-sm dark:divide-slate-800">
            <MoneyRow
              label="Total billed"
              value={
                loading
                  ? placeholder
                  : formatCurrency(dashboard?.total_revenue)
              }
            />

            <MoneyRow
              label="Paid so far"
              value={
                loading
                  ? placeholder
                  : formatCurrency(dashboard?.amount_paid)
              }
            />

            <MoneyRow
              label="Credit held"
              value={
                loading
                  ? placeholder
                  : formatCurrency(dashboard?.total_credit)
              }
            />
          </dl>

          <Link
            href="/cases"
            className="mt-auto inline-flex items-center gap-1 pt-5 text-sm font-medium text-[var(--fos-text-secondary)] hover:text-[var(--fos-text)] dark:text-[var(--fos-text-muted)] dark:hover:text-white"
          >
            Review case balances
            <ArrowRight size={15} />
          </Link>
        </section>
      </div>

      {/* FIGURES */}
      <dl
        className="fos-rise mt-6 grid grid-cols-1 divide-y divide-slate-200 rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] sm:grid-cols-3 sm:divide-x sm:divide-y-0 dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900"
        style={{ animationDelay: "120ms" }}
      >
        <Figure
          label="Active cases"
          note={
            loading
              ? "Loading"
              : `of ${dashboard?.total_cases ?? 0} in total`
          }
          value={
            loading
              ? placeholder
              : String(dashboard?.active_cases ?? 0)
          }
          href="/cases"
        />

        <Figure
          label="Funerals this month"
          note="Scheduled in the next 30 days"
          value={
            loading
              ? placeholder
              : String(dashboard?.upcoming_funeral_count ?? 0)
          }
          href="/calendar"
        />

        <Figure
          label="Families"
          note="Registered with you"
          value={
            loading
              ? placeholder
              : String(dashboard?.total_families ?? 0)
          }
          href="/families"
        />
      </dl>

      {/* RECENT CASES + QUICK ACTIONS */}
      <div
        className="fos-rise mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]"
        style={{ animationDelay: "180ms" }}
      >
        <section
          aria-labelledby="recent-heading"
          className="overflow-hidden rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="flex items-center justify-between gap-4 px-5 pb-3 pt-5 sm:px-6">
            <h2
              id="recent-heading"
              className="font-display text-2xl text-[var(--fos-text)] dark:text-white"
            >
              Recent cases
            </h2>

            <Link
              href="/cases"
              className="flex items-center gap-1 rounded-md text-sm font-medium text-[var(--fos-text-secondary)] hover:text-[var(--fos-text)] dark:text-[var(--fos-text-muted)] dark:hover:text-white"
            >
              All cases
              <ArrowRight size={15} />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left">
              <thead>
                <tr className="border-y border-[var(--fos-border)] bg-[var(--fos-page)] text-[var(--fos-text-muted)] dark:border-slate-800 dark:bg-slate-800/50 dark:text-[var(--fos-text-muted)]">
                  <th className="px-5 py-3 font-medium sm:px-6">
                    Case
                  </th>
                  <th className="px-3 py-3 font-medium">
                    Deceased
                  </th>
                  <th className="px-3 py-3 font-medium">
                    Funeral date
                  </th>
                  <th className="px-5 py-3 font-medium sm:px-6">
                    Status
                  </th>
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-6 py-10 text-center text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]"
                    >
                      Loading cases…
                    </td>
                  </tr>
                ) : recent.length ? (
                  recent.map((item) => {
                    const style = getStatusStyle(item.status);

                    return (
                      <tr
                        key={item.id}
                        onClick={() =>
                          router.push(`/cases/${item.id}`)
                        }
                        className="cursor-pointer border-b border-[var(--fos-border)] transition last:border-0 hover:bg-[var(--fos-page)] dark:border-slate-800 dark:hover:bg-slate-800/60"
                      >
                        <td className="px-5 py-3.5 text-sm font-semibold text-[var(--fos-text)] sm:px-6 dark:text-white">
                          <Link
                            href={`/cases/${item.id}`}
                            onClick={(event) =>
                              event.stopPropagation()
                            }
                            className="rounded hover:underline"
                          >
                            {item.case_number}
                          </Link>
                        </td>

                        <td className="px-3 py-3.5 text-sm text-[var(--fos-text-secondary)] dark:text-slate-300">
                          {item.deceased_full_name}
                        </td>

                        <td className="px-3 py-3.5 text-sm text-[var(--fos-text-secondary)] dark:text-[var(--fos-text-muted)]">
                          {formatDate(item.funeral_date)}
                        </td>

                        <td className="px-5 py-3.5 sm:px-6">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${style.pill}`}
                          >
                            <span
                              aria-hidden="true"
                              className={`h-1.5 w-1.5 rounded-full ${style.dot}`}
                            />
                            {formatStatus(item.status)}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-6 py-12 text-center"
                    >
                      <p className="font-medium text-[var(--fos-text)] dark:text-slate-100">
                        No cases yet
                      </p>

                      <p className="mt-1 text-sm text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
                        Create your first case to start tracking
                        arrangements and payments.
                      </p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section
          aria-labelledby="actions-heading"
          className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 sm:p-6 dark:border-slate-800 dark:bg-slate-900"
        >
          <h2
            id="actions-heading"
            className="font-display text-2xl text-[var(--fos-text)] dark:text-white"
          >
            Start something
          </h2>

          <ul className="mt-4 space-y-2">
            <QuickAction
              href="/cases"
              icon={<FilePlus2 size={18} />}
              title="New case"
              description="Register a death and start arrangements"
            />

            <QuickAction
              href="/families"
              icon={<Users size={18} />}
              title="Add a family"
              description="Record a client family and its contacts"
            />

            <QuickAction
              href="/cases"
              icon={<CreditCard size={18} />}
              title="Record a payment"
              description="Open a case and add a payment"
            />

            <QuickAction
              href="/memberships"
              icon={<HeartHandshake size={18} />}
              title="Memberships"
              description="Check cover and contributions"
            />
          </ul>
        </section>
      </div>
    </div>
  );
}

/* ============================================================
   SMALL PIECES
============================================================ */

function MoneyRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-3">
      <dt className="text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
        {label}
      </dt>

      <dd className="font-semibold text-[var(--fos-text)] tabular-nums dark:text-white">
        {value}
      </dd>
    </div>
  );
}

function Figure({
  label,
  note,
  value,
  href,
}: {
  label: string;
  note: string;
  value: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-baseline justify-between gap-4 px-5 py-5 transition first:rounded-t-2xl last:rounded-b-2xl hover:bg-[var(--fos-page)] sm:px-6 sm:first:rounded-l-2xl sm:first:rounded-tr-none sm:last:rounded-r-2xl sm:last:rounded-bl-none dark:hover:bg-slate-800/60"
    >
      <div>
        <dt className="text-sm font-medium text-[var(--fos-text-secondary)] dark:text-slate-200">
          {label}
        </dt>

        <p className="mt-0.5 text-xs text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
          {note}
        </p>
      </div>

      <dd className="font-display text-4xl leading-none text-[var(--fos-text)] tabular-nums dark:text-white">
        {value}
      </dd>
    </Link>
  );
}

function QuickAction({
  href,
  icon,
  title,
  description,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <li>
      <Link
        href={href}
        className="group flex items-center gap-3 rounded-xl border border-[var(--fos-border)] p-3.5 transition hover:border-[var(--fos-border)] hover:bg-[var(--fos-page)] dark:border-slate-700 dark:hover:border-slate-600 dark:hover:bg-slate-800"
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] dark:bg-slate-800 dark:text-slate-200">
          {icon}
        </span>

        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-[var(--fos-text)] dark:text-white">
            {title}
          </span>

          <span className="mt-0.5 block text-xs text-[var(--fos-text-muted)] dark:text-[var(--fos-text-muted)]">
            {description}
          </span>
        </span>

        <ChevronRight
          size={16}
          className="shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-[var(--fos-text-muted)] dark:text-[var(--fos-text-secondary)]"
        />
      </Link>
    </li>
  );
}
