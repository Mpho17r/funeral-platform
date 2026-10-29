
"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";

import api from "@/lib/api";

type Membership = {
  id: string;
  membership_number: string;
  member_id: string;
  plan_id: string;
  status: string;
};

type Contribution = {
  id: string;
  membership_id: string;
  contribution_period: string;
  amount_due: string;
  amount_paid: string;
  due_date: string;
  status: string;
};

type Payment = {
  id: string;
  business_id: string;
  membership_id: string;
  contribution_id: string | null;
  amount: string;
  payment_method: string;
  reference: string | null;
  payment_date: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type Member = {
  id: string;
  membership_number?: string;
  first_name?: string;
  last_name?: string;
  full_name?: string;
};

const PAYMENT_METHODS = [
  { value: "cash", label: "Cash" },
  { value: "card", label: "Card" },
  { value: "eft", label: "EFT" },
  { value: "debit_order", label: "Debit Order" },
  { value: "other", label: "Other" },
];

function formatCurrency(value: string | number) {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "ZAR",
  }).format(Number(value || 0));
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";

  return new Intl.DateTimeFormat("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function getStatusClasses(status: string) {
  switch (status) {
    case "paid":
      return "bg-emerald-100 text-emerald-700";

    case "partially_paid":
      return "bg-amber-100 text-amber-700";

    case "overdue":
      return "bg-red-100 text-red-700";

    case "waived":
      return "bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)]";

    default:
      return "bg-blue-100 text-blue-700";
  }
}

function getApiErrorDetail(error: unknown): string | undefined {
  if (error === null || typeof error !== "object") return undefined;

  const errorRecord = error as Record<string, unknown>;
  const response = errorRecord.response;
  if (response === null || typeof response !== "object") return undefined;

  const responseRecord = response as Record<string, unknown>;
  const data = responseRecord.data;
  if (data === null || typeof data !== "object") return undefined;

  const detail = (data as Record<string, unknown>).detail;
  return typeof detail === "string" ? detail : undefined;
}

