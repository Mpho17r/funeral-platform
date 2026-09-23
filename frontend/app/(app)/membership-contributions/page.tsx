"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
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
  monthly_contribution: number | string;
};

type Membership = {
  id: string;
  member_id: string;
  plan_id: string;
  membership_number: string;
  status: string;
  next_due_date: string | null;
};

type Contribution = {
  id: string;
  membership_id: string;
  contribution_period: string;
  amount_due: number | string;
  amount_paid: number | string;
  due_date: string;
  status: string;
  paid_at: string | null;
};

type ContributionForm = {
  membership_id: string;
  contribution_period: string;
  amount_due: string;
  due_date: string;
};

const emptyForm: ContributionForm = {
  membership_id: "",
  contribution_period: "",
  amount_due: "",
  due_date: "",
};

function getCurrentMonthPeriod() {
  const today = new Date();

  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");

  return `${year}-${month}-01`;
}

function normalizeContributionPeriod(value: string) {
  if (!value) {
    return "";
  }

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");

  return `${year}-${month}-01`;
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return "—";
  }

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-ZA", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatMoney(value: number | string | null | undefined) {
  const amount = Number(value ?? 0);

  return amount.toLocaleString("en-ZA", {
    style: "currency",
    currency: "ZAR",
  });
}

function getStatusLabel(status: string) {
  switch (status) {
    case "partially_paid":
      return "Partially Paid";

    case "paid":
      return "Paid";

    case "overdue":
      return "Overdue";

    case "waived":
      return "Waived";

    case "refunded":
      return "Refunded";

    case "due":
    default:
      return "Due";
  }
}

function getStatusClass(status: string) {
  switch (status) {
    case "paid":
      return "bg-green-100 text-green-700";

    case "partially_paid":
      return "bg-yellow-100 text-yellow-700";

    case "overdue":
      return "bg-red-100 text-red-700";

    case "waived":
      return "bg-gray-100 text-gray-700";

    case "refunded":
      return "bg-purple-100 text-purple-700";

    case "due":
    default:
      return "bg-blue-100 text-blue-700";
  }
}

function extractApiError(error: any, fallback: string) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  );
}

