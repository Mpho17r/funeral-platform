"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  CheckCircle2,
  Edit3,
  Plus,
  Trash2,
  X,
  XCircle,
} from "lucide-react";

import api from "@/lib/api";

type MembershipPlan = {
  id: string;
  business_id: string;
  name: string;
  description: string | null;
  monthly_contribution: string | number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type PlanForm = {
  name: string;
  description: string;
  monthly_contribution: string;
  is_active: boolean;
};

const emptyForm: PlanForm = {
  name: "",
  description: "",
  monthly_contribution: "",
  is_active: true,
};

export default function MembershipPlansPage() {
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingPlan, setEditingPlan] = useState<MembershipPlan | null>(null);
  const [form, setForm] = useState<PlanForm>(emptyForm);

  async function loadPlans() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<MembershipPlan[]>("/membership-plans");
      setPlans(response.data);
    } catch (err: any) {
      console.error("Failed to load membership plans:", err);

      if (err.response?.status === 401) {
        setError("Your session has expired. Please log in again.");
      } else {
        setError(
          err.response?.data?.detail ||
            "Unable to load membership plans."
        );
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlans();
  }, []);

  function openCreateForm() {
    setEditingPlan(null);
    setForm(emptyForm);
    setFormError("");
    setShowForm(true);
  }

  function openEditForm(plan: MembershipPlan) {
    setEditingPlan(plan);
    setForm({
      name: plan.name,
      description: plan.description || "",
      monthly_contribution: String(plan.monthly_contribution),
      is_active: plan.is_active,
    });
    setFormError("");
    setShowForm(true);
  }

  function closeForm() {
    if (saving) {
      return;
    }

    setShowForm(false);
    setEditingPlan(null);
    setForm(emptyForm);
    setFormError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setFormError("");

    const name = form.name.trim();
    const monthlyContribution = Number(form.monthly_contribution);

    if (!name) {
      setFormError("Plan name is required.");
      return;
    }

    if (
      form.monthly_contribution === "" ||
      Number.isNaN(monthlyContribution) ||
      monthlyContribution < 0
    ) {
      setFormError("Enter a valid monthly contribution.");
      return;
    }

    try {
      setSaving(true);

      const payload = {
        name,
        description: form.description.trim() || null,
        monthly_contribution: monthlyContribution,
        is_active: form.is_active,
      };

      if (editingPlan) {
        const response = await api.patch<MembershipPlan>(
          `/membership-plans/${editingPlan.id}`,
          payload
        );

        setPlans((current) =>
          current.map((plan) =>
            plan.id === editingPlan.id ? response.data : plan
          )
        );
      } else {
        const response = await api.post<MembershipPlan>(
          "/membership-plans",
          payload
        );

        setPlans((current) => [response.data, ...current]);
      }

      closeForm();
    } catch (err: any) {
      console.error("Failed to save membership plan:", err);

      if (err.response?.status === 401) {
        setFormError(
          "You are not authorized to manage membership plans. Main Admin access is required."
        );
      } else {
        setFormError(
          err.response?.data?.detail ||
            "Unable to save membership plan."
        );
      }
    } finally {
      setSaving(false);
    }
  }

  async function togglePlan(plan: MembershipPlan) {
    try {
      const response = await api.patch<MembershipPlan>(
        `/membership-plans/${plan.id}`,
        {
          is_active: !plan.is_active,
        }
      );

      setPlans((current) =>
        current.map((item) =>
          item.id === plan.id ? response.data : item
        )
      );
    } catch (err: any) {
      console.error("Failed to update plan status:", err);

      setError(
        err.response?.data?.detail ||
          "Unable to update membership plan status."
      );
    }
  }

  async function deletePlan(plan: MembershipPlan) {
    const confirmed = window.confirm(
      `Delete "${plan.name}"?\n\nThis action cannot be undone.`
    );

    if (!confirmed) {
      return;
    }

    try {
      await api.delete(`/membership-plans/${plan.id}`);

      setPlans((current) =>
        current.filter((item) => item.id !== plan.id)
      );
    } catch (err: any) {
      console.error("Failed to delete membership plan:", err);

      setError(
        err.response?.data?.detail ||
          "Unable to delete membership plan."
      );
    }
  }

  function formatCurrency(value: string | number) {
    const amount = Number(value);

    return new Intl.NumberFormat("en-ZA", {
      style: "currency",
      currency: "ZAR",
      minimumFractionDigits: 2,
    }).format(amount);
  }

  return (
    <div className="flex min-h-screen bg-slate-100">

      <main className="min-w-0 flex-1">
        <div className="border-b border-slate-200 bg-white">
          <div className="flex items-center justify-between px-6 py-5">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                Membership Plans
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                Manage funeral cover plans and monthly contribution prices.
              </p>
            </div>

            <button
              type="button"
              onClick={openCreateForm}
              className="flex items-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              <Plus size={18} />
              Add Plan
            </button>
          </div>
        </div>

        <div className="p-6">
          {error && (
            <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <XCircle size={20} className="mt-0.5 shrink-0" />
              <div className="flex-1">{error}</div>

              <button
                type="button"
                onClick={() => setError("")}
                className="text-red-500 hover:text-red-700"
              >
                <X size={18} />
              </button>
            </div>
          )}

          <div className="mb-6 grid gap-4 md:grid-cols-3">
            <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
              <p className="text-sm text-slate-500">Total Plans</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {plans.length}
              </p>
            </div>

            <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
              <p className="text-sm text-slate-500">Active Plans</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {plans.filter((plan) => plan.is_active).length}
              </p>
            </div>

            <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
              <p className="text-sm text-slate-500">Inactive Plans</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {plans.filter((plan) => !plan.is_active).length}
              </p>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl bg-white ring-1 ring-slate-200">
            <div className="border-b border-slate-200 px-6 py-4">
              <h2 className="font-semibold text-slate-900">
                Available Plans
              </h2>
            </div>

            {loading ? (
              <div className="p-10 text-center text-sm text-slate-500">
                Loading membership plans...
              </div>
            ) : plans.length === 0 ? (
              <div className="p-12 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                  <Plus size={22} className="text-slate-500" />
                </div>

                <h3 className="mt-4 font-semibold text-slate-900">
                  No membership plans yet
                </h3>

                <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
                  Create your first funeral cover plan to start assigning
                  members to a contribution structure.
                </p>

                <button
                  type="button"
                  onClick={openCreateForm}
                  className="mt-5 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
                >
                  Create First Plan
                </button>
              </div>
            ) : (
              <div className="divide-y divide-slate-200">
                {plans.map((plan) => (
                  <div
                    key={plan.id}
                    className="flex flex-col gap-4 px-6 py-5 md:flex-row md:items-center md:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="font-semibold text-slate-900">
                          {plan.name}
                        </h3>

                        {plan.is_active ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700">
                            <CheckCircle2 size={13} />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
                            <XCircle size={13} />
                            Inactive
                          </span>
                        )}
                      </div>

                      {plan.description && (
                        <p className="mt-1 text-sm text-slate-500">
                          {plan.description}
                        </p>
                      )}

                      <p className="mt-3 text-sm text-slate-500">
                        Monthly contribution
                      </p>

                      <p className="text-lg font-bold text-slate-900">
                        {formatCurrency(plan.monthly_contribution)}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => togglePlan(plan)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                      >
                        {plan.is_active ? "Deactivate" : "Activate"}
                      </button>

                      <button
                        type="button"
                        onClick={() => openEditForm(plan)}
                        className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                      >
                        <Edit3 size={16} />
                        Edit
                      </button>

                      <button
                        type="button"
                        onClick={() => deletePlan(plan)}
                        className="flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
                      >
                        <Trash2 size={16} />
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
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
                  {editingPlan
                    ? "Edit Membership Plan"
                    : "Create Membership Plan"}
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  Define the monthly contribution for this cover plan.
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

            <form onSubmit={handleSubmit} className="p-6">
              {formError && (
                <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {formError}
                </div>
              )}

              <div className="space-y-5">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">
                    Plan Name
                  </label>

                  <input
                    type="text"
                    value={form.name}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        name: event.target.value,
                      })
                    }
                    placeholder="e.g. Standard Family Cover"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                    disabled={saving}
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">
                    Description
                  </label>

                  <textarea
                    value={form.description}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        description: event.target.value,
                      })
                    }
                    placeholder="Describe what this plan covers."
                    rows={3}
                    className="w-full resize-none rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                    disabled={saving}
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">
                    Monthly Contribution
                  </label>

                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">
                      R
                    </span>

                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.monthly_contribution}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          monthly_contribution: event.target.value,
                        })
                      }
                      placeholder="0.00"
                      className="w-full rounded-lg border border-slate-300 py-2.5 pl-8 pr-3 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                      disabled={saving}
                    />
                  </div>
                </div>

                <label className="flex cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        is_active: event.target.checked,
                      })
                    }
                    className="h-4 w-4 rounded border-slate-300"
                    disabled={saving}
                  />

                  <span>
                    <span className="block text-sm font-medium text-slate-700">
                      Active plan
                    </span>
                    <span className="block text-xs text-slate-500">
                      Members can be assigned to active plans.
                    </span>
                  </span>
                </label>
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
                    : editingPlan
                      ? "Save Changes"
                      : "Create Plan"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
