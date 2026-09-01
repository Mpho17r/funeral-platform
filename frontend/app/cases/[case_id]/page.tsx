"use client";

import { useEffect, useState } from "react";
import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  CreditCard,
  FileText,
  HeartHandshake,
  Loader2,
  MapPin,
  Phone,
  UserRound,
  Users,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

type CaseSummary = {
  id: string;
  case_number: string;
  deceased_full_name: string;
  date_of_birth: string | null;
  date_of_death: string | null;
  next_of_kin_name: string | null;
  next_of_kin_phone: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  services: {
    total: number;
    pending: number;
    confirmed: number;
  };
  tasks: {
    total: number;
    pending: number;
    completed: number;
  };
  payments: {
    total: number;
    amount_paid: number;
  };
  financial: {
    total: number;
    amount_paid: number;
    balance: number;
    credit: number;
  } | null;
};

function formatMoney(value: number | string) {
  return Number(value || 0).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDate(value: string | null) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatStatus(status?: string | null) {
  if (!status) {
    return "Unknown";
  }

  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getStatusClass(status: string) {
  switch (status) {
    case "completed":
    case "confirmed":
      return "bg-emerald-50 text-emerald-700";

    case "in_progress":
      return "bg-blue-50 text-blue-700";

    case "cancelled":
      return "bg-red-50 text-red-700";

    case "closed":
      return "bg-slate-100 text-slate-700";

    default:
      return "bg-amber-50 text-amber-700";
  }
}

function MoneyCard({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-xl border bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-2 text-xl font-bold text-slate-900">
        R {formatMoney(value)}
      </p>
    </div>
  );
}

function ActivityCard({
  icon,
  title,
  total,
  detail,
}: {
  icon: React.ReactNode;
  title: string;
  total: number;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm transition">
      <div className="flex items-start justify-between">
        <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
          {icon}
        </div>

        <ChevronRight
          size={18}
          className="text-slate-300"
        />
      </div>

      <p className="mt-5 text-sm font-medium text-slate-500">
        {title}
      </p>

      <p className="mt-1 text-2xl font-bold text-slate-900">
        {total}
      </p>

      <p className="mt-1 text-xs text-slate-400">
        {detail}
      </p>
    </div>
  );
}

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 text-slate-400">
        {icon}
      </div>

      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
          {label}
        </p>

        <p className="mt-1 break-words text-sm font-medium text-slate-700">
          {value}
        </p>
      </div>
    </div>
  );
}

