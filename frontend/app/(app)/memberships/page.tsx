"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  Edit3,
  Plus,
  X,
  XCircle,
} from "lucide-react";

import api from "@/lib/api";

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

type MembershipForm = {
  member_id: string;
  plan_id: string;
  membership_number: string;
  start_date: string;
  status: string;
  next_due_date: string;
};

const emptyForm: MembershipForm = {
  member_id: "",
  plan_id: "",
  membership_number: "",
  start_date: new Date().toISOString().split("T")[0],
  status: "active",
  next_due_date: "",
};

const statuses = [
  "active",
  "arrears",
  "lapsed",
  "cancelled",
];

export default function MembershipsPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [editingMembership, setEditingMembership] =
    useState<Membership | null>(null);

  const [form, setForm] = useState<MembershipForm>(emptyForm);

  async function loadData() {
    try {
      setLoading(true);
      setError("");

      const [membersResponse, plansResponse, membershipsResponse] =
        await Promise.all([
          api.get<Member[]>("/members"),
          api.get<MembershipPlan[]>("/membership-plans"),
          api.get<Membership[]>("/memberships"),
        ]);

      setMembers(membersResponse.data);
      setPlans(plansResponse.data);
      setMemberships(membershipsResponse.data);
    } catch (err: any) {
      console.error("Failed to load membership data:", err);

      if (err.response?.status === 401) {
        setError("Your session has expired. Please log in again.");
      } else {
        setError(
          err.response?.data?.detail ||
            "Unable to load membership information."
        );
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  function openCreateForm() {
    setEditingMembership(null);
    setForm({
      ...emptyForm,
      start_date: new Date().toISOString().split("T")[0],
    });
    setFormError("");
    setShowForm(true);
  }

  function openEditForm(membership: Membership) {
    setEditingMembership(membership);

    setForm({
      member_id: membership.member_id,
      plan_id: membership.plan_id,
      membership_number: membership.membership_number,
      start_date: membership.start_date,
      status: membership.status,
      next_due_date: membership.next_due_date || "",
    });

    setFormError("");
    setShowForm(true);
  }

  function closeForm() {
    if (saving) {
      return;
    }

    setShowForm(false);
    setEditingMembership(null);
    setForm(emptyForm);
    setFormError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setFormError("");

    if (!editingMembership && !form.member_id) {
      setFormError("Please select a member.");
      return;
    }

    if (!form.plan_id) {
      setFormError("Please select a membership plan.");
      return;
    }

    if (!form.membership_number.trim()) {
      setFormError("Membership number is required.");
      return;
    }

    if (!form.start_date) {
      setFormError("Start date is required.");
      return;
    }

    try {
      setSaving(true);

      if (editingMembership) {
        const payload = {
          membership_number: form.membership_number.trim(),
          plan_id: form.plan_id,
          start_date: form.start_date,
          status: form.status,
          next_due_date: form.next_due_date || null,
        };

        const response = await api.patch<Membership>(
          `/memberships/${editingMembership.id}`,
          payload
        );

        setMemberships((current) =>
          current.map((membership) =>
            membership.id === editingMembership.id
              ? response.data
              : membership
          )
        );
      } else {
        const payload = {
          member_id: form.member_id,
          plan_id: form.plan_id,
          membership_number: form.membership_number.trim(),
          start_date: form.start_date,
          status: form.status,
          next_due_date: form.next_due_date || null,
        };

        const response = await api.post<Membership>(
          "/memberships",
          payload
        );

        setMemberships((current) => [response.data, ...current]);
      }

      closeForm();
    } catch (err: any) {
      console.error("Failed to save membership:", err);

      if (err.response?.status === 401) {
        setFormError(
          "You are not authorized to manage memberships. Main Admin access is required."
        );
      } else {
        setFormError(
          err.response?.data?.detail ||
            "Unable to save membership."
        );
      }
    } finally {
      setSaving(false);
    }
  }

  function getMember(memberId: string) {
    return members.find((member) => member.id === memberId);
  }

  function getPlan(planId: string) {
    return plans.find((plan) => plan.id === planId);
  }

  function formatCurrency(value: string | number) {
    return new Intl.NumberFormat("en-ZA", {
      style: "currency",
      currency: "ZAR",
      minimumFractionDigits: 2,
    }).format(Number(value));
  }

  function formatDate(value: string | null) {
    if (!value) {
      return "—";
    }

    return new Intl.DateTimeFormat("en-ZA", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(new Date(`${value}T00:00:00`));
  }

  function statusClasses(status: string) {
    switch (status) {
      case "active":
        return "bg-green-50 text-green-700";

      case "arrears":
        return "bg-amber-50 text-amber-700";

      case "lapsed":
        return "bg-red-50 text-red-700";

      case "cancelled":
        return "bg-slate-100 text-slate-500";

      default:
        return "bg-slate-100 text-slate-600";
    }
  }

  return (
    <div className="flex min-h-screen bg-slate-100">

      <main className="min-w-0 flex-1">
        <div className="border-b border-slate-200 bg-white">
          <div className="flex items-center justify-between px-6 py-5">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                Memberships
              </h1>

              <p className="mt-1 text-sm text-slate-500">
                Manage member funeral-cover memberships and their status.
              </p>
            </div>

            <button
              type="button"
              onClick={openCreateForm}
              className="flex items-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              <Plus size={18} />
              Add Membership
            </button>
          </div>
        </div>

        <div className="p-6">
          {error && (
            <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mb-6 grid gap-4 md:grid-cols-4">
            <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
              <p className="text-sm text-slate-500">
                Total Memberships
              </p>

              <p className="mt-2 text-2xl font-bold text-slate-900">
                {memberships.length}
              </p>
            </div>

            <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
              <p className="text-sm text-slate-500">
                Active
              </p>

              <p className="mt-2 text-2xl font-bold text-green-700">
                {
                  memberships.filter(
                    (membership) =>
                      membership.status === "active"
                  ).length
                }
              </p>
            </div>

            <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
              <p className="text-sm text-slate-500">
                In Arrears
              </p>

              <p className="mt-2 text-2xl font-bold text-amber-600">
                {
                  memberships.filter(
                    (membership) =>
                      membership.status === "arrears"
                  ).length
                }
              </p>
            </div>

            <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
              <p className="text-sm text-slate-500">
                Lapsed
              </p>

              <p className="mt-2 text-2xl font-bold text-red-600">
                {
                  memberships.filter(
                    (membership) =>
                      membership.status === "lapsed"
                  ).length
                }
              </p>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl bg-white ring-1 ring-slate-200">
            <div className="border-b border-slate-200 px-6 py-4">
              <h2 className="font-semibold text-slate-900">
                Member Cover
              </h2>
            </div>

            {loading ? (
              <div className="p-10 text-center text-sm text-slate-500">
                Loading memberships...
              </div>
            ) : memberships.length === 0 ? (
              <div className="p-12 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                  <Plus size={22} className="text-slate-500" />
                </div>

                <h3 className="mt-4 font-semibold text-slate-900">
                  No memberships yet
                </h3>

                <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
                  Assign a member to an active funeral-cover plan to
                  create their membership.
                </p>

                <button
                  type="button"
                  onClick={openCreateForm}
                  className="mt-5 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
                >
                  Create Membership
                </button>
              </div>
            ) : (
              <div className="divide-y divide-slate-200">
                {memberships.map((membership) => {
                  const member = getMember(membership.member_id);
                  const plan = getPlan(membership.plan_id);

                  return (
                    <div
                      key={membership.id}
                      className="px-6 py-5"
                    >
                      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-3">
                            <h3 className="font-semibold text-slate-900">
                              {member
                                ? `${member.first_name} ${member.last_name}`
                                : "Unknown Member"}
                            </h3>

                            <span
                              className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${statusClasses(
                                membership.status
                              )}`}
                            >
                              {membership.status}
                            </span>
                          </div>

                          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-500">
                            <span>
                              Member No:{" "}
                              <strong className="font-medium text-slate-700">
                                {member?.member_number || "—"}
                              </strong>
                            </span>

                            <span>
                              Membership No:{" "}
                              <strong className="font-medium text-slate-700">
                                {membership.membership_number}
                              </strong>
                            </span>
                          </div>

                          <div className="mt-4 grid gap-4 sm:grid-cols-3">
                            <div>
                              <p className="text-xs uppercase tracking-wide text-slate-400">
                                Plan
                              </p>

                              <p className="mt-1 text-sm font-medium text-slate-800">
                                {plan?.name || "Unknown Plan"}
                              </p>

                              {plan && (
                                <p className="text-xs text-slate-500">
                                  {formatCurrency(
                                    plan.monthly_contribution
                                  )}
                                  {" / month"}
                                </p>
                              )}
                            </div>

                            <div>
                              <p className="text-xs uppercase tracking-wide text-slate-400">
                                Start Date
                              </p>

                              <p className="mt-1 text-sm font-medium text-slate-800">
                                {formatDate(
                                  membership.start_date
                                )}
                              </p>
                            </div>

                            <div>
                              <p className="text-xs uppercase tracking-wide text-slate-400">
                                Next Due
                              </p>

                              <p className="mt-1 flex items-center gap-1 text-sm font-medium text-slate-800">
                                <CalendarDays size={15} />
                                {formatDate(
                                  membership.next_due_date
                                )}
                              </p>
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() =>
                            openEditForm(membership)
                          }
                          className="flex shrink-0 items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                        >
                          <Edit3 size={16} />
                          Edit
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </main>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  {editingMembership
                    ? "Edit Membership"
                    : "Create Membership"}
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  Connect a member to a funeral-cover plan.
                </p>
              </div>

              <button
                type="button"
                onClick={closeForm}
                disabled={saving}
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-50"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="max-h-[80vh] overflow-y-auto p-6"
            >
              {formError && (
                <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {formError}
                </div>
              )}

              <div className="space-y-5">
                {!editingMembership && (
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">
                      Member
                    </label>

                    <select
                      value={form.member_id}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          member_id: event.target.value,
                        })
                      }
                      disabled={saving}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                    >
                      <option value="">
                        Select a member
                      </option>

                      {members
                        .filter(
                          (member) =>
                            member.status !== "deceased"
                        )
                        .map((member) => (
                          <option
                            key={member.id}
                            value={member.id}
                          >
                            {member.first_name}{" "}
                            {member.last_name} —{" "}
                            {member.member_number}
                          </option>
                        ))}
                    </select>

                    {members.length === 0 && (
                      <p className="mt-2 text-xs text-amber-600">
                        No members exist yet. Create a member
                        first.
                      </p>
                    )}
                  </div>
                )}

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">
                    Membership Plan
                  </label>

                  <select
                    value={form.plan_id}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        plan_id: event.target.value,
                      })
                    }
                    disabled={saving}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  >
                    <option value="">
                      Select an active plan
                    </option>

                    {plans
                      .filter((plan) => plan.is_active)
                      .map((plan) => (
                        <option
                          key={plan.id}
                          value={plan.id}
                        >
                          {plan.name} —{" "}
                          {formatCurrency(
                            plan.monthly_contribution
                          )}
                          /month
                        </option>
                      ))}
                  </select>

                  {plans.filter(
                    (plan) => plan.is_active
                  ).length === 0 && (
                    <p className="mt-2 text-xs text-amber-600">
                      No active membership plans are available.
                    </p>
                  )}
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">
                    Membership Number
                  </label>

                  <input
                    type="text"
                    value={form.membership_number}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        membership_number:
                          event.target.value,
                      })
                    }
                    placeholder="e.g. MBR-0001"
                    disabled={saving}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  />
                </div>

                <div className="grid gap-5 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">
                      Start Date
                    </label>

                    <input
                      type="date"
                      value={form.start_date}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          start_date: event.target.value,
                        })
                      }
                      disabled={saving}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                    />
                  </div>

                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">
                      Next Due Date
                    </label>

                    <input
                      type="date"
                      value={form.next_due_date}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          next_due_date: event.target.value,
                        })
                      }
                      disabled={saving}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                    />

                    <p className="mt-1 text-xs text-slate-400">
                      Leave blank to let the backend calculate it.
                    </p>
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">
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
                    disabled={saving}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm capitalize outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  >
                    {statuses.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
                  <div className="flex gap-3">
                    <CheckCircle2
                      size={18}
                      className="mt-0.5 shrink-0 text-slate-500"
                    />

                    <p>
                      The member must belong to this business and
                      the selected plan must be active. A member
                      can only have one active or arrears
                      membership.
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-7 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={saving}
                  className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-slate-950 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving
                    ? "Saving..."
                    : editingMembership
                      ? "Save Changes"
                      : "Create Membership"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
