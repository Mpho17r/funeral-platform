"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Edit3,
  Plus,
  Search,
  Trash2,
  Users,
  X,
} from "lucide-react";
import api from "@/lib/api";

type Member = {
  id: string;
  member_number: string;
  first_name: string;
  last_name: string;
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

export default function CoveredDependentsPage() {
  const [dependents, setDependents] = useState<CoveredDependent[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);

  const [search, setSearch] = useState("");
  const [membershipFilter, setMembershipFilter] = useState("");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [form, setForm] = useState<DependentForm>(emptyForm);
  const [error, setError] = useState("");

  const loadData = async () => {
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
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError("Your session has expired. Please log in again.");
      } else {
        setError(
          err?.response?.data?.detail ||
            "Failed to load covered dependents."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const memberMap = useMemo(() => {
    return new Map(members.map((member) => [member.id, member]));
  }, [members]);

  const planMap = useMemo(() => {
    return new Map(plans.map((plan) => [plan.id, plan]));
  }, [plans]);

  const membershipMap = useMemo(() => {
    return new Map(
      memberships.map((membership) => [membership.id, membership])
    );
  }, [memberships]);

  const getMemberName = (membershipId: string) => {
    const membership = membershipMap.get(membershipId);

    if (!membership) {
      return "Unknown member";
    }

    const member = memberMap.get(membership.member_id);

    if (!member) {
      return membership.membership_number;
    }

    return `${member.first_name} ${member.last_name}`;
  };

  const getMembershipLabel = (membershipId: string) => {
    const membership = membershipMap.get(membershipId);

    if (!membership) {
      return "Unknown membership";
    }

    const memberName = getMemberName(membershipId);

    return `${memberName} — ${membership.membership_number}`;
  };

  const getPlanName = (membershipId: string) => {
    const membership = membershipMap.get(membershipId);

    if (!membership) {
      return "—";
    }

    return planMap.get(membership.plan_id)?.name || "—";
  };

  const filteredDependents = useMemo(() => {
    const term = search.trim().toLowerCase();

    return dependents.filter((dependent) => {
      const matchesMembership =
        !membershipFilter ||
        dependent.membership_id === membershipFilter;

      if (!matchesMembership) {
        return false;
      }

      if (!term) {
        return true;
      }

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
    memberMap,
  ]);

  const activeCount = dependents.filter(
    (dependent) => dependent.status === "active"
  ).length;

  const removedCount = dependents.filter(
    (dependent) => dependent.status === "removed"
  ).length;

  const deceasedCount = dependents.filter(
    (dependent) => dependent.status === "deceased"
  ).length;

  const openCreateForm = () => {
    setEditingId(null);
    setForm({
      ...emptyForm,
      membership_id: membershipFilter || "",
    });
    setError("");
    setShowForm(true);
  };

  const openEditForm = (dependent: CoveredDependent) => {
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
  };

  const closeForm = () => {
    if (saving) {
      return;
    }

    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
    setError("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
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
        await api.patch(
          `/covered-dependents/${editingId}`,
          payload
        );
      } else {
        await api.post("/covered-dependents", payload);
      }

      await loadData();
      closeForm();
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError("Your session has expired. Please log in again.");
      } else if (err?.response?.status === 409) {
        setError(
          err?.response?.data?.detail ||
            "This covered dependent already exists."
        );
      } else {
        setError(
          err?.response?.data?.detail ||
            "Failed to save covered dependent."
        );
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (dependent: CoveredDependent) => {
    const confirmed = window.confirm(
      `Remove ${dependent.first_name} ${dependent.last_name} from this membership?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setError("");

      await api.delete(`/covered-dependents/${dependent.id}`);

      await loadData();
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError("Your session has expired. Please log in again.");
      } else {
        setError(
          err?.response?.data?.detail ||
            "Failed to delete covered dependent."
        );
      }
    }
  };

  const formatDate = (value: string | null) => {
    if (!value) {
      return "—";
    }

    const date = new Date(`${value}T00:00:00`);

    return date.toLocaleDateString("en-ZA", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  const statusClass = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-700";
      case "removed":
        return "bg-gray-100 text-gray-700";
      case "deceased":
        return "bg-red-100 text-red-700";
      default:
        return "bg-gray-100 text-gray-700";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Covered Dependents
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage people covered under member funeral plans.
          </p>
        </div>

        <button
          type="button"
          onClick={openCreateForm}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800"
        >
          <Plus size={18} />
          Add Dependent
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>

          <button
            type="button"
            onClick={() => setError("")}
            className="ml-4"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Active Dependents
              </p>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {activeCount}
              </p>
            </div>

            <div className="rounded-lg bg-green-50 p-3 text-green-600">
              <Users size={22} />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Removed
              </p>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {removedCount}
              </p>
            </div>

            <div className="rounded-lg bg-gray-100 p-3 text-gray-600">
              <Users size={22} />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Deceased
              </p>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {deceasedCount}
              </p>
            </div>

            <div className="rounded-lg bg-red-50 p-3 text-red-600">
              <Users size={22} />
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row">
          <div className="relative flex-1">
            <Search
              size={18}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            />

            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search dependent, member or membership number..."
              className="w-full rounded-lg border border-gray-300 py-2.5 pl-10 pr-4 text-sm outline-none transition focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
            />
          </div>

          <select
            value={membershipFilter}
            onChange={(event) => setMembershipFilter(event.target.value)}
            className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
          >
            <option value="">All memberships</option>

            {memberships.map((membership) => (
              <option
                key={membership.id}
                value={membership.id}
              >
                {getMembershipLabel(membership.id)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px]">
            <thead className="border-b border-gray-200 bg-gray-50">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Dependent
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Member
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Relationship
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Date of Birth
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Cover
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Status
                </th>

                <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-5 py-12 text-center text-sm text-gray-500"
                  >
                    Loading covered dependents...
                  </td>
                </tr>
              ) : filteredDependents.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-5 py-12 text-center"
                  >
                    <Users
                      size={36}
                      className="mx-auto text-gray-300"
                    />

                    <p className="mt-3 text-sm font-medium text-gray-700">
                      No covered dependents found
                    </p>

                    <p className="mt-1 text-sm text-gray-500">
                      Add a dependent to a membership to get started.
                    </p>
                  </td>
                </tr>
              ) : (
                filteredDependents.map((dependent) => (
                  <tr
                    key={dependent.id}
                    className="hover:bg-gray-50"
                  >
                    <td className="px-5 py-4">
                      <div>
                        <p className="font-medium text-gray-900">
                          {dependent.first_name}{" "}
                          {dependent.last_name}
                        </p>

                        {dependent.id_number && (
                          <p className="mt-1 text-xs text-gray-500">
                            ID: {dependent.id_number}
                          </p>
                        )}
                      </div>
                    </td>

                    <td className="px-5 py-4">
                      <p className="font-medium text-gray-900">
                        {getMemberName(dependent.membership_id)}
                      </p>

                      <p className="mt-1 text-xs text-gray-500">
                        {membershipMap.get(
                          dependent.membership_id
                        )?.membership_number || "—"}
                      </p>
                    </td>

                    <td className="px-5 py-4">
                      <div className="space-y-1">
                        <p className="text-sm capitalize text-gray-900">
                          {dependent.relationship}
                        </p>

                        <p className="text-xs text-gray-500">
                          {getPlanName(dependent.membership_id)}
                        </p>
                      </div>
                    </td>

                    <td className="px-5 py-4 text-sm text-gray-700">
                      {formatDate(dependent.date_of_birth)}
                    </td>

                    <td className="px-5 py-4">
                      <p className="text-sm text-gray-700">
                        {formatDate(dependent.cover_start_date)}
                      </p>

                      <p className="mt-1 text-xs text-gray-500">
                        to{" "}
                        {formatDate(dependent.cover_end_date)}
                      </p>
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${statusClass(
                          dependent.status
                        )}`}
                      >
                        {dependent.status}
                      </span>
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            openEditForm(dependent)
                          }
                          className="rounded-lg border border-gray-200 p-2 text-gray-600 transition hover:bg-gray-100 hover:text-gray-900"
                          title="Edit dependent"
                        >
                          <Edit3 size={16} />
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            handleDelete(dependent)
                          }
                          className="rounded-lg border border-red-200 p-2 text-red-600 transition hover:bg-red-50"
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

      {/* Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
              <div>
                <h2 className="text-lg font-bold text-gray-900">
                  {editingId
                    ? "Edit Covered Dependent"
                    : "Add Covered Dependent"}
                </h2>

                <p className="mt-1 text-sm text-gray-500">
                  Add a person covered under a membership.
                </p>
              </div>

              <button
                type="button"
                onClick={closeForm}
                className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-900"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="space-y-5 p-6"
            >
              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">
                  Membership
                </label>

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
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900 disabled:bg-gray-100"
                >
                  <option value="">
                    Select membership
                  </option>

                  {memberships.map((membership) => (
                    <option
                      key={membership.id}
                      value={membership.id}
                    >
                      {getMembershipLabel(membership.id)}
                    </option>
                  ))}
                </select>

                {form.membership_id && (
                  <p className="mt-1.5 text-xs text-gray-500">
                    Plan:{" "}
                    {getPlanName(form.membership_id)}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    First Name
                  </label>

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
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Last Name
                  </label>

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
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Relationship
                  </label>

                  <select
                    value={form.relationship}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        relationship: event.target.value,
                      })
                    }
                    required
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm capitalize outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  >
                    {relationships.map((relationship) => (
                      <option
                        key={relationship}
                        value={relationship}
                      >
                        {relationship}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Status
                  </label>

                  <select
                    value={form.status}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        status: event.target.value,
                      })
                    }
                    required
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm capitalize outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  >
                    {statuses.map((status) => (
                      <option
                        key={status}
                        value={status}
                      >
                        {status}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    ID Number
                  </label>

                  <input
                    type="text"
                    value={form.id_number}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        id_number: event.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Phone
                  </label>

                  <input
                    type="tel"
                    value={form.phone}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        phone: event.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Date of Birth
                  </label>

                  <input
                    type="date"
                    value={form.date_of_birth}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        date_of_birth: event.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Cover Start
                  </label>

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
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Cover End
                  </label>

                  <input
                    type="date"
                    value={form.cover_end_date}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        cover_end_date: event.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 border-t border-gray-200 pt-5">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={saving}
                  className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving
                    ? "Saving..."
                    : editingId
                      ? "Save Changes"
                      : "Add Dependent"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