export default function CaseDetailsPage() {
  const router = useRouter();
  const params = useParams();

  const caseId = String(params.case_id || "");

  const [summary, setSummary] = useState<CaseSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    if (!caseId) {
      setError("Case ID is missing from the URL.");
      setLoading(false);
      return;
    }

    loadCase();
  }, [caseId, router]);

  async function loadCase() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<CaseSummary>(
        `/cases/${caseId}/summary`
      );

      setSummary(response.data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setError(
        err.response?.data?.detail ||
          "Unable to load funeral case."
      );
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Loader2
            size={20}
            className="animate-spin"
          />
          Loading case...
        </div>
      </main>
    );
  }

  if (error || !summary) {
    return (
      <main className="min-h-screen bg-slate-100 p-6">
        <div className="mx-auto max-w-3xl">
          <button
            type="button"
            onClick={() => router.push("/cases")}
            className="mb-6 flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft size={17} />
            Back to Cases
          </button>

          <div className="rounded-2xl border border-red-200 bg-red-50 p-6">
            <p className="text-sm font-medium text-red-700">
              {error || "Case not found."}
            </p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100">
      {/* HEADER */}
      <header className="border-b bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5 md:px-8">
          <button
            type="button"
            onClick={() => router.push("/cases")}
            className="mb-5 flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft size={17} />
            Back to Cases
          </button>

          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-slate-900 p-3 text-white">
                  <FileText size={22} />
                </div>

                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h1 className="text-2xl font-bold text-slate-900">
                      {summary.deceased_full_name}
                    </h1>

                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${getStatusClass(
                        summary.status
                      )}`}
                    >
                      {formatStatus(summary.status)}
                    </span>
                  </div>

                  <p className="mt-1 text-sm text-slate-500">
                    Case #{summary.case_number}
                  </p>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={loadCase}
              className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* CONTENT */}
      <section className="mx-auto max-w-7xl p-6 md:p-8">
        {/* CASE INFORMATION */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
              <UserRound size={20} />
            </div>

            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Case Information
              </h2>

              <p className="text-sm text-slate-500">
                Important details for this funeral case.
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <InfoRow
              icon={<UserRound size={17} />}
              label="Deceased"
              value={summary.deceased_full_name}
            />

            <InfoRow
              icon={<CalendarDays size={17} />}
              label="Date of Birth"
              value={formatDate(summary.date_of_birth)}
            />

            <InfoRow
              icon={<CalendarDays size={17} />}
              label="Date of Death"
              value={formatDate(summary.date_of_death)}
            />

            <InfoRow
              icon={<Users size={17} />}
              label="Next of Kin"
              value={summary.next_of_kin_name || "—"}
            />

            <InfoRow
              icon={<Phone size={17} />}
              label="Next of Kin Phone"
              value={summary.next_of_kin_phone || "—"}
            />

            <InfoRow
              icon={<FileText size={17} />}
              label="Case Number"
              value={summary.case_number}
            />
          </div>
        </div>

        {/* FINANCIAL SUMMARY */}
        <div className="mt-6 rounded-2xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
              <CreditCard size={20} />
            </div>

            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Financial Summary
              </h2>

              <p className="text-sm text-slate-500">
                Current case financial position
              </p>
            </div>
          </div>

          {summary.financial ? (
            <div className="mt-6 grid gap-4 md:grid-cols-4">
              <MoneyCard
                label="Total"
                value={summary.financial.total}
              />

              <MoneyCard
                label="Amount Paid"
                value={summary.financial.amount_paid}
              />

              <MoneyCard
                label="Balance"
                value={summary.financial.balance}
              />

              <MoneyCard
                label="Credit"
                value={summary.financial.credit}
              />
            </div>
          ) : (
            <div className="mt-6 rounded-xl bg-slate-50 p-5 text-sm text-slate-500">
              No financial record has been created for this case yet.
            </div>
          )}
        </div>

        {/* ACTIVITY CARDS */}
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          {/* SERVICES */}
          <button
            type="button"
            onClick={() => {
              console.log("SERVICES CLICKED", caseId);
              router.push(`/cases/${caseId}/services`);
            }}
            className="relative z-10 block w-full cursor-pointer text-left focus:outline-none focus:ring-2 focus:ring-slate-300"
          >
            <ActivityCard
              icon={<HeartHandshake size={19} />}
              title="Services"
              total={summary.services.total}
              detail={`${summary.services.pending} pending • ${summary.services.confirmed} confirmed`}
            />
          </button>

          {/* TASKS */}
          <button
            type="button"
            onClick={() => {
              console.log("TASKS CLICKED", caseId);
              router.push(`/cases/${caseId}/tasks`);
            }}
            className="relative z-10 block w-full cursor-pointer text-left focus:outline-none focus:ring-2 focus:ring-slate-300"
          >
            <ActivityCard
              icon={<CheckCircle2 size={19} />}
              title="Tasks"
              total={summary.tasks.total}
              detail={`${summary.tasks.pending} pending • ${summary.tasks.completed} completed`}
            />
          </button>

          {/* PAYMENTS */}
          <ActivityCard
            icon={<CreditCard size={19} />}
            title="Payments"
            total={summary.payments.total}
            detail={`R ${formatMoney(
              summary.payments.amount_paid
            )} paid`}
          />
        </div>

        {/* QUICK ACTIONS */}
        <div className="mt-6 rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900">
            Case Management
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Manage the different parts of this funeral case.
          </p>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <button
              type="button"
              onClick={() =>
                router.push(`/cases/${caseId}/contacts`)
              }
              className="flex items-center justify-between rounded-xl border p-4 text-left hover:bg-slate-50"
            >
              <div className="flex items-center gap-3">
                <Users
                  size={20}
                  className="text-slate-500"
                />

                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Contacts
                  </p>

                  <p className="text-xs text-slate-500">
                    Manage family and other contacts
                  </p>
                </div>
              </div>

              <ChevronRight
                size={18}
                className="text-slate-400"
              />
            </button>

            <button
              type="button"
              onClick={() =>
                router.push(`/cases/${caseId}/services`)
              }
              className="flex items-center justify-between rounded-xl border p-4 text-left hover:bg-slate-50"
            >
              <div className="flex items-center gap-3">
                <HeartHandshake
                  size={20}
                  className="text-slate-500"
                />

                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Services
                  </p>

                  <p className="text-xs text-slate-500">
                    Manage funeral services
                  </p>
                </div>
              </div>

              <ChevronRight
                size={18}
                className="text-slate-400"
              />
            </button>

            <button
              type="button"
              onClick={() =>
                router.push(`/cases/${caseId}/financial`)
              }
              className="flex items-center justify-between rounded-xl border p-4 text-left hover:bg-slate-50"
            >
              <div className="flex items-center gap-3">
                <CreditCard
                  size={20}
                  className="text-slate-500"
                />

                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Financials
                  </p>

                  <p className="text-xs text-slate-500">
                    Manage case finances
                  </p>
                </div>
              </div>

              <ChevronRight
                size={18}
                className="text-slate-400"
              />
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}