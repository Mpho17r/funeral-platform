"use client";

import {
  Activity,
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  CreditCard,
  FileText,
  HeartHandshake,
  LayoutDashboard,
  LogOut,
  RefreshCw,
  Settings,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
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
        "/dashboard/summary"
      );

      setDashboard(response.data);
    } catch (err: any) {
      console.error("Dashboard error:", err);

      if (err?.response?.status === 401) {
        removeToken();
        router.push("/login");
        return;
      }

      setError(
        err?.response?.data?.detail ||
          "Unable to load dashboard data."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  function handleLogout() {
    removeToken();
    router.push("/login");
  }

  function formatCurrency(value: string | number | null | undefined) {
    const amount = Number(value ?? 0);

    return new Intl.NumberFormat("en-ZA", {
      style: "currency",
      currency: "ZAR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  }

  function formatDate(date: string | null | undefined) {
    if (!date) {
      return "Not scheduled";
    }

    const parsed = new Date(date);

    if (Number.isNaN(parsed.getTime())) {
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

  function getStatusClass(status: string) {
    switch (status) {
      case "open":
        return "bg-blue-50 text-blue-700";

      case "confirmed":
        return "bg-indigo-50 text-indigo-700";

      case "in_progress":
        return "bg-amber-50 text-amber-700";

      case "completed":
        return "bg-green-50 text-green-700";

      case "closed":
        return "bg-slate-100 text-slate-700";

      case "cancelled":
        return "bg-red-50 text-red-700";

      default:
        return "bg-slate-100 text-slate-700";
    }
  }

  return (
    <main className="min-h-screen bg-slate-100">
      <div className="flex min-h-screen">

        {/* =====================================================
            SIDEBAR
        ===================================================== */}

        <aside className="hidden w-64 flex-col border-r bg-slate-950 text-white md:flex">

          {/* Logo */}

          <div className="flex h-20 items-center border-b border-slate-800 px-6">
            <div className="flex items-center gap-3">

              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-950">
                <span className="text-lg font-bold">
                  F
                </span>
              </div>

              <div>
                <h1 className="font-bold">
                  FuneralOS
                </h1>

                <p className="text-xs text-slate-400">
                  Funeral Management
                </p>
              </div>

            </div>
          </div>

          {/* Navigation */}

          <nav className="flex-1 space-y-1 px-4 py-6">

            <SidebarItem
              icon={<LayoutDashboard size={18} />}
              label="Dashboard"
              active
              onClick={() => router.push("/dashboard")}
            />

            <SidebarItem
              icon={<FileText size={18} />}
              label="Cases"
              onClick={() => router.push("/cases")}
            />

            <SidebarItem
  icon={<Users size={18} />}
  label="Families"
  onClick={() => router.push("/families")}
/>

            <SidebarItem
              icon={<CreditCard size={18} />}
              label="Payments"
              onClick={() => {
                alert("Payments are managed inside each case.");
              }}
            />

            <SidebarItem
              icon={<HeartHandshake size={18} />}
              label="Services"
              onClick={() => {
                alert("Services are managed inside each case.");
              }}
            />

            <SidebarItem
              icon={<CalendarDays size={18} />}
              label="Calendar"
              onClick={() => {
                alert("Calendar module coming next.");
              }}
            />

            <SidebarItem
              icon={<Activity size={18} />}
              label="Reports"
              onClick={() => {
                alert("Reports module coming next.");
              }}
            />

            <SidebarItem
              icon={<Settings size={18} />}
              label="Settings"
              onClick={() => {
                alert("Settings module coming next.");
              }}
            />

          </nav>

          {/* Logout */}

          <div className="border-t border-slate-800 p-4">

            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-sm text-slate-300 transition hover:bg-slate-900 hover:text-white"
            >
              <LogOut size={18} />
              Logout
            </button>

          </div>

        </aside>

        {/* =====================================================
            MAIN CONTENT
        ===================================================== */}

        <div className="flex min-w-0 flex-1 flex-col">

          {/* TOP BAR */}

          <header className="flex h-20 items-center justify-between border-b bg-white px-6">

            <div>
              <h2 className="text-xl font-bold text-slate-900">
                Dashboard
              </h2>

              <p className="text-sm text-slate-500">
                Overview of your funeral operations
              </p>
            </div>

            <div className="flex items-center gap-4">

              <button
                type="button"
                onClick={loadDashboard}
                disabled={loading}
                className="rounded-lg border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
                title="Refresh dashboard"
              >
                <RefreshCw
                  size={18}
                  className={loading ? "animate-spin" : ""}
                />
              </button>

              <div className="flex items-center gap-3">

                <div className="hidden text-right sm:block">
                  <p className="text-sm font-semibold text-slate-900">
                    Administrator
                  </p>

                  <p className="text-xs text-slate-500">
                    Admin
                  </p>
                </div>

                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                  A
                </div>

              </div>

            </div>

          </header>

          {/* CONTENT */}

          <section className="flex-1 p-6 md:p-8">

            <div className="mx-auto max-w-7xl">

              {/* Welcome */}

              <div className="mb-8">

                <h3 className="text-2xl font-bold text-slate-900">
                  Welcome back 👋
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  Here's what's happening with your funeral operations.
                </p>

              </div>

              {/* ERROR */}

              {error && (
                <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
                  {error}
                </div>
              )}

              {/* =================================================
                  STATISTICS
              ================================================= */}

              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">

                <StatCard
                  title="Active Cases"
                  value={
                    loading
                      ? "..."
                      : String(dashboard?.active_cases ?? 0)
                  }
                  description={
                    loading
                      ? "Loading..."
                      : `Out of ${dashboard?.total_cases ?? 0} total cases`
                  }
                  icon={<BriefcaseBusiness size={20} />}
                  onClick={() => router.push("/cases")}
                />

                <StatCard
                  title="Upcoming Funerals"
                  value={
                    loading
                      ? "..."
                      : String(
                          dashboard?.upcoming_funeral_count ?? 0
                        )
                  }
                  description="Next 30 days"
                  icon={<CalendarDays size={20} />}
                  onClick={() => {
                    if (
                      (dashboard?.upcoming_funeral_count ?? 0) > 0
                    ) {
                      document
                        .getElementById("upcoming-funerals")
                        ?.scrollIntoView({
                          behavior: "smooth",
                        });
                    }
                  }}
                />

                <StatCard
                  title="Outstanding Balance"
                  value={
                    loading
                      ? "..."
                      : formatCurrency(
                          dashboard?.outstanding_balance
                        )
                  }
                  description="Across all cases"
                  icon={<CreditCard size={20} />}
                  onClick={() => router.push("/cases")}
                />

                <StatCard
                  title="Total Families"
                  value={
                    loading
                      ? "..."
                      : String(
                          dashboard?.total_families ?? 0
                        )
                  }
                  description="Registered families"
                  icon={<Users size={20} />}
                  onClick={() => {
                    alert("Families module coming next.");
                  }}
                />

              </div>

              {/* =================================================
                  MAIN GRID
              ================================================= */}

              <div className="mt-8 grid gap-6 xl:grid-cols-3">

                {/* RECENT CASES */}

                <div className="overflow-hidden rounded-2xl border bg-white shadow-sm xl:col-span-2">

                  <div className="flex items-center justify-between border-b px-6 py-5">

                    <div>
                      <h3 className="font-semibold text-slate-900">
                        Recent Cases
                      </h3>

                      <p className="mt-1 text-xs text-slate-500">
                        Latest funeral cases added to the system
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => router.push("/cases")}
                      className="flex items-center gap-1 text-sm font-medium text-slate-700 hover:text-slate-950"
                    >
                      View all
                      <ArrowUpRight size={15} />
                    </button>

                  </div>

                  <div className="overflow-x-auto">

                    <table className="w-full min-w-[650px]">

                      <thead>

                        <tr className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">

                          <th className="px-6 py-4 font-medium">
                            Case
                          </th>

                          <th className="px-6 py-4 font-medium">
                            Deceased
                          </th>

                          <th className="px-6 py-4 font-medium">
                            Funeral Date
                          </th>

                          <th className="px-6 py-4 font-medium">
                            Status
                          </th>

                        </tr>

                      </thead>

                      <tbody>

                        {loading ? (
                          <tr>
                            <td
                              colSpan={4}
                              className="px-6 py-10 text-center text-sm text-slate-500"
                            >
                              Loading recent cases...
                            </td>
                          </tr>
                        ) : dashboard?.recent_cases?.length ? (
                          dashboard.recent_cases.map((item) => (
                            <CaseRow
                              key={item.id}
                              caseNumber={item.case_number}
                              deceased={item.deceased_full_name}
                              date={formatDate(item.funeral_date)}
                              status={formatStatus(item.status)}
                              statusClass={getStatusClass(
                                item.status
                              )}
                              onClick={() =>
                                router.push(
                                  `/cases/${item.id}`
                                )
                              }
                            />
                          ))
                        ) : (
                          <tr>
                            <td
                              colSpan={4}
                              className="px-6 py-10 text-center text-sm text-slate-500"
                            >
                              No funeral cases found.
                            </td>
                          </tr>
                        )}

                      </tbody>

                    </table>

                  </div>

                </div>

                {/* QUICK ACTIONS */}

                <div className="rounded-2xl border bg-white p-6 shadow-sm">

                  <h3 className="font-semibold text-slate-900">
                    Quick Actions
                  </h3>

                  <p className="mt-1 text-xs text-slate-500">
                    Common tasks
                  </p>

                  <div className="mt-5 space-y-3">

                    <QuickAction
                      icon={<FileText size={18} />}
                      title="Create New Case"
                      description="Register a new funeral case"
                      onClick={() => router.push("/cases")}
                    />

                    <QuickAction
                      icon={<Users size={18} />}
                      title="Add Family"
                      description="Register a family/client"
                      onClick={() => {
                        alert("Families module coming next.");
                      }}
                    />

                    <QuickAction
                      icon={<CreditCard size={18} />}
                      title="Record Payment"
                      description="Add a case payment"
                      onClick={() => {
                        router.push("/cases");
                      }}
                    />

                    <QuickAction
                      icon={<HeartHandshake size={18} />}
                      title="Manage Services"
                      description="View funeral services"
                      onClick={() => {
                        router.push("/cases");
                      }}
                    />

                  </div>

                </div>

              </div>

              {/* =================================================
                  BOTTOM CARDS
              ================================================= */}

              <div className="mt-6 grid gap-6 md:grid-cols-2">

                {/* FINANCIAL */}

                <div className="rounded-2xl border bg-white p-6 shadow-sm">

                  <div className="flex items-center justify-between">

                    <div>
                      <h3 className="font-semibold text-slate-900">
                        Financial Overview
                      </h3>

                      <p className="mt-1 text-xs text-slate-500">
                        Current financial position
                      </p>
                    </div>

                    <CreditCard
                      size={20}
                      className="text-slate-400"
                    />

                  </div>

                  <div className="mt-6 grid grid-cols-2 gap-5">

                    <div>

                      <p className="text-xs text-slate-500">
                        Total Revenue
                      </p>

                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {loading
                          ? "..."
                          : formatCurrency(
                              dashboard?.total_revenue
                            )}
                      </p>

                    </div>

                    <div>

                      <p className="text-xs text-slate-500">
                        Amount Paid
                      </p>

                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {loading
                          ? "..."
                          : formatCurrency(
                              dashboard?.amount_paid
                            )}
                      </p>

                    </div>

                    <div>

                      <p className="text-xs text-slate-500">
                        Outstanding
                      </p>

                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {loading
                          ? "..."
                          : formatCurrency(
                              dashboard?.outstanding_balance
                            )}
                      </p>

                    </div>

                    <div>

                      <p className="text-xs text-slate-500">
                        Credit
                      </p>

                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {loading
                          ? "..."
                          : formatCurrency(
                              dashboard?.total_credit
                            )}
                      </p>

                    </div>

                  </div>

                </div>

                {/* UPCOMING FUNERALS */}

                <div
                  id="upcoming-funerals"
                  className="rounded-2xl border bg-white p-6 shadow-sm"
                >

                  <div className="flex items-center justify-between">

                    <div>
                      <h3 className="font-semibold text-slate-900">
                        Upcoming Funerals
                      </h3>

                      <p className="mt-1 text-xs text-slate-500">
                        Scheduled services for the next 30 days
                      </p>
                    </div>

                    <CalendarDays
                      size={20}
                      className="text-slate-400"
                    />

                  </div>

                  <div className="mt-5 space-y-4">

                    {loading ? (
                      <p className="py-5 text-sm text-slate-500">
                        Loading upcoming funerals...
                      </p>
                    ) : dashboard?.upcoming_funerals?.length ? (
                      dashboard.upcoming_funerals.map(
                        (funeral) => (
                          <UpcomingFuneral
                            key={funeral.id}
                            caseNumber={
                              funeral.case_number
                            }
                            deceased={
                              funeral.deceased_full_name
                            }
                            date={formatDate(
                              funeral.funeral_date
                            )}
                            venue={
                              funeral.funeral_venue
                            }
                          />
                        )
                      )
                    ) : (
                      <div className="rounded-xl bg-slate-50 px-4 py-6 text-center">

                        <CalendarDays
                          size={24}
                          className="mx-auto text-slate-400"
                        />

                        <p className="mt-2 text-sm font-medium text-slate-700">
                          No upcoming funerals
                        </p>

                        <p className="mt-1 text-xs text-slate-500">
                          There are no scheduled funerals in the next
                          30 days.
                        </p>

                      </div>
                    )}

                  </div>

                </div>

              </div>

            </div>

          </section>

        </div>

      </div>
    </main>
  );
}

/* ============================================================
   SIDEBAR ITEM
============================================================ */

function SidebarItem({
  icon,
  label,
  active = false,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-sm transition ${
        active
          ? "bg-white text-slate-950"
          : "text-slate-400 hover:bg-slate-900 hover:text-white"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

/* ============================================================
   STAT CARD
============================================================ */

function StatCard({
  title,
  value,
  description,
  icon,
  onClick,
}: {
  title: string;
  value: string;
  description: string;
  icon: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-2xl border bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="flex items-center justify-between">

        <p className="text-sm font-medium text-slate-500">
          {title}
        </p>

        <div className="rounded-lg bg-slate-100 p-2 text-slate-700">
          {icon}
        </div>

      </div>

      <p className="mt-4 text-2xl font-bold text-slate-900">
        {value}
      </p>

      <p className="mt-1 text-xs text-slate-500">
        {description}
      </p>

    </button>
  );
}

/* ============================================================
   CASE ROW
============================================================ */

function CaseRow({
  caseNumber,
  deceased,
  date,
  status,
  statusClass,
  onClick,
}: {
  caseNumber: string;
  deceased: string;
  date: string;
  status: string;
  statusClass: string;
  onClick?: () => void;
}) {
  return (
    <tr
      onClick={onClick}
      className="cursor-pointer border-b transition hover:bg-slate-50"
    >
      <td className="px-6 py-4 text-sm font-semibold text-slate-900">
        {caseNumber}
      </td>

      <td className="px-6 py-4 text-sm text-slate-600">
        {deceased}
      </td>

      <td className="px-6 py-4 text-sm text-slate-600">
        {date}
      </td>

      <td className="px-6 py-4">
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${statusClass}`}
        >
          {status}
        </span>
      </td>
    </tr>
  );
}

/* ============================================================
   QUICK ACTION
============================================================ */

function QuickAction({
  icon,
  title,
  description,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-4 rounded-xl border border-slate-200 p-4 text-left transition hover:border-slate-300 hover:bg-slate-50"
    >
      <div className="rounded-lg bg-slate-100 p-2 text-slate-700">
        {icon}
      </div>

      <div>
        <p className="text-sm font-semibold text-slate-900">
          {title}
        </p>

        <p className="mt-1 text-xs text-slate-500">
          {description}
        </p>
      </div>
    </button>
  );
}

/* ============================================================
   UPCOMING FUNERAL
============================================================ */

function UpcomingFuneral({
  caseNumber,
  deceased,
  date,
  venue,
}: {
  caseNumber: string;
  deceased: string;
  date: string;
  venue: string | null;
}) {
  return (
    <div className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0">

      <div>
        <p className="text-sm font-medium text-slate-900">
          {deceased}
        </p>

        <p className="mt-1 text-xs text-slate-500">
          {caseNumber}
          {venue ? ` • ${venue}` : ""}
        </p>
      </div>

      <p className="ml-4 whitespace-nowrap text-sm font-semibold text-slate-700">
        {date}
      </p>

    </div>
  );
}
