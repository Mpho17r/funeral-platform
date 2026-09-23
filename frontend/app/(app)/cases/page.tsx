"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  Eye,
  FilePlus2,
  Search,
  Users,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

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
  created_at: string;
  updated_at: string;
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
  monthly_contribution: string | number;
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
    label: "Private / Non-member",
    description: "Funeral is not linked to a membership.",
  },
  {
    value: "member",
    label: "Member",
    description: "Funeral is for the principal member.",
  },
  {
    value: "dependent",
    label: "Covered Dependent",
    description: "Funeral is for someone covered under a membership.",
  },
];

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

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const [funeralType, setFuneralType] =
    useState<FuneralType>("private");

  const [form, setForm] = useState({
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
  });

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    loadCases();
    loadMembershipData();
  }, [router]);

  async function loadCases() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<FuneralCase[]>("/cases");
      setCases(response.data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setError(
        err.response?.data?.detail ||
          "Unable to load funeral cases."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadMembershipData() {
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
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setCreateError(
        err.response?.data?.detail ||
          "Unable to load membership information."
      );
    }
  }

  function updateForm(
    field: keyof typeof form,
    value: string
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleFuneralTypeChange(type: FuneralType) {
    setFuneralType(type);

    setForm((current) => ({
      ...current,
      membership_id:
        type === "private" ? "" : current.membership_id,
      covered_dependent_id: "",
    }));
  }

  function resetForm() {
    setForm({
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
    });

    setFuneralType("private");
  }

  async function handleCreateCase(
    event: FormEvent<HTMLFormElement>
  ) {
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
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setCreateError(
        err.response?.data?.detail ||
          "Unable to create funeral case."
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

      return matchesSearch && matchesStatus;
    });
  }, [cases, search, statusFilter]);

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
    <main className="min-h-screen bg-slate-100">
      <div className="flex min-h-screen">
        <div className="min-w-0 flex-1">
          <header className="border-b bg-white">
            <div className="flex min-h-20 items-center justify-between gap-4 px-6 md:px-8">
              <div>
                <h2 className="text-xl font-bold text-slate-900">
                  Funeral Cases
                </h2>
                <p className="text-sm text-slate-500">
                  Manage and track all funeral cases
                </p>
              </div>

              <button
                onClick={() => {
                  setCreateError("");
                  setShowCreateForm(true);
                }}
                className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                <FilePlus2 size={17} />
                <span className="hidden sm:inline">
                  New Case
                </span>
              </button>
            </div>
          </header>

          <section className="p-6 md:p-8">
            <div className="mx-auto max-w-7xl">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  title="Total Cases"
                  value={statistics.total}
                />
                <StatCard
                  title="Open"
                  value={statistics.open}
                />
                <StatCard
                  title="In Progress"
                  value={statistics.inProgress}
                />
                <StatCard
                  title="Completed"
                  value={statistics.completed}
                />
              </div>

              <div className="mt-6 rounded-2xl border bg-white p-4 shadow-sm">
                <div className="flex flex-col gap-4 md:flex-row">
                  <div className="relative flex-1">
                    <Search
                      size={18}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />

                    <input
                      value={search}
                      onChange={(event) =>
                        setSearch(event.target.value)
                      }
                      placeholder="Search by case number, deceased name or next of kin..."
                      className="w-full rounded-lg border border-slate-300 py-3 pl-10 pr-4 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                    />
                  </div>

                  <select
                    value={statusFilter}
                    onChange={(event) =>
                      setStatusFilter(event.target.value)
                    }
                    className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-slate-900"
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
                </div>
              </div>

              {error && (
                <div className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div className="mt-6 overflow-hidden rounded-2xl border bg-white shadow-sm">
                <div className="border-b px-6 py-5">
                  <h3 className="font-semibold text-slate-900">
                    Cases
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    {filteredCases.length} case
                    {filteredCases.length === 1
                      ? ""
                      : "s"} shown
                  </p>
                </div>

                {loading ? (
                  <div className="px-6 py-16 text-center text-sm text-slate-500">
                    Loading cases...
                  </div>
                ) : filteredCases.length === 0 ? (
                  <div className="px-6 py-16 text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                      <FilePlus2
                        size={20}
                        className="text-slate-500"
                      />
                    </div>

                    <h4 className="mt-4 font-semibold text-slate-900">
                      No cases found
                    </h4>

                    <p className="mt-1 text-sm text-slate-500">
                      Create a new case or change your search.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[900px]">
                      <thead>
                        <tr className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                          <th className="px-6 py-4 font-medium">
                            Case
                          </th>
                          <th className="px-6 py-4 font-medium">
                            Deceased
                          </th>
                          <th className="px-6 py-4 font-medium">
                            Next of Kin
                          </th>
                          <th className="px-6 py-4 font-medium">
                            Funeral Date
                          </th>
                          <th className="px-6 py-4 font-medium">
                            Status
                          </th>
                          <th className="px-6 py-4 font-medium">
                            Action
                          </th>
                        </tr>
                      </thead>

                      <tbody>
                        {filteredCases.map((item) => (
                          <tr
                            key={item.id}
                            className="border-b last:border-0 hover:bg-slate-50"
                          >
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-900">
                                {item.case_number}
                              </p>

                              <p className="mt-1 text-xs text-slate-400">
                                {formatDate(
                                  item.created_at
                                )}
                              </p>
                            </td>

                            <td className="px-6 py-4">
                              <p className="text-sm font-medium text-slate-900">
                                {item.deceased_full_name}
                              </p>

                              {item.funeral_venue && (
                                <p className="mt-1 text-xs text-slate-500">
                                  {item.funeral_venue}
                                </p>
                              )}
                            </td>

                            <td className="px-6 py-4">
                              <p className="text-sm text-slate-700">
                                {item.next_of_kin_name ||
                                  "—"}
                              </p>

                              {item.next_of_kin_phone && (
                                <p className="mt-1 text-xs text-slate-400">
                                  {item.next_of_kin_phone}
                                </p>
                              )}
                            </td>

                            <td className="px-6 py-4 text-sm text-slate-600">
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

                            <td className="px-6 py-4">
                              <button
                                onClick={() =>
                                  router.push(
                                    `/cases/${item.id}`
                                  )
                                }
                                className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                              >
                                <Eye size={15} />
                                View
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>

      {showCreateForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between border-b bg-white px-6 py-5">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  Create New Case
                </h3>

                <p className="mt-1 text-xs text-slate-500">
                  Register a new funeral case
                </p>
              </div>

              <button
                onClick={() =>
                  setShowCreateForm(false)
                }
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleCreateCase}
              className="space-y-6 p-6"
            >
              {createError && (
                <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
                  {createError}
                </div>
              )}

              {/* Funeral type */}
              <div>
                <h4 className="mb-4 font-semibold text-slate-900">
                  Funeral Type
                </h4>

                <div className="grid gap-3 md:grid-cols-3">
                  {FUNERAL_TYPE_OPTIONS.map(
                    (option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() =>
                          handleFuneralTypeChange(
                            option.value
                          )
                        }
                        className={`rounded-xl border p-4 text-left transition ${
                          funeralType === option.value
                            ? "border-slate-900 bg-slate-50 ring-2 ring-slate-200"
                            : "border-slate-200 hover:bg-slate-50"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border ${
                              funeralType ===
                              option.value
                                ? "border-slate-900"
                                : "border-slate-300"
                            }`}
                          >
                            {funeralType ===
                              option.value && (
                              <div className="h-2.5 w-2.5 rounded-full bg-slate-900" />
                            )}
                          </div>

                          <div>
                            <p className="text-sm font-semibold text-slate-900">
                              {option.label}
                            </p>
                            <p className="mt-1 text-xs leading-5 text-slate-500">
                              {option.description}
                            </p>
                          </div>
                        </div>
                      </button>
                    )
                  )}
                </div>
              </div>

              {/* Membership */}
              {funeralType !== "private" && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
                  <div className="mb-4 flex items-center gap-3">
                    <div className="rounded-lg bg-white p-2 text-slate-600">
                      <Users size={18} />
                    </div>

                    <div>
                      <h4 className="font-semibold text-slate-900">
                        Membership & Cover
                      </h4>
                      <p className="text-xs text-slate-500">
                        Link this case to an existing membership.
                      </p>
                    </div>
                  </div>

                  <label className="mb-2 block text-sm font-medium text-slate-700">
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
                    className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                  >
                    <option value="">
                      Select membership
                    </option>

                    {memberships.map((membership) => {
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
                          — {membership.membership_number}
                        </option>
                      );
                    })}
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
                          selectedPlan?.name || "Unknown"
                        }
                      />

                      <InfoCard
                        label="Monthly Contribution"
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
                    <div className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
                      <p className="font-semibold">
                        Coverage notice
                      </p>
                      <p className="mt-1">
                        {membershipWarning}
                      </p>
                    </div>
                  )}

                  {funeralType === "dependent" && (
                    <div className="mt-5">
                      <label className="mb-2 block text-sm font-medium text-slate-700">
                        Covered Dependent
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
                        disabled={!form.membership_id}
                        className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none disabled:cursor-not-allowed disabled:bg-slate-100 focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
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
                              {dependent.last_name}{" "}
                              — {formatRelationship(
                                dependent.relationship
                              )}
                            </option>
                          )
                        )}
                      </select>

                      {dependentWarning && (
                        <div className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
                          <p className="font-semibold">
                            Dependent coverage notice
                          </p>
                          <p className="mt-1">
                            {dependentWarning}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Case information */}
              <div>
                <h4 className="mb-4 font-semibold text-slate-900">
                  Case Information
                </h4>

                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    label="Case Number"
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
                      updateForm("status", value)
                    }
                    options={STATUS_OPTIONS.filter(
                      (item) => item !== "all"
                    )}
                  />

                  <FormField
                    label="Deceased Full Name"
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
                    label="Date of Birth"
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
                    label="Date of Death"
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
                    label="Funeral Date"
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
              </div>

              {/* Next of kin */}
              <div>
                <h4 className="mb-4 font-semibold text-slate-900">
                  Next of Kin
                </h4>

                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    label="Next of Kin Name"
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
                    label="Next of Kin Phone"
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
              </div>

              {/* Funeral */}
              <div>
                <h4 className="mb-4 font-semibold text-slate-900">
                  Funeral Details
                </h4>

                <FormField
                  label="Funeral Venue"
                  value={form.funeral_venue}
                  onChange={(value) =>
                    updateForm(
                      "funeral_venue",
                      value
                    )
                  }
                  placeholder="Funeral venue"
                />
              </div>

              {/* Notes */}
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Notes
                </label>

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
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                />
              </div>

              <div className="flex justify-end gap-3 border-t pt-5">
                <button
                  type="button"
                  onClick={() =>
                    setShowCreateForm(false)
                  }
                  className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {creating
                    ? "Creating..."
                    : "Create Case"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

function StatCard({
  title,
  value,
}: {
  title: string;
  value: number;
}) {
  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">
        {title}
      </p>

      <p className="mt-3 text-2xl font-bold text-slate-900">
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
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-xs font-medium text-slate-500">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-slate-900">
        {value}
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
      <label className="mb-2 block text-sm font-medium text-slate-700">
        {label}
        {required && (
          <span className="ml-1 text-red-500">*</span>
        )}
      </label>

      {type === "select" ? (
        <select
          value={value}
          onChange={(event) =>
            onChange(event.target.value)
          }
          required={required}
          className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
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
          className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
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
    open: "bg-blue-50 text-blue-700",
    confirmed: "bg-indigo-50 text-indigo-700",
    in_progress: "bg-amber-50 text-amber-700",
    completed: "bg-emerald-50 text-emerald-700",
    closed: "bg-slate-100 text-slate-700",
    cancelled: "bg-red-50 text-red-700",
  };

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${
        styles[status] ||
        "bg-slate-100 text-slate-700"
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
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    minimumFractionDigits: 2,
  }).format(Number(value));
}