export default function MembershipPaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [contributions, setContributions] = useState<Contribution[]>([]);
  const [members, setMembers] = useState<Member[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");

  const [showModal, setShowModal] = useState(false);
  const [editingPayment, setEditingPayment] =
    useState<Payment | null>(null);

  const [membershipId, setMembershipId] = useState("");
  const [contributionId, setContributionId] = useState("");
  const [amount, setAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const [paymentDate, setPaymentDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [notes, setNotes] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [
        paymentsResponse,
        membershipsResponse,
        contributionsResponse,
        membersResponse,
      ] = await Promise.all([
        api.get("/membership-payments"),
        api.get("/memberships"),
        api.get("/membership-contributions"),
        api.get("/members"),
      ]);

      setPayments(paymentsResponse.data);
      setMemberships(membershipsResponse.data);
      setContributions(contributionsResponse.data);
      setMembers(membersResponse.data);
    } catch (err: unknown) {
      console.error(err);
      setError(
        getApiErrorDetail(err) ||
          "Unable to load membership payment data.",
      );
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

  function getMemberName(membershipIdValue: string) {
    const membership = memberships.find(
      (item) => item.id === membershipIdValue,
    );

    if (!membership) return "Unknown member";

    const member = members.find(
      (item) => item.id === membership.member_id,
    );

    if (!member) return membership.membership_number;

    if (member.full_name) return member.full_name;

    const fullName = [member.first_name, member.last_name]
      .filter(Boolean)
      .join(" ");

    return fullName || membership.membership_number;
  }

  function getMembershipNumber(membershipIdValue: string) {
    return (
      memberships.find(
        (item) => item.id === membershipIdValue,
      )?.membership_number || "—"
    );
  }

  function getContribution(contributionId: string | null) {
    if (!contributionId) return null;

    return (
      contributions.find(
        (item) => item.id === contributionId,
      ) || null
    );
  }

  function resetForm() {
    setMembershipId("");
    setContributionId("");
    setAmount("");
    setPaymentMethod("cash");
    setReference("");
    setPaymentDate(new Date().toISOString().slice(0, 10));
    setNotes("");
    setEditingPayment(null);
    setError("");
  }

  function openCreateModal() {
    resetForm();
    setShowModal(true);
  }

  function openEditModal(payment: Payment) {
    setEditingPayment(payment);
    setMembershipId(payment.membership_id);
    setContributionId(payment.contribution_id || "");
    setAmount(payment.amount);
    setPaymentMethod(payment.payment_method);
    setReference(payment.reference || "");
    setPaymentDate(payment.payment_date);
    setNotes(payment.notes || "");
    setError("");
    setShowModal(true);
  }

  function closeModal() {
    if (saving) return;

    setShowModal(false);
    resetForm();
  }

  const availableContributions = useMemo(() => {
    if (!membershipId) return [];

    return contributions.filter(
      (contribution) =>
        contribution.membership_id === membershipId,
    );
  }, [membershipId, contributions]);

  function handleMembershipChange(value: string) {
    setMembershipId(value);
    setContributionId("");
    setAmount("");
  }

  function handleContributionChange(value: string) {
    setContributionId(value);

    if (!value) {
      setAmount("");
      return;
    }

    const contribution = contributions.find(
      (item) => item.id === value,
    );

    if (!contribution) return;

    const remaining =
      Number(contribution.amount_due) -
      Number(contribution.amount_paid);

    setAmount(remaining > 0 ? remaining.toFixed(2) : "");
  }

  async function handleDelete(payment: Payment) {
    const memberName = getMemberName(payment.membership_id);

    const confirmed = window.confirm(
      `Delete this payment?\n\nMember: ${memberName}\nAmount: ${formatCurrency(
        payment.amount,
      )}\nReference: ${payment.reference || "—"}\n\nThis will recalculate the linked contribution. This action cannot be undone.`,
    );

    if (!confirmed) return;

    try {
      setError("");
      setSaving(true);

      await api.delete(
        `/membership-payments/${payment.id}`,
      );

      await loadData();
    } catch (err: unknown) {
      console.error(err);

      setError(
        getApiErrorDetail(err) ||
          "Unable to delete the membership payment.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!membershipId) {
      setError("Please select a membership.");
      return;
    }

    if (!amount || Number(amount) <= 0) {
      setError("Please enter a valid payment amount.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      const payload = {
        membership_id: membershipId,
        contribution_id: contributionId || null,
        amount: Number(amount),
        payment_method: paymentMethod,
        reference: reference.trim() || null,
        payment_date: paymentDate,
        notes: notes.trim() || null,
      };

      if (editingPayment) {
        await api.patch(
          `/membership-payments/${editingPayment.id}`,
          {
            amount: Number(amount),
            payment_method: paymentMethod,
            reference: reference.trim() || null,
            payment_date: paymentDate,
            notes: notes.trim() || null,
          },
        );
      } else {
        await api.post(
          "/membership-payments",
          payload,
        );
      }

      setShowModal(false);
      resetForm();

      await loadData();
    } catch (err: unknown) {
      console.error(err);

      setError(
        getApiErrorDetail(err) ||
          "Unable to save the membership payment.",
      );
    } finally {
      setSaving(false);
    }
  }

  const filteredPayments = payments.filter((payment) => {
    const memberName = getMemberName(
      payment.membership_id,
    ).toLowerCase();

    const membershipNumber = getMembershipNumber(
      payment.membership_id,
    ).toLowerCase();

    const contribution = getContribution(
      payment.contribution_id,
    );

    const period =
      contribution?.contribution_period || "";

    const query = search.toLowerCase().trim();

    if (!query) return true;

    return (
      memberName.includes(query) ||
      membershipNumber.includes(query) ||
      payment.payment_method
        .toLowerCase()
        .includes(query) ||
      (payment.reference || "")
        .toLowerCase()
        .includes(query) ||
      period.includes(query)
    );
  });

  const totalPayments = payments.reduce(
    (sum, payment) =>
      sum + Number(payment.amount),
    0,
  );

  const currentMonth = new Date()
    .toISOString()
    .slice(0, 7);

  const monthlyPayments = payments
    .filter((payment) =>
      payment.payment_date.startsWith(
        currentMonth,
      ),
    )
    .reduce(
      (sum, payment) =>
        sum + Number(payment.amount),
      0,
    );

  const linkedPayments = payments.filter(
    (payment) => payment.contribution_id,
  ).length;

  const unallocatedPayments = payments.filter(
    (payment) => !payment.contribution_id,
  ).length;

  return (
    <main className="min-h-screen bg-[var(--fos-surface-muted)]">
      <div className="flex min-h-screen">
        <div className="min-w-0 flex-1">
          <div className="border-b border-[var(--fos-border)] bg-[var(--fos-surface)]">
            <div className="flex items-center justify-between px-6 py-5">
              <div>
                <h1 className="text-2xl font-bold text-[var(--fos-text)]">
                  Membership Payments
                </h1>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                  Record and manage member contribution payments.
                </p>
              </div>

              <button
                onClick={openCreateModal}
                className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                <Plus size={18} />
                Record Payment
              </button>
            </div>
          </div>

          <div className="p-6">
            {error && !showModal && (
              <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
                <p className="text-sm text-[var(--fos-text-muted)]">
                  Total Payments
                </p>

                <p className="mt-2 text-2xl font-bold text-[var(--fos-text)]">
                  {formatCurrency(totalPayments)}
                </p>
              </div>

              <div className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
                <p className="text-sm text-[var(--fos-text-muted)]">
                  This Month
                </p>

                <p className="mt-2 text-2xl font-bold text-[var(--fos-text)]">
                  {formatCurrency(monthlyPayments)}
                </p>
              </div>

              <div className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
                <p className="text-sm text-[var(--fos-text-muted)]">
                  Linked Payments
                </p>

                <p className="mt-2 text-2xl font-bold text-[var(--fos-text)]">
                  {linkedPayments}
                </p>
              </div>

              <div className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
                <p className="text-sm text-[var(--fos-text-muted)]">
                  Unallocated
                </p>

                <p className="mt-2 text-2xl font-bold text-[var(--fos-text)]">
                  {unallocatedPayments}
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)]">
              <div className="border-b border-[var(--fos-border)] p-4">
                <div className="relative max-w-md">
                  <Search
                    size={18}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fos-text-muted)]"
                  />

                  <input
                    value={search}
                    onChange={(event) =>
                      setSearch(event.target.value)
                    }
                    placeholder="Search payments..."
                    className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] py-2.5 pl-10 pr-4 text-sm outline-none transition focus:border-slate-500"
                  />
                </div>
              </div>

              {loading ? (
                <div className="p-8 text-center text-sm text-[var(--fos-text-muted)]">
                  Loading membership payments...
                </div>
              ) : filteredPayments.length === 0 ? (
                <div className="p-10 text-center">
                  <p className="font-medium text-[var(--fos-text-secondary)]">
                    No membership payments found.
                  </p>

                  <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                    Record a payment to see it here.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1000px] text-left">
                    <thead className="border-b border-[var(--fos-border)] bg-[var(--fos-page)]">
                      <tr>
                        <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                          Member
                        </th>

                        <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                          Contribution
                        </th>

                        <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                          Amount
                        </th>

                        <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                          Method
                        </th>

                        <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                          Reference
                        </th>

                        <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                          Date
                        </th>

                        <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                          Action
                        </th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-slate-100">
                      {filteredPayments.map((payment) => {
                        const contribution =
                          getContribution(
                            payment.contribution_id,
                          );

                        return (
                          <tr
                            key={payment.id}
                            className="transition hover:bg-[var(--fos-page)]"
                          >
                            <td className="px-5 py-4">
                              <div className="font-medium text-[var(--fos-text)]">
                                {getMemberName(
                                  payment.membership_id,
                                )}
                              </div>

                              <div className="text-xs text-[var(--fos-text-muted)]">
                                {getMembershipNumber(
                                  payment.membership_id,
                                )}
                              </div>
                            </td>

                            <td className="px-5 py-4">
                              {contribution ? (
                                <>
                                  <div className="font-medium text-[var(--fos-text)]">
                                    {formatDate(
                                      contribution.contribution_period,
                                    )}
                                  </div>

                                  <span
                                    className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${getStatusClasses(
                                      contribution.status,
                                    )}`}
                                  >
                                    {contribution.status.replace(
                                      "_",
                                      " ",
                                    )}
                                  </span>
                                </>
                              ) : (
                                <span className="text-sm text-[var(--fos-text-muted)]">
                                  Unallocated
                                </span>
                              )}
                            </td>

                            <td className="px-5 py-4 font-semibold text-[var(--fos-text)]">
                              {formatCurrency(
                                payment.amount,
                              )}
                            </td>

                            <td className="px-5 py-4 text-sm capitalize text-[var(--fos-text-secondary)]">
                              {payment.payment_method.replace(
                                "_",
                                " ",
                              )}
                            </td>

                            <td className="px-5 py-4 text-sm text-[var(--fos-text-secondary)]">
                              {payment.reference || "—"}
                            </td>

                            <td className="px-5 py-4 text-sm text-[var(--fos-text-secondary)]">
                              {formatDate(
                                payment.payment_date,
                              )}
                            </td>

                            <td className="px-5 py-4">
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() =>
                                    openEditModal(payment)
                                  }
                                  disabled={saving}
                                  className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--fos-border)] px-3 py-2 text-sm font-medium text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-surface-muted)] disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  <Pencil size={15} />
                                  Edit
                                </button>

                                <button
                                  onClick={() =>
                                    handleDelete(payment)
                                  }
                                  disabled={saving}
                                  className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  <Trash2 size={15} />
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4">
          <div className="m-auto max-h-[90dvh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-[var(--fos-surface)] shadow-xl">
            <div className="flex items-center justify-between border-b border-[var(--fos-border)] px-6 py-5">
              <div>
                <h2 className="text-xl font-bold text-[var(--fos-text)]">
                  {editingPayment
                    ? "Edit Membership Payment"
                    : "Record Membership Payment"}
                </h2>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                  {editingPayment
                    ? "Update the payment details."
                    : "Record a contribution payment for a member."}
                </p>
              </div>

              <button
                onClick={closeModal}
                className="rounded-lg p-2 text-[var(--fos-text-muted)] transition hover:bg-[var(--fos-surface-muted)]"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="p-6"
            >
              {error && (
                <div className="mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div className="grid gap-5 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Membership
                  </label>

                  <select
                    value={membershipId}
                    onChange={(event) =>
                      handleMembershipChange(
                        event.target.value,
                      )
                    }
                    disabled={!!editingPayment}
                    className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-2.5 text-sm outline-none focus:border-slate-500 disabled:bg-[var(--fos-surface-muted)]"
                  >
                    <option value="">
                      Select membership
                    </option>

                    {memberships.map(
                      (membership) => (
                        <option
                          key={membership.id}
                          value={membership.id}
                        >
                          {membership.membership_number} —{" "}
                          {getMemberName(
                            membership.id,
                          )}
                        </option>
                      ),
                    )}
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Contribution
                  </label>

                  <select
                    value={contributionId}
                    onChange={(event) =>
                      handleContributionChange(
                        event.target.value,
                      )
                    }
                    disabled={
                      !!editingPayment ||
                      !membershipId
                    }
                    className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-2.5 text-sm outline-none focus:border-slate-500 disabled:bg-[var(--fos-surface-muted)]"
                  >
                    <option value="">
                      {membershipId
                        ? "Select contribution (optional)"
                        : "Select membership first"}
                    </option>

                    {availableContributions.map(
                      (contribution) => {
                        const remaining =
                          Number(
                            contribution.amount_due,
                          ) -
                          Number(
                            contribution.amount_paid,
                          );

                        return (
                          <option
                            key={contribution.id}
                            value={contribution.id}
                          >
                            {formatDate(
                              contribution.contribution_period,
                            )}{" "}
                            — Due{" "}
                            {formatCurrency(
                              contribution.amount_due,
                            )}{" "}
                            — Remaining{" "}
                            {formatCurrency(
                              Math.max(
                                remaining,
                                0,
                              ),
                            )}
                          </option>
                        );
                      },
                    )}
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Amount
                  </label>

                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={amount}
                    onChange={(event) =>
                      setAmount(
                        event.target.value,
                      )
                    }
                    placeholder="0.00"
                    className="w-full rounded-lg border border-[var(--fos-border)] px-3 py-2.5 text-sm outline-none focus:border-slate-500"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Payment Method
                  </label>

                  <select
                    value={paymentMethod}
                    onChange={(event) =>
                      setPaymentMethod(
                        event.target.value,
                      )
                    }
                    className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-2.5 text-sm outline-none focus:border-slate-500"
                  >
                    {PAYMENT_METHODS.map(
                      (method) => (
                        <option
                          key={method.value}
                          value={method.value}
                        >
                          {method.label}
                        </option>
                      ),
                    )}
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Payment Date
                  </label>

                  <input
                    type="date"
                    value={paymentDate}
                    onChange={(event) =>
                      setPaymentDate(
                        event.target.value,
                      )
                    }
                    className="w-full rounded-lg border border-[var(--fos-border)] px-3 py-2.5 text-sm outline-none focus:border-slate-500"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Reference
                  </label>

                  <input
                    type="text"
                    value={reference}
                    onChange={(event) =>
                      setReference(
                        event.target.value,
                      )
                    }
                    placeholder="e.g. EFT-2026-001"
                    className="w-full rounded-lg border border-[var(--fos-border)] px-3 py-2.5 text-sm outline-none focus:border-slate-500"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text-secondary)]">
                    Notes
                  </label>

                  <textarea
                    value={notes}
                    onChange={(event) =>
                      setNotes(event.target.value)
                    }
                    rows={3}
                    placeholder="Optional payment notes..."
                    className="w-full rounded-lg border border-[var(--fos-border)] px-3 py-2.5 text-sm outline-none focus:border-slate-500"
                  />
                </div>
              </div>

              <div className="mt-6 flex justify-end gap-3 border-t border-[var(--fos-border)] pt-5">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={saving}
                  className="rounded-lg border border-[var(--fos-border)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)] disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving
                    ? "Saving..."
                    : editingPayment
                      ? "Save Changes"
                      : "Record Payment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