export default function MembershipContributionsPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [contributions, setContributions] = useState<Contribution[]>([]);

  const [form, setForm] = useState<ContributionForm>({
    ...emptyForm,
    contribution_period: getCurrentMonthPeriod(),
  });

  const [editingId, setEditingId] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const getMember = (memberId: string) => {
    return members.find((member) => member.id === memberId);
  };

  const getPlan = (planId: string) => {
    return plans.find((plan) => plan.id === planId);
  };

  const getMembership = (membershipId: string) => {
    return memberships.find(
      (membership) => membership.id === membershipId
    );
  };

  const getMemberNameForMembership = (membership: Membership) => {
    const member = getMember(membership.member_id);

    if (!member) {
      return membership.membership_number;
    }

    return `${member.first_name} ${member.last_name}`;
  };

  const loadData = async () => {
    try {
      setLoading(true);
      setError("");

      const [
        membersResponse,
        plansResponse,
        membershipsResponse,
        contributionsResponse,
      ] = await Promise.all([
        api.get("/members"),
        api.get("/membership-plans"),
        api.get("/memberships"),
        api.get("/membership-contributions"),
      ]);

      setMembers(membersResponse.data);
      setPlans(plansResponse.data);
      setMemberships(membershipsResponse.data);
      setContributions(contributionsResponse.data);
    } catch (error: any) {
      console.error(error);

      setError(
        extractApiError(
          error,
          "Failed to load membership contribution data."
        )
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleMembershipChange = (membershipId: string) => {
    const membership = getMembership(membershipId);

    if (!membership) {
      setForm((current) => ({
        ...current,
        membership_id: "",
        amount_due: "",
        due_date: "",
      }));

      return;
    }

    const plan = getPlan(membership.plan_id);

    setForm((current) => ({
      ...current,
      membership_id: membershipId,
      amount_due: plan
        ? String(plan.monthly_contribution)
        : "",
      due_date: membership.next_due_date || "",
    }));

    setError("");
    setSuccess("");
  };

  const resetForm = () => {
    setEditingId(null);

    setForm({
      ...emptyForm,
      contribution_period: getCurrentMonthPeriod(),
    });

    setError("");
    setSuccess("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!form.membership_id) {
      setError("Please select a membership.");
      return;
    }

    if (!form.contribution_period) {
      setError("Please select a contribution period.");
      return;
    }

    if (!form.amount_due) {
      setError("Please enter the contribution amount.");
      return;
    }

    if (!form.due_date) {
      setError("Please enter a due date.");
      return;
    }

    const normalizedPeriod = normalizeContributionPeriod(
      form.contribution_period
    );

    setSaving(true);

    try {
      if (editingId) {
        const payload = {
          amount_due: Number(form.amount_due),
          due_date: form.due_date,
        };

        await api.patch(
          `/membership-contributions/${editingId}`,
          payload
        );

        setSuccess("Contribution updated successfully.");
      } else {
        const duplicate = contributions.some(
          (contribution) =>
            contribution.membership_id === form.membership_id &&
            normalizeContributionPeriod(
              contribution.contribution_period
            ) === normalizedPeriod
        );

        if (duplicate) {
          setError(
            "A contribution already exists for this membership period."
          );
          setSaving(false);
          return;
        }

        const payload = {
          membership_id: form.membership_id,
          contribution_period: normalizedPeriod,
          amount_due: Number(form.amount_due),
          due_date: form.due_date,
        };

        await api.post("/membership-contributions", payload);

        setSuccess("Contribution created successfully.");
      }

      resetForm();
      await loadData();
    } catch (error: any) {
      console.error(error);

      const statusCode = error?.response?.status;

      if (statusCode === 409) {
        setError(
          "A contribution already exists for this membership period."
        );
      } else {
        setError(
          extractApiError(
            error,
            editingId
              ? "Failed to update contribution."
              : "Failed to create contribution."
          )
        );
      }
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (contribution: Contribution) => {
    setEditingId(contribution.id);

    setForm({
      membership_id: contribution.membership_id,
      contribution_period: normalizeContributionPeriod(
        contribution.contribution_period
      ),
      amount_due: String(contribution.amount_due),
      due_date: contribution.due_date,
    });

    setError("");
    setSuccess("");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const filteredContributions = useMemo(() => {
    const query = search.trim().toLowerCase();

    return contributions.filter((contribution) => {
      const membership = getMembership(contribution.membership_id);

      if (!membership) {
        return false;
      }

      const member = getMember(membership.member_id);

      const memberName = member
        ? `${member.first_name} ${member.last_name}`
        : "";

      const matchesSearch =
        !query ||
        membership.membership_number
          .toLowerCase()
          .includes(query) ||
        memberName.toLowerCase().includes(query) ||
        contribution.contribution_period
          .toLowerCase()
          .includes(query);

      const matchesStatus =
        statusFilter === "all" ||
        contribution.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [
    contributions,
    memberships,
    members,
    search,
    statusFilter,
  ]);

  const summary = useMemo(() => {
    const total = contributions.length;

    const due = contributions.filter(
      (item) => item.status === "due"
    ).length;

    const overdue = contributions.filter(
      (item) => item.status === "overdue"
    ).length;

    const partiallyPaid = contributions.filter(
      (item) => item.status === "partially_paid"
    ).length;

    const paid = contributions.filter(
      (item) => item.status === "paid"
    ).length;

    const totalDue = contributions.reduce(
      (sum, item) => sum + Number(item.amount_due || 0),
      0
    );

    const totalPaid = contributions.reduce(
      (sum, item) => sum + Number(item.amount_paid || 0),
      0
    );

    return {
      total,
      due,
      overdue,
      partiallyPaid,
      paid,
      totalDue,
      totalPaid,
    };
  }, [contributions]);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Membership Contributions
          </h1>

          <p className="mt-1 text-sm text-gray-600">
            Manage recurring membership contribution periods and
            amounts.
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {success && (
          <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            {success}
          </div>
        )}

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          <div className="rounded-xl bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-500">
              Contributions
            </p>

            <p className="mt-2 text-2xl font-bold text-gray-900">
              {summary.total}
            </p>
          </div>

          <div className="rounded-xl bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-500">Due</p>

            <p className="mt-2 text-2xl font-bold text-blue-600">
              {summary.due}
            </p>
          </div>

          <div className="rounded-xl bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-500">
              Overdue
            </p>

            <p className="mt-2 text-2xl font-bold text-red-600">
              {summary.overdue}
            </p>
          </div>

          <div className="rounded-xl bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-500">
              Partially Paid
            </p>

            <p className="mt-2 text-2xl font-bold text-yellow-600">
              {summary.partiallyPaid}
            </p>
          </div>

          <div className="rounded-xl bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-500">
              Paid
            </p>

            <p className="mt-2 text-2xl font-bold text-green-600">
              {summary.paid}
            </p>
          </div>

          <div className="rounded-xl bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-500">
              Total Paid
            </p>

            <p className="mt-2 text-xl font-bold text-gray-900">
              {formatMoney(summary.totalPaid)}
            </p>
          </div>
        </section>

        <section className="rounded-xl bg-white p-6 shadow-sm">
          <div className="mb-5">
            <h2 className="text-lg font-semibold text-gray-900">
              {editingId
                ? "Edit Contribution"
                : "Add Contribution"}
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              Contribution status is calculated automatically from
              payments and due dates.
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="grid gap-4 md:grid-cols-2"
          >
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Membership
              </label>

              <select
                value={form.membership_id}
                onChange={(event) =>
                  handleMembershipChange(event.target.value)
                }
                disabled={Boolean(editingId) || saving}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
              >
                <option value="">
                  Select membership
                </option>

                {memberships.map((membership) => (
                  <option
                    key={membership.id}
                    value={membership.id}
                  >
                    {membership.membership_number} —{" "}
                    {getMemberNameForMembership(membership)}
                  </option>
                ))}
              </select>

              {editingId && (
                <p className="mt-1 text-xs text-gray-500">
                  Membership cannot be changed when editing.
                </p>
              )}
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Contribution Period
              </label>

              <input
                type="month"
                value={
                  form.contribution_period
                    ? form.contribution_period.slice(0, 7)
                    : ""
                }
                onChange={(event) => {
                  const value = event.target.value;

                  setForm((current) => ({
                    ...current,
                    contribution_period: value
                      ? `${value}-01`
                      : "",
                  }));
                }}
                disabled={Boolean(editingId) || saving}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
              />

              <p className="mt-1 text-xs text-gray-500">
                One contribution is allowed per membership per month.
              </p>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Amount Due
              </label>

              <input
                type="number"
                min="0"
                step="0.01"
                value={form.amount_due}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    amount_due: event.target.value,
                  }))
                }
                disabled={saving}
                placeholder="0.00"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
              />

              <p className="mt-1 text-xs text-gray-500">
                Defaults to the membership plan contribution.
              </p>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Due Date
              </label>

              <input
                type="date"
                value={form.due_date}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    due_date: event.target.value,
                  }))
                }
                disabled={saving}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
              />

              <p className="mt-1 text-xs text-gray-500">
                Defaults to the membership&apos;s next due date.
              </p>
            </div>

            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 md:col-span-2">
              <p className="text-sm font-medium text-blue-900">
                Automatic contribution status
              </p>

              <p className="mt-1 text-sm text-blue-700">
                Status is managed automatically by the payment
                engine. Payments can move a contribution from Due
                to Partially Paid or Paid, while unpaid past-due
                contributions become Overdue.
              </p>
            </div>

            <div className="flex gap-3 md:col-span-2">
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving
                  ? "Saving..."
                  : editingId
                    ? "Update Contribution"
                    : "Create Contribution"}
              </button>

              {editingId && (
                <button
                  type="button"
                  onClick={resetForm}
                  disabled={saving}
                  className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </section>

        <section className="rounded-xl bg-white p-6 shadow-sm">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                Contribution Records
              </h2>

              <p className="mt-1 text-sm text-gray-500">
                {filteredContributions.length} record
                {filteredContributions.length === 1 ? "" : "s"}
                {" "}shown
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                type="search"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Search membership or member..."
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
              />

              <select
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value)
                }
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
              >
                <option value="all">All statuses</option>
                <option value="due">Due</option>
                <option value="overdue">Overdue</option>
                <option value="partially_paid">
                  Partially Paid
                </option>
                <option value="paid">Paid</option>
                <option value="waived">Waived</option>
                <option value="refunded">Refunded</option>
              </select>
            </div>
          </div>

          {loading ? (
            <div className="py-10 text-center text-sm text-gray-500">
              Loading contributions...
            </div>
          ) : filteredContributions.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 py-10 text-center">
              <p className="text-sm font-medium text-gray-700">
                No contributions found.
              </p>

              <p className="mt-1 text-sm text-gray-500">
                Create a contribution or change your search filters.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                    <th className="px-4 py-3">
                      Membership
                    </th>

                    <th className="px-4 py-3">
                      Period
                    </th>

                    <th className="px-4 py-3">
                      Due Date
                    </th>

                    <th className="px-4 py-3">
                      Amount Due
                    </th>

                    <th className="px-4 py-3">
                      Amount Paid
                    </th>

                    <th className="px-4 py-3">
                      Balance
                    </th>

                    <th className="px-4 py-3">
                      Status
                    </th>

                    <th className="px-4 py-3 text-right">
                      Action
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {filteredContributions.map(
                    (contribution) => {
                      const membership = getMembership(
                        contribution.membership_id
                      );

                      const member = membership
                        ? getMember(membership.member_id)
                        : undefined;

                      const amountDue = Number(
                        contribution.amount_due || 0
                      );

                      const amountPaid = Number(
                        contribution.amount_paid || 0
                      );

                      const balance = Math.max(
                        amountDue - amountPaid,
                        0
                      );

                      return (
                        <tr
                          key={contribution.id}
                          className="border-b border-gray-100 last:border-0"
                        >
                          <td className="px-4 py-4">
                            <div className="font-medium text-gray-900">
                              {membership?.membership_number ||
                                "Unknown"}
                            </div>

                            <div className="text-xs text-gray-500">
                              {member
                                ? `${member.first_name} ${member.last_name}`
                                : "Unknown member"}
                            </div>
                          </td>

                          <td className="px-4 py-4 text-gray-700">
                            {formatDate(
                              contribution.contribution_period
                            )}
                          </td>

                          <td className="px-4 py-4 text-gray-700">
                            {formatDate(
                              contribution.due_date
                            )}
                          </td>

                          <td className="px-4 py-4 font-medium text-gray-900">
                            {formatMoney(amountDue)}
                          </td>

                          <td className="px-4 py-4 text-gray-700">
                            {formatMoney(amountPaid)}
                          </td>

                          <td className="px-4 py-4 font-medium text-gray-900">
                            {formatMoney(balance)}
                          </td>

                          <td className="px-4 py-4">
                            <span
                              className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusClass(
                                contribution.status
                              )}`}
                            >
                              {getStatusLabel(
                                contribution.status
                              )}
                            </span>
                          </td>

                          <td className="px-4 py-4 text-right">
                            <button
                              type="button"
                              onClick={() =>
                                handleEdit(contribution)
                              }
                              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                            >
                              Edit
                            </button>
                          </td>
                        </tr>
                      );
                    }
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}