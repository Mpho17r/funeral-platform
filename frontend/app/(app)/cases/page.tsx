"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Eye,
  FilePlus2,
  Search,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";

import axios from "axios";
import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { useBranches } from "@/lib/branches";
import {
  ALL_BRANCHES,
  BranchBadge,
  BranchFilter,
  BranchSelect,
  MoveButton,
  TransferDialog,
  matchesBranch,
} from "@/components/BranchControls";

type FuneralCase = {
  id: string;
  business_id: string;
  case_number: string;
  deceased_full_name: string;
  date_of_birth: string | null;
  date_of_death: string | null;
  next_of_kin_name: string | null;
  next_of_kin_phone: string | null;
  funeral_date: string | null;
  funeral_venue: string | null;
  status: string;
  notes: string | null;
  membership_id: string | null;
  covered_dependent_id: string | null;
  branch_id: string | null;
  created_at: string;
  updated_at: string;
};

type Member = {
  id: string;
  first_name: string;
  last_name: string;
};

type MembershipPlan = {
  id: string;
  name: string;
  monthly_contribution: string | number;
};

type Membership = {
  id: string;
  member_id: string;
  membership_number: string;
  plan_id: string;
  status: string;
};

type CoveredDependent = {
  id: string;
  membership_id: string;
  first_name: string;
  last_name: string;
  relationship: string;
  status: string;
  cover_start_date: string;
  cover_end_date: string | null;
};

type FuneralType = "private" | "member" | "dependent";

const STATUS_OPTIONS = [
  "all",
  "open",
  "confirmed",
  "in_progress",
  "completed",
  "closed",
  "cancelled",
];

const FUNERAL_TYPE_OPTIONS: {
  value: FuneralType;
  label: string;
  description: string;
}[] = [
  {
    value: "private",
    label: "Private Funeral",
    description: "Create a case without linking it to membership cover.",
  },
  {
    value: "member",
    label: "Member Funeral",
    description: "Link the deceased directly to an existing membership.",
  },
  {
    value: "dependent",
    label: "Dependent Funeral",
    description: "Link the case to a covered dependent under a membership.",
  },
];

const INITIAL_FORM = {
  case_number: "",
  deceased_full_name: "",
  date_of_birth: "",
  date_of_death: "",
  next_of_kin_name: "",
  next_of_kin_phone: "",
  funeral_date: "",
  funeral_venue: "",
  status: "open",
  notes: "",
  membership_id: "",
  covered_dependent_id: "",
};

function getApiErrorStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  const detail = axios.isAxiosError<{ detail?: unknown }>(error)
    ? error.response?.data?.detail
    : undefined;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (typeof item === "string") {
          return item;
        }

        if (
          item !== null &&
          typeof item === "object" &&
          "msg" in item &&
          typeof item.msg === "string"
        ) {
          return item.msg;
        }

        return "Invalid request.";
      })
      .join(" ");
  }

  return error instanceof Error ? error.message : fallback;
}

