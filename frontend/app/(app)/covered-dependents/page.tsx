"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  Edit3,
  Heart,
  Plus,
  Search,
  Trash2,
  UserRound,
  Users,
  X,
} from "lucide-react";

import api from "@/lib/api";
import { ALL_BRANCHES, BranchFilter, matchesBranch } from "@/components/BranchControls";
import { useBranches } from "@/lib/branches";

type Member = {
  id: string;
  member_number: string;
  first_name: string;
  last_name: string;
  branch_id?: string | null;
  region?: string | null;
  phone?: string | null;
};

type MembershipPlan = {
  id: string;
  name: string;
  monthly_contribution: string | number;
  is_active: boolean;
};

type Membership = {
  id: string;
  member_id: string;
  plan_id: string;
  membership_number: string;
  start_date: string;
  status: string;
  next_due_date: string | null;
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

type DependentForm = {
  membership_id: string;
  first_name: string;
  last_name: string;
  relationship: string;
  id_number: string;
  date_of_birth: string;
  phone: string;
  status: string;
  cover_start_date: string;
  cover_end_date: string;
};

const emptyForm: DependentForm = {
  membership_id: "",
  first_name: "",
  last_name: "",
  relationship: "child",
  id_number: "",
  date_of_birth: "",
  phone: "",
  status: "active",
  cover_start_date: new Date().toISOString().split("T")[0],
  cover_end_date: "",
};

const relationships = [
  "spouse",
  "partner",
  "child",
  "parent",
  "sibling",
  "grandparent",
  "grandchild",
  "other",
];

const statuses = ["active", "removed", "deceased"];

const inputClassName =
  "w-full rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm text-[var(--fos-text)] outline-none transition placeholder:text-[var(--fos-text-muted)] focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 disabled:bg-[var(--fos-page)] disabled:text-[var(--fos-text-muted)]";

function formatDate(value: string | null) {
  if (!value) return "—";

  return new Date(`${value}T00:00:00`).toLocaleDateString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function statusLabel(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function relationshipLabel(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function statusClass(status: string) {
  switch (status) {
    case "active":
      return "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/15";
    case "removed":
      return "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] ring-1 ring-inset ring-slate-500/10";
    case "deceased":
      return "bg-purple-50 text-purple-700 ring-1 ring-inset ring-purple-600/15";
    default:
      return "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)] ring-1 ring-inset ring-slate-500/10";
  }
}

function initials(firstName: string, lastName: string) {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

function StatCard({
  label,
  value,
  detail,
  icon,
  tone,
}: {
  label: string;
  value: number;
  detail: string;
  icon: React.ReactNode;
  tone: string;
}) {
  return (
    <div className="rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] p-5 shadow-[0_2px_12px_rgba(15,23,42,0.04)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-[var(--fos-text-muted)]">{label}</p>

          <p className="mt-2 text-3xl font-semibold tracking-tight text-[var(--fos-text)]">
            {value}
          </p>

          <p className="mt-1 text-xs text-[var(--fos-text-muted)]">{detail}</p>
        </div>

        <div className={`rounded-xl p-3 ${tone}`}>{icon}</div>
      </div>
    </div>
  );
}

function FormField({
  label,
  required,
  children,
  hint,
  className = "",
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
        {label}
        {required && <span className="ml-1 text-emerald-600">*</span>}
      </label>

      {children}

      {hint && <p className="mt-1.5 text-xs text-[var(--fos-text-muted)]">{hint}</p>}
    </div>
  );
}

function EmptyState({
  hasFilters,
  onClear,
  onCreate,
}: {
  hasFilters: boolean;
  onClear: () => void;
  onCreate: () => void;
}) {
  return (
    <div className="px-6 py-16 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
        <Users size={26} />
      </div>

      <h2 className="mt-5 text-lg font-semibold text-[var(--fos-text)]">
        {hasFilters
          ? "No covered dependents found"
          : "No covered dependents yet"}
      </h2>

      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--fos-text-muted)]">
        {hasFilters
          ? "Try adjusting your search or membership filter."
          : "Add people covered under your members' funeral plans to keep family cover records organised."}
      </p>

      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {hasFilters && (
          <button
            type="button"
            onClick={onClear}
            className="rounded-xl border border-[var(--fos-border)] px-4 py-2.5 text-sm font-medium text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)]"
          >
            Clear filters
          </button>
        )}

        {!hasFilters && (
          <button
            type="button"
            onClick={onCreate}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800"
          >
            <Plus size={17} />
            Add dependent
          </button>
        )}
      </div>
    </div>
  );
}

function getApiErrorDetails(error: unknown): {
  status?: number;
  detail?: string;
} {
  if (error === null || typeof error !== "object") return {};

  const errorRecord = error as Record<string, unknown>;
  const response = errorRecord.response;
  if (response === null || typeof response !== "object") return {};

  const responseRecord = response as Record<string, unknown>;
  const data = responseRecord.data;
  const detail =
    data !== null && typeof data === "object"
      ? (data as Record<string, unknown>).detail
      : undefined;

  return {
    status:
      typeof responseRecord.status === "number"
        ? responseRecord.status
        : undefined,
    detail: typeof detail === "string" ? detail : undefined,
  };
}

export default function CoveredDependentsPage() {
  const [dependents, setDependents] = useState<CoveredDependent[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);

  const [search, setSearch] = useState("");
  const [membershipFilter, setMembershipFilter] = useState("");
  const [view, setView] = useState<"households" | "list">("households");
  const [branchFilter, setBranchFilter] = useState(ALL_BRANCHES);
  const [regionFilter, setRegionFilter] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [focusMember, setFocusMember] = useState("");
  const branchData = useBranches();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [form, setForm] = useState<DependentForm>(emptyForm);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [
        dependentsResponse,
        membersResponse,
        plansResponse,
        membershipsResponse,
      ] = await Promise.all([
        api.get<CoveredDependent[]>("/covered-dependents"),
        api.get<Member[]>("/members"),
        api.get<MembershipPlan[]>("/membership-plans"),
        api.get<Membership[]>("/memberships"),
      ]);

      setDependents(dependentsResponse.data);
      setMembers(membersResponse.data);
      setPlans(plansResponse.data);
      setMemberships(membershipsResponse.data);
    } catch (err: unknown) {
      const { status, detail } = getApiErrorDetails(err);

      if (status === 401) {
        setError("Your session has expired. Please log in again.");
      } else if (status === 403) {
        setError("You do not have permission to view covered dependents.");
      } else {
        setError(detail || "Failed to load covered dependents.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    async function initializeData() {
      await loadData();
    }

    void initializeData();
  }, [loadData]);

  useEffect(() => {
    // Arriving from a member's row: open that member's household.
    const id = new URLSearchParams(window.location.search).get("member");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (id) setFocusMember(id);
  }, []);

  const memberMap = useMemo(
    () => new Map(members.map((member) => [member.id, member])),
    [members]
  );

  const planMap = useMemo(
    () => new Map(plans.map((plan) => [plan.id, plan])),
    [plans]
  );

  const membershipMap = useMemo(
    () =>
      new Map(
        memberships.map((membership) => [membership.id, membership])
      ),
    [memberships]
  );

  const getMemberName = useCallback(
    (membershipId: string) => {
      const membership = membershipMap.get(membershipId);

      if (!membership) return "Unknown member";

      const member = memberMap.get(membership.member_id);

      if (!member) return membership.membership_number;

      return `${member.first_name} ${member.last_name}`;
    },
    [memberMap, membershipMap]
  );

  function getMembershipLabel(membershipId: string) {
    const membership = membershipMap.get(membershipId);

    if (!membership) return "Unknown membership";

    return `${getMemberName(membershipId)} — ${membership.membership_number}`;
  }

  function getPlanName(membershipId: string) {
    const membership = membershipMap.get(membershipId);

    if (!membership) return "—";

    return planMap.get(membership.plan_id)?.name || "—";
  }

  const filteredDependents = useMemo(() => {
    const term = search.trim().toLowerCase();

    return dependents.filter((dependent) => {
      if (
        membershipFilter &&
        dependent.membership_id !== membershipFilter
      ) {
        return false;
      }

      if (!term) return true;

      const memberName = getMemberName(dependent.membership_id);
      const membership = membershipMap.get(dependent.membership_id);

      const searchable = [
        dependent.first_name,
        dependent.last_name,
        dependent.relationship,
        dependent.id_number || "",
        dependent.phone || "",
        dependent.status,
        memberName,
        membership?.membership_number || "",
      ]
        .join(" ")
        .toLowerCase();

      return searchable.includes(term);
    });
  }, [
    dependents,
    search,
    membershipFilter,
    membershipMap,
    getMemberName,
  ]);

  const regions = useMemo(
    () =>
      Array.from(
        new Set(members.map((m) => m.region).filter(Boolean) as string[])
      ).sort((a, b) => a.localeCompare(b)),
    [members]
  );

  // One household per paying member's membership, with the people it covers.
  const households = useMemo(() => {
    const term = search.trim().toLowerCase();
    const byMembership = new Map<string, CoveredDependent[]>();
    for (const dependent of dependents) {
      byMembership.set(dependent.membership_id, [
        ...(byMembership.get(dependent.membership_id) ?? []),
        dependent,
      ]);
    }

    return memberships
      .map((membership) => {
        const payer = memberMap.get(membership.member_id);
        const covered = byMembership.get(membership.id) ?? [];
        return { membership, payer, covered };
      })
      .filter(({ membership, payer, covered }) => {
        if (!payer) return false;
        const focused = focusMember === payer.id;
        if (!focused && covered.length === 0) return false;
        if (!matchesBranch(branchFilter, payer.branch_id ?? null)) return false;
        if (regionFilter && (payer.region || "") !== regionFilter) return false;
        if (membershipFilter && membership.id !== membershipFilter) return false;
        if (focusMember && !term) return focused;
        if (!term) return true;
        const text = [
          payer.first_name,
          payer.last_name,
          payer.member_number,
          membership.membership_number,
          ...covered.map((d) => `${d.first_name} ${d.last_name} ${d.id_number || ""}`),
        ]
          .join(" ")
          .toLowerCase();
        return text.includes(term);
      })
      .sort((a, b) =>
        `${a.payer?.last_name} ${a.payer?.first_name}`.localeCompare(
          `${b.payer?.last_name} ${b.payer?.first_name}`
        )
      );
  }, [
    dependents,
    memberships,
    memberMap,
    search,
    branchFilter,
    regionFilter,
    membershipFilter,
    focusMember,
  ]);

  const totalCount = dependents.length;

  const activeCount = dependents.filter(
    (dependent) => dependent.status === "active"
  ).length;

  const removedCount = dependents.filter(
    (dependent) => dependent.status === "removed"
  ).length;

  const deceasedCount = dependents.filter(
    (dependent) => dependent.status === "deceased"
  ).length;

  const hasFilters = Boolean(
    search.trim() ||
    membershipFilter ||
    regionFilter ||
    focusMember ||
    branchFilter !== ALL_BRANCHES
  );

  function clearFilters() {
    setSearch("");
    setMembershipFilter("");
    setBranchFilter(ALL_BRANCHES);
    setRegionFilter("");
    setFocusMember("");
  }

  function openCreateForm() {
    setEditingId(null);
    setForm({
      ...emptyForm,
      membership_id: membershipFilter || "",
    });
    setError("");
    setShowForm(true);
  }

  function openEditForm(dependent: CoveredDependent) {
    setEditingId(dependent.id);

    setForm({
      membership_id: dependent.membership_id,
      first_name: dependent.first_name,
      last_name: dependent.last_name,
      relationship: dependent.relationship,
      id_number: dependent.id_number || "",
      date_of_birth: dependent.date_of_birth || "",
      phone: dependent.phone || "",
      status: dependent.status,
      cover_start_date: dependent.cover_start_date,
      cover_end_date: dependent.cover_end_date || "",
    });

    setError("");
    setShowForm(true);
  }

  function closeForm() {
    if (saving) return;

    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
    setError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!form.membership_id) {
      setError("Please select a membership.");
      return;
    }

    if (!form.first_name.trim() || !form.last_name.trim()) {
      setError("First name and last name are required.");
      return;
    }

    if (
      form.cover_end_date &&
      form.cover_start_date &&
      form.cover_end_date < form.cover_start_date
    ) {
      setError("Cover end date cannot be before cover start date.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      const payload = {
        membership_id: form.membership_id,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        relationship: form.relationship,
        id_number: form.id_number.trim() || null,
        date_of_birth: form.date_of_birth || null,
        phone: form.phone.trim() || null,
        status: form.status,
        cover_start_date: form.cover_start_date,
        cover_end_date: form.cover_end_date || null,
      };

      if (editingId) {
        await api.patch(`/covered-dependents/${editingId}`, payload);
      } else {
        await api.post("/covered-dependents", payload);
      }

      await loadData();
      closeForm();
    } catch (err: unknown) {
      const { status, detail } = getApiErrorDetails(err);

      if (status === 401) {
        setError("Your session has expired. Please log in again.");
      } else if (status === 403) {
        setError("You do not have permission to manage covered dependents.");
      } else if (status === 409) {
        setError(detail || "This covered dependent already exists.");
      } else {
        setError(detail || "Failed to save covered dependent.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(dependent: CoveredDependent) {
    const confirmed = window.confirm(
      `Remove ${dependent.first_name} ${dependent.last_name} from this membership?`
    );

    if (!confirmed) return;

    try {
      setError("");
      await api.delete(`/covered-dependents/${dependent.id}`);
      await loadData();
    } catch (err: unknown) {
      const { status, detail } = getApiErrorDetails(err);

      if (status === 401) {
        setError("Your session has expired. Please log in again.");
      } else if (status === 403) {
        setError("You do not have permission to delete covered dependents.");
      } else {
        setError(detail || "Failed to delete covered dependent.");
      }
    }
  }

  return (
    <div className="space-y-7">
      {/* Header */}
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">
            Customers & Membership
          </p>

          <h1 className="mt-2 font-[family-name:var(--font-newsreader)] text-4xl leading-none tracking-tight text-[var(--fos-text)] sm:text-[42px]">
            Covered dependents
          </h1>

          <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--fos-text-muted)]">
            Manage the people covered under your members&apos; funeral plans
            and keep their family cover records accurate.
          </p>
        </div>

        <button
          type="button"
          onClick={openCreateForm}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800"
        >
          <Plus size={18} />
          Add dependent
        </button>
      </div>

      {/* Error */}
      {error && !showForm && (
        <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3.5 text-sm text-red-700">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />

          <span className="flex-1">{error}</span>

          <button
            type="button"
            onClick={() => setError("")}
            className="rounded-lg p-1 transition hover:bg-red-100"
          >
            <X size={17} />
          </button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total dependents"
          value={totalCount}
          detail="All recorded covered people"
          icon={<Users size={21} />}
          tone="bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)]"
        />

        <StatCard
          label="Active"
          value={activeCount}
          detail="Currently recorded as covered"
          icon={<CheckCircle2 size={21} />}
          tone="bg-emerald-50 text-emerald-600"
        />

        <StatCard
          label="Removed"
          value={removedCount}
          detail="No longer active on cover"
          icon={<Users size={21} />}
          tone="bg-[var(--fos-surface-muted)] text-[var(--fos-text-muted)]"
        />

        <StatCard
          label="Deceased"
          value={deceasedCount}
          detail="Recorded as deceased"
          icon={<Heart size={21} />}
          tone="bg-purple-50 text-purple-600"
        />
      </div>

      {/* Filters */}
      <div className="rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] p-4 shadow-[0_2px_12px_rgba(15,23,42,0.04)]">
        <div className="flex flex-col gap-3 lg:flex-row">
          <div className="relative flex-1">
            <Search
              size={18}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--fos-text-muted)]"
            />

            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search dependent, member or membership number..."
              className={`${inputClassName} pl-10`}
            />
          </div>

          <select
            value={membershipFilter}
            onChange={(event) => setMembershipFilter(event.target.value)}
            className={`${inputClassName} lg:w-[340px]`}
          >
            <option value="">All memberships</option>

            {memberships.map((membership) => (
              <option key={membership.id} value={membership.id}>
                {getMembershipLabel(membership.id)}
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

          {regions.length > 0 && (
            <select
              aria-label="Filter by region"
              value={regionFilter}
              onChange={(event) => setRegionFilter(event.target.value)}
              className={`${inputClassName} lg:w-[180px]`}
            >
              <option value="">All regions</option>
              {regions.map((region) => (
                <option key={region} value={region}>
                  {region}
                </option>
              ))}
            </select>
          )}

          <div
            role="tablist"
            aria-label="How to show covered people"
            className="inline-flex shrink-0 rounded-xl border border-[var(--fos-border)] p-1 text-sm"
          >
            {(
              [
                ["households", "By paying member"],
                ["list", "All people"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                role="tab"
                type="button"
                aria-selected={view === value}
                onClick={() => setView(value)}
                className={`rounded-lg px-3 py-2 font-medium ${
                  view === value
                    ? "bg-emerald-700 text-white"
                    : "text-[var(--fos-text-secondary)]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {hasFilters && (
          <div className="mt-3 flex items-center justify-between border-t border-[var(--fos-border)] pt-3">
            <p className="text-xs text-[var(--fos-text-muted)]">
              Showing {filteredDependents.length} of {dependents.length}{" "}
              dependents
            </p>

            <button
              type="button"
              onClick={clearFilters}
              className="text-xs font-semibold text-emerald-700 hover:underline"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {view === "households" && (
        <div className="space-y-3">
          {loading ? (
            <p className="rounded-2xl border p-8 text-center text-sm text-[var(--fos-text-muted)]">
              Loading covered dependents...
            </p>
          ) : households.length === 0 ? (
            <p className="rounded-2xl border p-8 text-center text-sm text-[var(--fos-text-muted)]">
              No households match. Covered people are listed under the member who pays.
            </p>
          ) : (
            households.map(({ membership, payer, covered }) => {
              const expanded =
                open.has(membership.id) ||
                focusMember === payer?.id ||
                Boolean(search.trim());
              return (
                <section
                  key={membership.id}
                  className="rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] shadow-[0_2px_12px_rgba(15,23,42,0.04)]"
                >
                  <button
                    type="button"
                    aria-expanded={expanded}
                    onClick={() =>
                      setOpen((current) => {
                        const next = new Set(current);
                        if (next.has(membership.id)) next.delete(membership.id);
                        else next.add(membership.id);
                        return next;
                      })
                    }
                    className="flex w-full items-center justify-between gap-3 p-4 text-left"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[var(--fos-text)]">
                        {payer?.first_name} {payer?.last_name}
                        <span className="ml-2 text-xs font-normal text-[var(--fos-text-muted)]">
                          pays · {membership.membership_number}
                        </span>
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--fos-text-muted)]">
                        {getPlanName(membership.id)}
                        {payer?.region ? ` · ${payer.region}` : ""}
                        {branchData.multiple && payer?.branch_id
                          ? ` · ${branchData.byId.get(payer.branch_id)?.name ?? ""}`
                          : ""}
                      </p>
                    </div>
                    <span className="shrink-0 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                      {covered.filter((d) => d.status === "active").length} covered
                      {covered.length !== covered.filter((d) => d.status === "active").length
                        ? ` · ${covered.length} recorded`
                        : ""}
                    </span>
                  </button>

                  {expanded && (
                    <div className="border-t border-[var(--fos-border)]">
                      {covered.length === 0 && (
                        <p className="p-4 text-sm text-[var(--fos-text-muted)]">
                          No one else is covered under this membership yet.
                        </p>
                      )}
                      <ul className="divide-y divide-slate-100">
                        {covered.map((dependent) => (
                          <li
                            key={dependent.id}
                            className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                          >
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-[var(--fos-text)]">
                                {dependent.first_name} {dependent.last_name}
                              </p>
                              <p className="text-xs text-[var(--fos-text-muted)]">
                                {relationshipLabel(dependent.relationship)}
                                {dependent.date_of_birth
                                  ? ` · born ${formatDate(dependent.date_of_birth)}`
                                  : ""}
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <span
                                className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(
                                  dependent.status
                                )}`}
                              >
                                {statusLabel(dependent.status)}
                              </span>
                              <button
                                type="button"
                                onClick={() => openEditForm(dependent)}
                                className="rounded-xl p-2 text-[var(--fos-text-muted)] hover:bg-[var(--fos-surface-muted)]"
                                title="Edit dependent"
                              >
                                <Edit3 size={16} />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDelete(dependent)}
                                className="rounded-xl p-2 text-red-500 hover:bg-red-50"
                                title="Delete dependent"
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                      <div className="p-3">
                        <button
                          type="button"
                          onClick={() => {
                            openCreateForm();
                            setForm((f) => ({ ...f, membership_id: membership.id }));
                          }}
                          className="text-sm font-semibold text-emerald-700 hover:underline"
                        >
                          + Add a covered person
                        </button>
                      </div>
                    </div>
                  )}
                </section>
              );
            })
          )}
        </div>
      )}

      {view === "list" && (<>
      {/* Desktop table */}
      <div className="hidden overflow-hidden rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] shadow-[0_2px_12px_rgba(15,23,42,0.04)] lg:block">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1120px]">
            <thead className="border-b border-[var(--fos-border)] bg-[var(--fos-page)]/70">
              <tr>
                {[
                  "Dependent",
                  "Member / membership",
                  "Relationship",
                  "Date of birth",
                  "Cover period",
                  "Status",
                  "Actions",
                ].map((heading) => (
                  <th
                    key={heading}
                    className={`px-5 py-3.5 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fos-text-muted)] ${
                      heading === "Actions" ? "text-right" : ""
                    }`}
                  >
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-5 py-14 text-center text-sm text-[var(--fos-text-muted)]"
                  >
                    Loading covered dependents...
                  </td>
                </tr>
              ) : filteredDependents.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      hasFilters={hasFilters}
                      onClear={clearFilters}
                      onCreate={openCreateForm}
                    />
                  </td>
                </tr>
              ) : (
                filteredDependents.map((dependent) => (
                  <tr
                    key={dependent.id}
                    className="transition hover:bg-[var(--fos-page)]/60"
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-xs font-bold text-emerald-700">
                          {initials(
                            dependent.first_name,
                            dependent.last_name
                          )}
                        </div>

                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-[var(--fos-text)]">
                            {dependent.first_name} {dependent.last_name}
                          </p>

                          {dependent.id_number && (
                            <p className="mt-0.5 text-xs text-[var(--fos-text-muted)]">
                              ID: {dependent.id_number}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="px-5 py-4">
                      <p className="text-sm font-medium text-[var(--fos-text)]">
                        {getMemberName(dependent.membership_id)}
                      </p>

                      <p className="mt-0.5 text-xs text-[var(--fos-text-muted)]">
                        {membershipMap.get(dependent.membership_id)
                          ?.membership_number || "—"}
                      </p>
                    </td>

                    <td className="px-5 py-4">
                      <p className="text-sm text-[var(--fos-text)]">
                        {relationshipLabel(dependent.relationship)}
                      </p>

                      <p className="mt-0.5 text-xs text-[var(--fos-text-muted)]">
                        {getPlanName(dependent.membership_id)}
                      </p>
                    </td>

                    <td className="px-5 py-4 text-sm text-[var(--fos-text-secondary)]">
                      {formatDate(dependent.date_of_birth)}
                    </td>

                    <td className="px-5 py-4">
                      <p className="text-sm text-[var(--fos-text-secondary)]">
                        {formatDate(dependent.cover_start_date)}
                      </p>

                      <p className="mt-0.5 text-xs text-[var(--fos-text-muted)]">
                        Until {formatDate(dependent.cover_end_date)}
                      </p>
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(
                          dependent.status
                        )}`}
                      >
                        {statusLabel(dependent.status)}
                      </span>
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => openEditForm(dependent)}
                          className="rounded-xl p-2 text-[var(--fos-text-muted)] transition hover:bg-[var(--fos-surface-muted)] hover:text-[var(--fos-text)]"
                          title="Edit dependent"
                        >
                          <Edit3 size={16} />
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDelete(dependent)}
                          className="rounded-xl p-2 text-red-500 transition hover:bg-red-50 hover:text-red-700"
                          title="Delete dependent"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile / tablet */}
      <div className="space-y-3 lg:hidden">
        {loading ? (
          <div className="rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] px-5 py-14 text-center text-sm text-[var(--fos-text-muted)]">
            Loading covered dependents...
          </div>
        ) : filteredDependents.length === 0 ? (
          <div className="rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)]">
            <EmptyState
              hasFilters={hasFilters}
              onClear={clearFilters}
              onCreate={openCreateForm}
            />
          </div>
        ) : (
          filteredDependents.map((dependent) => (
            <div
              key={dependent.id}
              className="rounded-2xl border border-[var(--fos-border)]/80 bg-[var(--fos-surface)] p-4 shadow-[0_2px_12px_rgba(15,23,42,0.04)]"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-xs font-bold text-emerald-700">
                    {initials(
                      dependent.first_name,
                      dependent.last_name
                    )}
                  </div>

                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[var(--fos-text)]">
                      {dependent.first_name} {dependent.last_name}
                    </p>

                    <p className="mt-0.5 text-xs text-[var(--fos-text-muted)]">
                      {relationshipLabel(dependent.relationship)}
                    </p>
                  </div>
                </div>

                <span
                  className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(
                    dependent.status
                  )}`}
                >
                  {statusLabel(dependent.status)}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 border-t border-[var(--fos-border)] pt-4">
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Member
                  </p>

                  <p className="mt-1 text-sm font-medium text-[var(--fos-text)]">
                    {getMemberName(dependent.membership_id)}
                  </p>
                </div>

                <div>
                  <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Membership
                  </p>

                  <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
                    {membershipMap.get(dependent.membership_id)
                      ?.membership_number || "—"}
                  </p>
                </div>

                <div>
                  <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Date of birth
                  </p>

                  <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
                    {formatDate(dependent.date_of_birth)}
                  </p>
                </div>

                <div>
                  <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                    Plan
                  </p>

                  <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
                    {getPlanName(dependent.membership_id)}
                  </p>
                </div>
              </div>

              <div className="mt-4 rounded-xl bg-[var(--fos-page)] p-3">
                <div className="flex items-center gap-2 text-xs font-medium text-[var(--fos-text-muted)]">
                  <CalendarDays size={14} />
                  Cover period
                </div>

                <p className="mt-1 text-sm text-[var(--fos-text)]">
                  {formatDate(dependent.cover_start_date)}
                  {" — "}
                  {formatDate(dependent.cover_end_date)}
                </p>
              </div>

              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => openEditForm(dependent)}
                  className="inline-flex items-center gap-2 rounded-xl border border-[var(--fos-border)] px-3.5 py-2 text-sm font-medium text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)]"
                >
                  <Edit3 size={15} />
                  Edit
                </button>

                <button
                  type="button"
                  onClick={() => handleDelete(dependent)}
                  className="inline-flex items-center gap-2 rounded-xl border border-red-200 px-3.5 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50"
                >
                  <Trash2 size={15} />
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      </>)}

      {/* Form modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-3 backdrop-blur-sm sm:p-5">
          <div className="flex max-h-[94vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-[var(--fos-surface)] shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[var(--fos-border)] px-5 py-5 sm:px-7">
              <div>
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
                  <UserRound size={19} />
                </div>

                <h2 className="font-[family-name:var(--font-newsreader)] text-2xl text-[var(--fos-text)]">
                  {editingId
                    ? "Edit covered dependent"
                    : "Add covered dependent"}
                </h2>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                  Keep the dependent&apos;s membership and cover information
                  accurate.
                </p>
              </div>

              <button
                type="button"
                onClick={closeForm}
                disabled={saving}
                className="rounded-xl p-2 text-[var(--fos-text-muted)] transition hover:bg-[var(--fos-surface-muted)] hover:text-[var(--fos-text-secondary)] disabled:opacity-50"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="overflow-y-auto">
              <div className="space-y-7 px-5 py-6 sm:px-7">
                {error && (
                  <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3.5 text-sm text-red-700">
                    <AlertCircle size={17} className="mt-0.5 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <section>
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-[var(--fos-text)]">
                      Membership
                    </h3>

                    <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                      Choose the membership responsible for this dependent&apos;s
                      cover.
                    </p>
                  </div>

                  <FormField
                    label="Membership"
                    required
                    hint={
                      form.membership_id
                        ? `Plan: ${getPlanName(form.membership_id)}`
                        : undefined
                    }
                  >
                    <select
                      value={form.membership_id}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          membership_id: event.target.value,
                        })
                      }
                      disabled={!!editingId}
                      required
                      className={inputClassName}
                    >
                      <option value="">Select membership</option>

                      {memberships.map((membership) => (
                        <option key={membership.id} value={membership.id}>
                          {getMembershipLabel(membership.id)}
                        </option>
                      ))}
                    </select>
                  </FormField>
                </section>

                <section className="border-t border-[var(--fos-border)] pt-7">
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-[var(--fos-text)]">
                      Personal details
                    </h3>

                    <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                      Basic information for the person covered by the plan.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <FormField label="First name" required>
                      <input
                        type="text"
                        value={form.first_name}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            first_name: event.target.value,
                          })
                        }
                        required
                        className={inputClassName}
                        placeholder="First name"
                      />
                    </FormField>

                    <FormField label="Last name" required>
                      <input
                        type="text"
                        value={form.last_name}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            last_name: event.target.value,
                          })
                        }
                        required
                        className={inputClassName}
                        placeholder="Last name"
                      />
                    </FormField>

                    <FormField label="Relationship" required>
                      <select
                        value={form.relationship}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            relationship: event.target.value,
                          })
                        }
                        required
                        className={inputClassName}
                      >
                        {relationships.map((relationship) => (
                          <option key={relationship} value={relationship}>
                            {relationshipLabel(relationship)}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <FormField label="Status" required>
                      <select
                        value={form.status}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            status: event.target.value,
                          })
                        }
                        required
                        className={inputClassName}
                      >
                        {statuses.map((status) => (
                          <option key={status} value={status}>
                            {statusLabel(status)}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <FormField label="ID number">
                      <input
                        type="text"
                        value={form.id_number}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            id_number: event.target.value,
                          })
                        }
                        className={inputClassName}
                        placeholder="Optional"
                      />
                    </FormField>

                    <FormField label="Phone">
                      <input
                        type="tel"
                        value={form.phone}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            phone: event.target.value,
                          })
                        }
                        className={inputClassName}
                        placeholder="Optional"
                      />
                    </FormField>

                    <FormField label="Date of birth">
                      <input
                        type="date"
                        value={form.date_of_birth}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            date_of_birth: event.target.value,
                          })
                        }
                        className={inputClassName}
                      />
                    </FormField>
                  </div>
                </section>

                <section className="border-t border-[var(--fos-border)] pt-7">
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-[var(--fos-text)]">
                      Cover period
                    </h3>

                    <p className="mt-1 text-xs text-[var(--fos-text-muted)]">
                      Record when this dependent&apos;s cover starts and, if
                      applicable, ends.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <FormField label="Cover start date" required>
                      <input
                        type="date"
                        value={form.cover_start_date}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            cover_start_date: event.target.value,
                          })
                        }
                        required
                        className={inputClassName}
                      />
                    </FormField>

                    <FormField
                      label="Cover end date"
                      hint="Leave blank if the cover has no recorded end date."
                    >
                      <input
                        type="date"
                        value={form.cover_end_date}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            cover_end_date: event.target.value,
                          })
                        }
                        className={inputClassName}
                      />
                    </FormField>
                  </div>
                </section>
              </div>

              <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t border-[var(--fos-border)] bg-[var(--fos-surface)]/95 px-5 py-4 backdrop-blur sm:px-7">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={saving}
                  className="rounded-xl border border-[var(--fos-border)] px-4 py-2.5 text-sm font-medium text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)] disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving ? (
                    "Saving..."
                  ) : editingId ? (
                    <>
                      <CheckCircle2 size={16} />
                      Save changes
                    </>
                  ) : (
                    <>
                      <Plus size={16} />
                      Add dependent
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
