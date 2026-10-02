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
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";

import { useParams, useRouter } from "next/navigation";

import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

type FuneralCase = {
  id: string;
  business_id: string;
  case_number: string;
  membership_id: string | null;
  covered_dependent_id: string | null;
  deceased_full_name: string;
  date_of_birth: string | null;
  date_of_death: string | null;
  next_of_kin_name: string | null;
  next_of_kin_phone: string | null;
  funeral_date: string | null;
  funeral_venue: string | null;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type CaseSummary = {
  case: FuneralCase;
  contacts: {
    total: number;
  };
  tasks: {
    total: number;
    pending: number;
    completed: number;
  };
  documents: {
    total: number;
  };
  services: {
    total: number;
    pending: number;
    confirmed: number;
  };
  payments: {
    total: number;
    amount_paid: number | string;
  };
  financial: {
    total: number | string;
    amount_paid: number | string;
    balance: number | string;
    credit: number | string;
    status: string;
  } | null;
};

type Member = {
  id: string;
  business_id: string;
  member_number: string;
  first_name: string;
  last_name: string;
  status: string;
};

type MembershipPlan = {
  id: string;
  business_id: string;
  name: string;
  description: string | null;
  monthly_contribution: number | string;
  is_active: boolean;
};

type Membership = {
  id: string;
  business_id: string;
  member_id: string;
  plan_id: string;
  membership_number: string;
  start_date: string;
  status: string;
  next_due_date: string | null;
  arrears_since: string | null;
  lapsed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
};

type CoveredDependent = {
  id: string;
  business_id: string;
  membership_id: string;
  first_name: string;
  last_name: string;
  relationship: string;
  id_number: string | null;
  date_of_birth: string | null;
  phone: string | null;
  status: string;
  cover_start_date: string;
  cover_end_date: string | null;
  created_at: string;
  updated_at: string;
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

function formatRelationship(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getStatusClass(status: string) {
  switch (status) {
    case "completed":
    case "confirmed":
    case "active":
      return "bg-emerald-50 text-emerald-700";

    case "in_progress":
      return "bg-blue-50 text-blue-700";

    case "cancelled":
      return "bg-red-50 text-red-700";

    case "closed":
    case "lapsed":
      return "bg-slate-100 text-slate-700";

    case "arrears":
    case "overdue":
      return "bg-amber-50 text-amber-700";

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

        <ChevronRight size={18} className="text-slate-300" />
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

function CoverageBadge({
  status,
  label,
}: {
  status: string;
  label?: string;
}) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${getStatusClass(
        status
      )}`}
    >
      {label || formatStatus(status)}
    </span>
  );
}

export default function CaseDetailsPage() {
  const router = useRouter();
  const params = useParams();

  const caseId = String(params.case_id || "");

  const [summary, setSummary] = useState<CaseSummary | null>(null);

  const [members, setMembers] = useState<Member[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [dependents, setDependents] = useState<CoveredDependent[]>([]);

  const [loading, setLoading] = useState(true);
  const [coverageLoading, setCoverageLoading] = useState(false);
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
      setCoverageLoading(true);
      setError("");

      const response = await api.get<CaseSummary>(
        `/cases/${caseId}/summary`
      );

      setSummary(response.data);

      const [
        membersResponse,
        plansResponse,
        membershipsResponse,
        dependentsResponse,
      ] = await Promise.all([
        api.get<Member[]>("/members"),
        api.get<MembershipPlan[]>("/membership-plans"),
        api.get<Membership[]>("/memberships"),
        api.get<CoveredDependent[]>("/covered-dependents"),
      ]);

      setMembers(membersResponse.data);
      setPlans(plansResponse.data);
      setMemberships(membershipsResponse.data);
      setDependents(dependentsResponse.data);
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
      setCoverageLoading(false);
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

  const funeralCase = summary.case;

  const membership = funeralCase.membership_id
    ? memberships.find(
        (item) => item.id === funeralCase.membership_id
      )
    : null;

  const member = membership
    ? members.find((item) => item.id === membership.member_id)
    : null;

  const plan = membership
    ? plans.find((item) => item.id === membership.plan_id)
    : null;

  const dependent = funeralCase.covered_dependent_id
    ? dependents.find(
        (item) => item.id === funeralCase.covered_dependent_id
      )
    : null;

  const isPrivateCase = !funeralCase.membership_id;

  const isDependentCase =
    Boolean(funeralCase.membership_id) &&
    Boolean(funeralCase.covered_dependent_id);

  const membershipStatus = membership?.status || null;

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
                      {funeralCase.deceased_full_name}
                    </h1>

                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${getStatusClass(
                        funeralCase.status
                      )}`}
                    >
                      {formatStatus(funeralCase.status)}
                    </span>
                  </div>

                  <p className="mt-1 text-sm text-slate-500">
                    Case #{funeralCase.case_number}
                  </p>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={loadCase}
              className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              {coverageLoading ? (
                <Loader2
                  size={16}
                  className="animate-spin"
                />
              ) : null}

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
              value={funeralCase.deceased_full_name}
            />

            <InfoRow
              icon={<CalendarDays size={17} />}
              label="Date of Birth"
              value={formatDate(funeralCase.date_of_birth)}
            />

            <InfoRow
              icon={<CalendarDays size={17} />}
              label="Date of Death"
              value={formatDate(funeralCase.date_of_death)}
            />

            <InfoRow
              icon={<Users size={17} />}
              label="Next of Kin"
              value={funeralCase.next_of_kin_name || "—"}
            />

            <InfoRow
              icon={<Phone size={17} />}
              label="Next of Kin Phone"
              value={funeralCase.next_of_kin_phone || "—"}
            />

            <InfoRow
              icon={<MapPin size={17} />}
              label="Funeral Venue"
              value={funeralCase.funeral_venue || "—"}
            />

            <InfoRow
              icon={<CalendarDays size={17} />}
              label="Funeral Date"
              value={formatDate(funeralCase.funeral_date)}
            />

            <InfoRow
              icon={<FileText size={17} />}
              label="Case Number"
              value={funeralCase.case_number}
            />
          </div>
        </div>

        {/* COVERAGE & MEMBERSHIP */}

        <div className="mt-6 rounded-2xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
              <ShieldCheck size={20} />
            </div>

            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Coverage & Membership
              </h2>

              <p className="text-sm text-slate-500">
                Membership and funeral cover information linked to this case.
              </p>
            </div>
          </div>

          {isPrivateCase ? (
            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                    Funeral Type
                  </p>

                  <p className="mt-1 text-base font-semibold text-slate-900">
                    Private / Non-member
                  </p>

                  <p className="mt-1 text-sm text-slate-500">
                    No membership or covered dependent is linked to this case.
                  </p>
                </div>

                <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-medium text-slate-700">
                  No Cover
                </span>
              </div>
            </div>
          ) : (
            <div className="mt-6 space-y-5">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-xl border bg-slate-50 p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                    Funeral Type
                  </p>

                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {isDependentCase
                      ? "Covered Dependent"
                      : "Member"}
                  </p>
                </div>

                <div className="rounded-xl border bg-slate-50 p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                    Membership Number
                  </p>

                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {membership?.membership_number || "—"}
                  </p>
                </div>

                <div className="rounded-xl border bg-slate-50 p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                    Membership Status
                  </p>

                  <div className="mt-2">
                    {membershipStatus ? (
                      <CoverageBadge status={membershipStatus} />
                    ) : (
                      <span className="text-sm text-slate-500">
                        Membership not found
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                <InfoRow
                  icon={<UserRound size={17} />}
                  label="Member"
                  value={
                    member
                      ? `${member.first_name} ${member.last_name}`
                      : "Member not found"
                  }
                />

                <InfoRow
                  icon={<ShieldCheck size={17} />}
                  label="Membership"
                  value={
                    membership?.membership_number || "—"
                  }
                />

                <InfoRow
                  icon={<HeartHandshake size={17} />}
                  label="Plan"
                  value={plan?.name || "Plan not found"}
                />

                <InfoRow
                  icon={<CreditCard size={17} />}
                  label="Monthly Contribution"
                  value={
                    plan
                      ? `R ${formatMoney(
                          plan.monthly_contribution
                        )}`
                      : "—"
                  }
                />
              </div>

              {membership?.arrears_since ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
                  <p className="text-sm font-semibold text-amber-800">
                    Membership has arrears
                  </p>

                  <p className="mt-1 text-sm text-amber-700">
                    Arrears began on{" "}
                    {formatDate(membership.arrears_since)}.
                    Coverage is governed by the business's configured
                    arrears and lapse policy.
                  </p>
                </div>
              ) : null}

              {membership?.lapsed_at ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-5">
                  <p className="text-sm font-semibold text-red-800">
                    Membership lapsed
                  </p>

                  <p className="mt-1 text-sm text-red-700">
                    Membership was recorded as lapsed on{" "}
                    {formatDate(membership.lapsed_at)}.
                  </p>
                </div>
              ) : null}

              {isDependentCase && dependent ? (
                <div className="rounded-xl border bg-slate-50 p-5">
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">
                        Covered Dependent
                      </p>

                      <p className="mt-1 text-xs text-slate-500">
                        Person covered under the linked membership.
                      </p>
                    </div>

                    <CoverageBadge
                      status={dependent.status}
                    />
                  </div>

                  <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                    <InfoRow
                      icon={<UserRound size={17} />}
                      label="Dependent"
                      value={`${dependent.first_name} ${dependent.last_name}`}
                    />

                    <InfoRow
                      icon={<Users size={17} />}
                      label="Relationship"
                      value={formatRelationship(
                        dependent.relationship
                      )}
                    />

                    <InfoRow
                      icon={<CalendarDays size={17} />}
                      label="Cover Start"
                      value={formatDate(
                        dependent.cover_start_date
                      )}
                    />

                    <InfoRow
                      icon={<CalendarDays size={17} />}
                      label="Cover End"
                      value={formatDate(
                        dependent.cover_end_date
                      )}
                    />
                  </div>
                </div>
              ) : null}

              {!membership ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-5">
                  <p className="text-sm font-semibold text-red-800">
                    Linked membership could not be found
                  </p>

                  <p className="mt-1 text-sm text-red-700">
                    The case contains a membership reference, but the
                    membership record is not available in the current
                    business context.
                  </p>
                </div>
              ) : null}

              {isDependentCase && !dependent ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-5">
                  <p className="text-sm font-semibold text-red-800">
                    Covered dependent could not be found
                  </p>

                  <p className="mt-1 text-sm text-red-700">
                    The case contains a covered-dependent reference, but
                    the dependent record is not available in the current
                    business context.
                  </p>
                </div>
              ) : null}
            </div>
          )}
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
              router.push(
                `/cases/${caseId}/services`
              );
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
              router.push(
                `/cases/${caseId}/tasks`
              );
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
            {/* CONTACTS */}

            <button
              type="button"
              onClick={() =>
                router.push(
                  `/cases/${caseId}/contacts`
                )
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

            {/* SERVICES */}

            <button
              type="button"
              onClick={() =>
                router.push(
                  `/cases/${caseId}/services`
                )
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

            {/* FINANCIALS */}

            <button
              type="button"
              onClick={() =>
                router.push(
                  `/cases/${caseId}/financial`
                )
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

            {/* DOCUMENTS */}

            <button
              type="button"
              onClick={() =>
                router.push(
                  `/cases/${caseId}/documents`
                )
              }
              className="flex items-center justify-between rounded-xl border p-4 text-left hover:bg-slate-50"
            >
              <div className="flex items-center gap-3">
                <FileText
                  size={20}
                  className="text-slate-500"
                />

                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Documents
                  </p>

                  <p className="text-xs text-slate-500">
                    Manage case documents
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