export default function CasesPage() {
  const router = useRouter();

  const [cases, setCases] = useState<FuneralCase[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [dependents, setDependents] = useState<CoveredDependent[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const branchData = useBranches();
  const [branchFilter, setBranchFilter] = useState(ALL_BRANCHES);
  const [newCaseBranch, setNewCaseBranch] = useState("");
  const [moving, setMoving] = useState<FuneralCase | null>(null);
  const [notice, setNotice] = useState("");

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const [funeralType, setFuneralType] =
    useState<FuneralType>("private");

  const [form, setForm] = useState(INITIAL_FORM);

  const loadCases = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await api.get<FuneralCase[]>("/cases");
      setCases(response.data);
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        router.push("/login");
        return;
      }

      setError(getApiErrorMessage(err, "Unable to load funeral cases."));
    } finally {
      setLoading(false);
    }
  }, [router]);

  const loadMembershipData = useCallback(async () => {
    try {
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
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        router.push("/login");
        return;
      }

      setCreateError(
        getApiErrorMessage(err, "Unable to load membership information.")
      );
    }
  }, [router]);

  useEffect(() => {
    async function initializeCasesPage() {
      if (!isAuthenticated()) {
        router.push("/login");
        return;
      }

      await Promise.all([
        loadCases(),
        loadMembershipData(),
      ]);
    }

    void initializeCasesPage();
  }, [router, loadCases, loadMembershipData]);

  function updateForm(
    field: keyof typeof INITIAL_FORM,
    value: string
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleFuneralTypeChange(type: FuneralType) {
    setFuneralType(type);

    if (type === "private") {
      setForm((current) => ({
        ...current,
        membership_id: "",
        covered_dependent_id: "",
      }));
    } else if (type === "member") {
      setForm((current) => ({
        ...current,
        covered_dependent_id: "",
      }));
    }
  }

  function resetForm() {
    setFuneralType("private");
    setForm(INITIAL_FORM);
    setCreateError("");
    setNewCaseBranch("");
  }

  async function handleCreateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setCreating(true);
    setCreateError("");

    try {
      if (
        funeralType !== "private" &&
        !form.membership_id
      ) {
        setCreateError("Please select a membership.");
        setCreating(false);
        return;
      }

      if (
        funeralType === "dependent" &&
        !form.covered_dependent_id
      ) {
        setCreateError(
          "Please select the covered dependent."
        );
        setCreating(false);
        return;
      }

      const payload = {
        case_number: form.case_number.trim(),
        deceased_full_name:
          form.deceased_full_name.trim(),
        date_of_birth: form.date_of_birth || null,
        date_of_death: form.date_of_death || null,
        next_of_kin_name:
          form.next_of_kin_name.trim() || null,
        next_of_kin_phone:
          form.next_of_kin_phone.trim() || null,
        funeral_date: form.funeral_date || null,
        funeral_venue:
          form.funeral_venue.trim() || null,
        status: form.status,
        notes: form.notes.trim() || null,
        membership_id:
          funeralType === "private"
            ? null
            : form.membership_id,
        covered_dependent_id:
          funeralType === "dependent"
            ? form.covered_dependent_id
            : null,
        // Left empty, the server uses the creator's own branch.
        ...(newCaseBranch ? { branch_id: newCaseBranch } : {}),
      };

      const response = await api.post<FuneralCase>(
        "/cases",
        payload
      );

      setCases((current) => [
        response.data,
        ...current,
      ]);

      resetForm();
      setShowCreateForm(false);
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        router.push("/login");
        return;
      }

      setCreateError(
        getApiErrorMessage(err, "Unable to create funeral case.")
      );
    } finally {
      setCreating(false);
    }
  }

  const selectedMembership = useMemo(() => {
    return memberships.find(
      (membership) =>
        membership.id === form.membership_id
    );
  }, [memberships, form.membership_id]);

  const selectedPlan = useMemo(() => {
    if (!selectedMembership) {
      return undefined;
    }

    return plans.find(
      (plan) => plan.id === selectedMembership.plan_id
    );
  }, [plans, selectedMembership]);

  const selectedMember = useMemo(() => {
    if (!selectedMembership) {
      return undefined;
    }

    return members.find(
      (member) =>
        member.id === selectedMembership.member_id
    );
  }, [members, selectedMembership]);

  const availableDependents = useMemo(() => {
    if (!form.membership_id) {
      return [];
    }

    return dependents.filter(
      (dependent) =>
        dependent.membership_id === form.membership_id
    );
  }, [dependents, form.membership_id]);

  const selectedDependent = useMemo(() => {
    return dependents.find(
      (dependent) =>
        dependent.id === form.covered_dependent_id
    );
  }, [dependents, form.covered_dependent_id]);

  const membershipWarning = useMemo(() => {
    if (!selectedMembership) {
      return "";
    }

    if (selectedMembership.status === "lapsed") {
      return "This membership is lapsed. The case can still be recorded, but coverage is not currently active.";
    }

    if (selectedMembership.status === "cancelled") {
      return "This membership is cancelled. The case can still be recorded, but coverage is not currently active.";
    }

    if (selectedMembership.status === "arrears") {
      return "This membership is in arrears. Coverage will be determined by the business cover policy.";
    }

    return "";
  }, [selectedMembership]);

  const dependentWarning = useMemo(() => {
    if (!selectedDependent) {
      return "";
    }

    if (selectedDependent.status !== "active") {
      return "This dependent is not marked as active. The case can still be recorded, but dependent coverage may not apply.";
    }

    const deathDate = form.date_of_death
      ? new Date(form.date_of_death)
      : null;

    if (deathDate) {
      const start = new Date(
        selectedDependent.cover_start_date
      );

      const end = selectedDependent.cover_end_date
        ? new Date(selectedDependent.cover_end_date)
        : null;

      if (deathDate < start) {
        return "The date of death is before this dependent's cover start date.";
      }

      if (end && deathDate > end) {
        return "The date of death is after this dependent's cover end date.";
      }
    }

    return "";
  }, [selectedDependent, form.date_of_death]);

  const filteredCases = useMemo(() => {
    const query = search.trim().toLowerCase();

    return cases.filter((item) => {
      const matchesSearch =
        !query ||
        item.case_number
          .toLowerCase()
          .includes(query) ||
        item.deceased_full_name
          .toLowerCase()
          .includes(query) ||
        item.next_of_kin_name
          ?.toLowerCase()
          .includes(query);

      const matchesStatus =
        statusFilter === "all" ||
        item.status === statusFilter;

      return (
        matchesSearch &&
        matchesStatus &&
        matchesBranch(branchFilter, item.branch_id)
      );
    });
  }, [cases, search, statusFilter, branchFilter]);

  const statistics = {
    total: cases.length,
    open: cases.filter(
      (item) => item.status === "open"
    ).length,
    inProgress: cases.filter(
      (item) => item.status === "in_progress"
    ).length,
    completed: cases.filter(
      (item) => item.status === "completed"
    ).length,
  };

  return (
    <main className="min-h-full bg-[var(--fos-page)]">
      <section className="px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          {/* Header */}
          <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-emerald-700">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
                Operations
              </div>

              <h1 className="font-serif text-3xl tracking-tight text-[var(--fos-text)] sm:text-4xl">
                Funeral cases
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--fos-text-muted)]">
                Manage active funeral arrangements, case details,
                family information and service progress from one place.
              </p>
            </div>

            <button
              onClick={() => {
                setCreateError("");
                setShowCreateForm(true);
              }}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2"
            >
              <FilePlus2 size={17} />
              New case
            </button>
          </div>

          {/* Statistics */}
          <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={FilePlus2}
              label="Total cases"
              value={statistics.total}
              detail="All recorded cases"
            />

            <StatCard
              icon={Clock3}
              label="Open"
              value={statistics.open}
              detail="Awaiting progress"
            />

            <StatCard
              icon={CalendarDays}
              label="In progress"
              value={statistics.inProgress}
              detail="Currently being handled"
            />

            <StatCard
              icon={CheckCircle2}
              label="Completed"
              value={statistics.completed}
              detail="Completed arrangements"
            />
          </div>

          {/* Search and filters */}
          <div className="mt-6 rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] p-3 shadow-[0_8px_30px_rgba(15,23,42,0.04)] sm:p-4">
            <div className="flex flex-col gap-3 lg:flex-row">
              <div className="relative flex-1">
                <Search
                  size={18}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--fos-text-muted)]"
                />

                <input
                  value={search}
                  onChange={(event) =>
                    setSearch(event.target.value)
                  }
                  placeholder="Search case number, deceased name or next of kin..."
                  className="h-11 w-full rounded-xl border border-[var(--fos-border)] bg-[var(--fos-page)]/70 py-2.5 pl-10 pr-4 text-sm text-[var(--fos-text)] outline-none transition placeholder:text-[var(--fos-text-muted)] focus:border-emerald-500 focus:bg-[var(--fos-surface)] focus:ring-2 focus:ring-emerald-100"
                />
              </div>

              <select
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value)
                }
                className="h-11 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-page)]/70 px-4 text-sm text-[var(--fos-text-secondary)] outline-none transition focus:border-emerald-500 focus:bg-[var(--fos-surface)] focus:ring-2 focus:ring-emerald-100"
              >
                {STATUS_OPTIONS.map((status) => (
                  <option
                    key={status}
                    value={status}
                  >
                    {status === "all"
                      ? "All statuses"
                      : formatStatus(status)}
                  </option>
                ))}
              </select>

              {branchData.multiple && (
                <BranchFilter
                  branches={branchData.branches}
                  value={branchFilter}
                  onChange={setBranchFilter}
                />
              )}
            </div>
          </div>

          {notice && (
            <div
              role="status"
              className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
            >
              {notice}
            </div>
          )}

          {error && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Cases */}
          <div className="mt-6 overflow-hidden rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
            <div className="flex flex-col gap-1 border-b border-[var(--fos-border)] px-4 py-4 sm:px-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-sm font-semibold text-[var(--fos-text)]">
                    Cases
                  </h2>

                  <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                    {filteredCases.length} case
                    {filteredCases.length === 1
                      ? ""
                      : "s"} shown
                  </p>
                </div>

                {(search || statusFilter !== "all") && (
                  <button
                    onClick={() => {
                      setSearch("");
                      setStatusFilter("all");
                    }}
                    className="text-xs font-medium text-emerald-700 hover:text-emerald-800"
                  >
                    Clear filters
                  </button>
                )}
              </div>
            </div>

            {loading ? (
              <div className="px-6 py-20 text-center">
                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--fos-border)] border-t-emerald-600" />
                <p className="mt-4 text-sm text-[var(--fos-text-muted)]">
                  Loading cases...
                </p>
              </div>
            ) : filteredCases.length === 0 ? (
              <EmptyCases
                hasFilters={Boolean(
                  search || statusFilter !== "all"
                )}
                onCreate={() => {
                  setCreateError("");
                  setShowCreateForm(true);
                }}
              />
            ) : (
              <>
                {/* Desktop */}
                <div className="hidden overflow-x-auto lg:block">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-[var(--fos-border)] bg-[var(--fos-page)]/70 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fos-text-muted)]">
                        <th className="px-6 py-3.5">
                          Case
                        </th>
                        <th className="px-6 py-3.5">
                          Deceased
                        </th>
                        <th className="px-6 py-3.5">
                          Next of kin
                        </th>
                        <th className="px-6 py-3.5">
                          Funeral date
                        </th>
                        <th className="px-6 py-3.5">
                          Status
                        </th>
                        <th className="px-6 py-3.5 text-right">
                          Action
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {filteredCases.map((item) => (
                        <tr
                          key={item.id}
                          onClick={() =>
                            router.push(
                              `/cases/${item.id}`
                            )
                          }
                          className="cursor-pointer border-b border-[var(--fos-border)] last:border-0 transition hover:bg-emerald-50/30"
                        >
                          <td className="px-6 py-4">
                            <p className="text-sm font-semibold text-[var(--fos-text)]">
                              {item.case_number}
                            </p>

                            <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                              Created{" "}
                              {formatDate(item.created_at)}
                            </p>

                            {branchData.multiple && (
                              <div className="mt-1.5">
                                <BranchBadge
                                  branchId={item.branch_id}
                                  byId={branchData.byId}
                                />
                              </div>
                            )}
                          </td>

                          <td className="px-6 py-4">
                            <p className="text-sm font-medium text-[var(--fos-text)]">
                              {item.deceased_full_name}
                            </p>

                            {item.funeral_venue && (
                              <p className="mt-1 max-w-[220px] truncate text-xs text-[var(--fos-text-muted)]">
                                {item.funeral_venue}
                              </p>
                            )}
                          </td>

                          <td className="px-6 py-4">
                            <p className="text-sm text-[var(--fos-text-secondary)]">
                              {item.next_of_kin_name ||
                                "—"}
                            </p>

                            {item.next_of_kin_phone && (
                              <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                                {item.next_of_kin_phone}
                              </p>
                            )}
                          </td>

                          <td className="px-6 py-4 text-sm text-[var(--fos-text-secondary)]">
                            {item.funeral_date
                              ? formatDate(
                                  item.funeral_date
                                )
                              : "Not scheduled"}
                          </td>

                          <td className="px-6 py-4">
                            <StatusBadge
                              status={item.status}
                            />
                          </td>

                          <td className="px-6 py-4 text-right">
                            <div className="flex flex-wrap justify-end gap-2">
                              <button
                                onClick={(event) => {
                                  event.stopPropagation();
                                  router.push(
                                    `/cases/${item.id}`
                                  );
                                }}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--fos-border)] px-3 py-2 text-xs font-semibold text-[var(--fos-text-secondary)] transition hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-800"
                              >
                                <Eye size={14} />
                                View
                              </button>

                              {branchData.multiple && (
                                <span
                                  onClick={(event) =>
                                    event.stopPropagation()
                                  }
                                >
                                  <MoveButton
                                    onClick={() =>
                                      setMoving(item)
                                    }
                                  />
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile / tablet */}
                <div className="divide-y divide-slate-100 lg:hidden">
                  {filteredCases.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() =>
                        router.push(
                          `/cases/${item.id}`
                        )
                      }
                      className="block w-full px-4 py-4 text-left transition hover:bg-emerald-50/30 sm:px-6"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                              {item.case_number}
                            </span>

                            <StatusBadge
                              status={item.status}
                            />
                          </div>

                          <h3 className="mt-2 truncate text-sm font-semibold text-[var(--fos-text)]">
                            {item.deceased_full_name}
                          </h3>

                          {branchData.multiple && (
                            <div className="mt-1.5">
                              <BranchBadge
                                branchId={item.branch_id}
                                byId={branchData.byId}
                              />
                            </div>
                          )}
                        </div>

                        <ChevronRight
                          size={18}
                          className="mt-1 shrink-0 text-[var(--fos-text-muted)]"
                        />
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-3">
                        <MobileCaseDetail
                          icon={CalendarDays}
                          label="Funeral"
                          value={
                            item.funeral_date
                              ? formatDate(
                                  item.funeral_date
                                )
                              : "Not scheduled"
                          }
                        />

                        <MobileCaseDetail
                          icon={UserRound}
                          label="Next of kin"
                          value={
                            item.next_of_kin_name ||
                            "Not provided"
                          }
                        />
                      </div>

                      {item.funeral_venue && (
                        <p className="mt-3 truncate text-xs text-[var(--fos-text-muted)]">
                          {item.funeral_venue}
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      {/* Create case modal */}
      {showCreateForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-3 backdrop-blur-[2px] sm:p-6">
          <div className="flex max-h-[94vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-2xl">
            <div className="flex shrink-0 items-center justify-between border-b border-[var(--fos-border)] px-5 py-4 sm:px-6">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">
                  <FilePlus2 size={14} />
                  New case
                </div>

                <h2 className="mt-1 font-serif text-2xl text-[var(--fos-text)]">
                  Create funeral case
                </h2>

                <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                  Register a new funeral arrangement.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setShowCreateForm(false)
                }
                className="rounded-xl p-2 text-[var(--fos-text-muted)] transition hover:bg-[var(--fos-surface-muted)] hover:text-[var(--fos-text-secondary)] focus:outline-none focus:ring-2 focus:ring-emerald-100"
                aria-label="Close"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleCreateCase}
              className="min-h-0 overflow-y-auto"
            >
              <div className="space-y-7 p-5 sm:p-6">
                {createError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {createError}
                  </div>
                )}

                {/* Funeral type */}
                <section>
                  <SectionHeading
                    title="Funeral type"
                    description="Choose how this case is connected to the business."
                  />

                  <div className="grid gap-3 md:grid-cols-3">
                    {FUNERAL_TYPE_OPTIONS.map(
                      (option) => {
                        const selected =
                          funeralType === option.value;

                        return (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() =>
                              handleFuneralTypeChange(
                                option.value
                              )
                            }
                            className={`rounded-xl border p-4 text-left transition ${
                              selected
                                ? "border-emerald-500 bg-emerald-50/70 ring-2 ring-emerald-100"
                                : "border-[var(--fos-border)] bg-[var(--fos-surface)] hover:border-[var(--fos-border)] hover:bg-[var(--fos-page)]"
                            }`}
                          >
                            <div className="flex items-start gap-3">
                              <div
                                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                                  selected
                                    ? "border-emerald-600"
                                    : "border-[var(--fos-border)]"
                                }`}
                              >
                                {selected && (
                                  <div className="h-2.5 w-2.5 rounded-full bg-emerald-600" />
                                )}
                              </div>

                              <div>
                                <p className="text-sm font-semibold text-[var(--fos-text)]">
                                  {option.label}
                                </p>

                                <p className="mt-1 text-xs leading-5 text-[var(--fos-text-muted)]">
                                  {option.description}
                                </p>
                              </div>
                            </div>
                          </button>
                        );
                      }
                    )}
                  </div>
                </section>

                {/* Membership */}
                {funeralType !== "private" && (
                  <section className="rounded-2xl border border-emerald-100 bg-emerald-50/45 p-4 sm:p-5">
                    <div className="mb-5 flex items-start gap-3">
                      <div className="rounded-xl bg-[var(--fos-surface)] p-2.5 text-emerald-700 shadow-sm">
                        <Users size={18} />
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold text-[var(--fos-text)]">
                          Membership & cover
                        </h3>

                        <p className="mt-1 text-xs leading-5 text-[var(--fos-text-muted)]">
                          Link this case to an existing membership.
                        </p>
                      </div>
                    </div>

                    <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                      Membership
                    </label>

                    <select
                      value={form.membership_id}
                      onChange={(event) => {
                        updateForm(
                          "membership_id",
                          event.target.value
                        );
                        updateForm(
                          "covered_dependent_id",
                          ""
                        );
                      }}
                      required
                      className="w-full rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    >
                      <option value="">
                        Select membership
                      </option>

                      {memberships.map(
                        (membership) => {
                          const member = members.find(
                            (item) =>
                              item.id ===
                              membership.member_id
                          );

                          return (
                            <option
                              key={membership.id}
                              value={membership.id}
                            >
                              {member
                                ? `${member.first_name} ${member.last_name}`
                                : "Unknown member"}{" "}
                              —{" "}
                              {membership.membership_number}
                            </option>
                          );
                        }
                      )}
                    </select>

                    {selectedMembership && (
                      <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        <InfoCard
                          label="Member"
                          value={
                            selectedMember
                              ? `${selectedMember.first_name} ${selectedMember.last_name}`
                              : "Unknown"
                          }
                        />

                        <InfoCard
                          label="Plan"
                          value={
                            selectedPlan?.name ||
                            "Unknown"
                          }
                        />

                        <InfoCard
                          label="Monthly contribution"
                          value={
                            selectedPlan
                              ? formatCurrency(
                                  selectedPlan.monthly_contribution
                                )
                              : "—"
                          }
                        />
                      </div>
                    )}

                    {membershipWarning && (
                      <Notice
                        title="Coverage notice"
                        message={membershipWarning}
                      />
                    )}

                    {funeralType === "dependent" && (
                      <div className="mt-5">
                        <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                          Covered dependent
                        </label>

                        <select
                          value={
                            form.covered_dependent_id
                          }
                          onChange={(event) =>
                            updateForm(
                              "covered_dependent_id",
                              event.target.value
                            )
                          }
                          required
                          disabled={
                            !form.membership_id
                          }
                          className="w-full rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm outline-none transition disabled:cursor-not-allowed disabled:bg-[var(--fos-surface-muted)] focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                        >
                          <option value="">
                            {!form.membership_id
                              ? "Select membership first"
                              : availableDependents.length ===
                                  0
                                ? "No covered dependents found"
                                : "Select covered dependent"}
                          </option>

                          {availableDependents.map(
                            (dependent) => (
                              <option
                                key={dependent.id}
                                value={dependent.id}
                              >
                                {dependent.first_name}{" "}
                                {dependent.last_name} —{" "}
                                {formatRelationship(
                                  dependent.relationship
                                )}
                              </option>
                            )
                          )}
                        </select>

                        {dependentWarning && (
                          <Notice
                            title="Dependent coverage notice"
                            message={dependentWarning}
                          />
                        )}
                      </div>
                    )}
                  </section>
                )}

                {/* Case information */}
                <section>
                  <SectionHeading
                    title="Case information"
                    description="Basic information about the deceased and arrangement."
                  />

                  <div className="grid gap-4 md:grid-cols-2">
                    <FormField
                      label="Case number"
                      required
                      value={form.case_number}
                      onChange={(value) =>
                        updateForm(
                          "case_number",
                          value
                        )
                      }
                      placeholder="CASE-00125"
                    />

                    <FormField
                      label="Status"
                      type="select"
                      value={form.status}
                      onChange={(value) =>
                        updateForm(
                          "status",
                          value
                        )
                      }
                      options={STATUS_OPTIONS.filter(
                        (item) => item !== "all"
                      )}
                    />

                    <FormField
                      label="Deceased full name"
                      required
                      value={
                        form.deceased_full_name
                      }
                      onChange={(value) =>
                        updateForm(
                          "deceased_full_name",
                          value
                        )
                      }
                      placeholder="Full name"
                    />

                    <FormField
                      label="Date of birth"
                      type="date"
                      value={form.date_of_birth}
                      onChange={(value) =>
                        updateForm(
                          "date_of_birth",
                          value
                        )
                      }
                    />

                    <FormField
                      label="Date of death"
                      type="date"
                      value={form.date_of_death}
                      onChange={(value) =>
                        updateForm(
                          "date_of_death",
                          value
                        )
                      }
                    />

                    <FormField
                      label="Funeral date"
                      type="date"
                      value={form.funeral_date}
                      onChange={(value) =>
                        updateForm(
                          "funeral_date",
                          value
                        )
                      }
                    />
                  </div>
                </section>

                {/* Next of kin */}
                <section>
                  <SectionHeading
                    title="Next of kin"
                    description="Primary family contact for the arrangement."
                  />

                  <div className="grid gap-4 md:grid-cols-2">
                    <FormField
                      label="Next of kin name"
                      value={
                        form.next_of_kin_name
                      }
                      onChange={(value) =>
                        updateForm(
                          "next_of_kin_name",
                          value
                        )
                      }
                      placeholder="Full name"
                    />

                    <FormField
                      label="Next of kin phone"
                      value={
                        form.next_of_kin_phone
                      }
                      onChange={(value) =>
                        updateForm(
                          "next_of_kin_phone",
                          value
                        )
                      }
                      placeholder="+27..."
                    />
                  </div>
                </section>

                {/* Funeral details */}
                <section>
                  <SectionHeading
                    title="Funeral details"
                    description="Location and other arrangement information."
                  />

                  <FormField
                    label="Funeral venue"
                    value={form.funeral_venue}
                    onChange={(value) =>
                      updateForm(
                        "funeral_venue",
                        value
                      )
                    }
                    placeholder="Funeral venue"
                  />
                </section>

                {branchData.multiple && (
                  <BranchSelect
                    branches={branchData.branches}
                    value={newCaseBranch}
                    onChange={setNewCaseBranch}
                  />
                )}

                {/* Notes */}
                <section>
                  <SectionHeading
                    title="Notes"
                    description="Add any additional information relevant to this case."
                  />

                  <textarea
                    value={form.notes}
                    onChange={(event) =>
                      updateForm(
                        "notes",
                        event.target.value
                      )
                    }
                    rows={4}
                    placeholder="Additional information about the case..."
                    className="w-full resize-y rounded-xl border border-[var(--fos-border)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none transition placeholder:text-[var(--fos-text-muted)] focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                  />
                </section>
              </div>

              <div className="sticky bottom-0 flex flex-col-reverse gap-3 border-t border-[var(--fos-border)] bg-[var(--fos-surface)] px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
                <button
                  type="button"
                  onClick={() =>
                    setShowCreateForm(false)
                  }
                  className="rounded-xl border border-[var(--fos-border)] px-5 py-2.5 text-sm font-semibold text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)]"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {creating
                    ? "Creating..."
                    : "Create case"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {moving && (
        <TransferDialog
          path={`/cases/${moving.id}/transfer`}
          subject={`case ${moving.case_number}`}
          currentBranchId={moving.branch_id}
          branches={branchData.branches}
          onClose={() => setMoving(null)}
          onMoved={(message) => {
            setMoving(null);
            setNotice(message);
            void loadCases();
          }}
        />
      )}
    </main>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof FilePlus2;
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] p-4 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.1em] text-[var(--fos-text-muted)]">
            {label}
          </p>

          <p className="mt-2 text-2xl font-semibold tracking-tight text-[var(--fos-text)]">
            {value}
          </p>

          <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
            {detail}
          </p>
        </div>

        <div className="rounded-xl bg-emerald-50 p-2.5 text-emerald-700">
          <Icon size={17} />
        </div>
      </div>
    </div>
  );
}

function EmptyCases({
  hasFilters,
  onCreate,
}: {
  hasFilters: boolean;
  onCreate: () => void;
}) {
  return (
    <div className="px-6 py-16 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
        <FilePlus2 size={20} />
      </div>

      <h3 className="mt-4 text-sm font-semibold text-[var(--fos-text)]">
        {hasFilters
          ? "No matching cases"
          : "No cases yet"}
      </h3>

      <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-[var(--fos-text-muted)]">
        {hasFilters
          ? "Try changing your search or status filter."
          : "Create your first funeral case to begin managing the arrangement."}
      </p>

      {!hasFilters && (
        <button
          onClick={onCreate}
          className="mt-5 inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800"
        >
          <FilePlus2 size={16} />
          New case
        </button>
      )}
    </div>
  );
}

function MobileCaseDetail({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof CalendarDays;
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
        <Icon size={12} />
        {label}
      </div>

      <p className="mt-1 truncate text-xs font-medium text-[var(--fos-text-secondary)]">
        {value}
      </p>
    </div>
  );
}

function InfoCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-[var(--fos-text)]">
        {value}
      </p>
    </div>
  );
}

function Notice({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 leading-5">{message}</p>
    </div>
  );
}

function SectionHeading({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mb-4">
      <h3 className="text-sm font-semibold text-[var(--fos-text)]">
        {title}
      </h3>

      <p className="mt-1 text-xs leading-5 text-[var(--fos-text-muted)]">
        {description}
      </p>
    </div>
  );
}

function FormField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  required = false,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: "text" | "date" | "select";
  required?: boolean;
  options?: string[];
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
        {label}

        {required && (
          <span className="ml-1 text-red-500">
            *
          </span>
        )}
      </label>

      {type === "select" ? (
        <select
          value={value}
          onChange={(event) =>
            onChange(event.target.value)
          }
          required={required}
          className="w-full rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        >
          {options?.map((option) => (
            <option key={option} value={option}>
              {formatStatus(option)}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={type}
          value={value}
          onChange={(event) =>
            onChange(event.target.value)
          }
          placeholder={placeholder}
          required={required}
          className="w-full rounded-xl border border-[var(--fos-border)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none transition placeholder:text-[var(--fos-text-muted)] focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />
      )}
    </div>
  );
}

function StatusBadge({
  status,
}: {
  status: string;
}) {
  const styles: Record<string, string> = {
    open: "bg-sky-50 text-sky-700 ring-sky-100",
    confirmed:
      "bg-indigo-50 text-indigo-700 ring-indigo-100",
    in_progress:
      "bg-amber-50 text-amber-700 ring-amber-100",
    completed:
      "bg-emerald-50 text-emerald-700 ring-emerald-100",
    closed:
      "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] ring-slate-200",
    cancelled:
      "bg-red-50 text-red-700 ring-red-100",
  };

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${
        styles[status] ||
        "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] ring-slate-200"
      }`}
    >
      {formatStatus(status)}
    </span>
  );
}

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase()
    );
}

function formatRelationship(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase()
    );
}

function formatDate(value: string | null) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatCurrency(
  value: string | number
) {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "ZAR",
    minimumFractionDigits: 2,
  }).format(Number(value));
}
