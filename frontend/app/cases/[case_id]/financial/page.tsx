"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  ArrowLeft,
  Calculator,
  CheckCircle2,
  CreditCard,
  Loader2,
  Pencil,
  Plus,
  Receipt,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";

import { useParams, useRouter } from "next/navigation";

import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

/* ============================================================
   TYPES
============================================================ */

type Financial = {
  id: string;
  business_id: string;
  case_id: string;
  status: string;
  subtotal: number;
  discount: number;
  tax: number;
  total: number;
  amount_paid: number;
  balance: number;
  credit: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type Payment = {
  id: string;
  business_id: string;
  case_id: string;
  amount: number;
  payment_method: string;
  reference: string | null;
  payment_date: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type FinancialForm = {
  subtotal: string;
  discount: string;
  tax: string;
  notes: string;
};

type PaymentForm = {
  amount: string;
  payment_method: string;
  reference: string;
  payment_date: string;
  notes: string;
};

/* ============================================================
   API ERROR HELPER
============================================================ */

function getApiErrorMessage(
  err: any,
  fallback: string
): string {
  const detail = err?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: any) => {
        if (typeof item === "string") {
          return item;
        }

        if (item?.msg) {
          const location = Array.isArray(item.loc)
            ? item.loc.join(".")
            : "";

          return location
            ? `${location}: ${item.msg}`
            : item.msg;
        }

        return "Invalid request.";
      })
      .join(" ");
  }

  if (
    detail &&
    typeof detail === "object"
  ) {
    if (detail.msg) {
      return String(detail.msg);
    }

    return fallback;
  }

  if (typeof err?.message === "string") {
    return err.message;
  }

  return fallback;
}

/* ============================================================
   MAIN PAGE
============================================================ */

export default function FinancialPage() {
  const router = useRouter();
  const params = useParams();

  const caseId = params.case_id as string;

  const [financial, setFinancial] =
    useState<Financial | null>(null);

  const [payments, setPayments] =
    useState<Payment[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [savingFinancial, setSavingFinancial] =
    useState(false);

  const [savingPayment, setSavingPayment] =
    useState(false);

  const [recalculating, setRecalculating] =
    useState(false);

  const [deletingPayment, setDeletingPayment] =
    useState<string | null>(null);

  const [pageError, setPageError] =
    useState("");

  const [financialError, setFinancialError] =
    useState("");

  const [paymentError, setPaymentError] =
    useState("");

  const [showFinancialForm, setShowFinancialForm] =
    useState(false);

  const [showPaymentForm, setShowPaymentForm] =
    useState(false);

  const [editingPaymentId, setEditingPaymentId] =
    useState<string | null>(null);

  const [financialForm, setFinancialForm] =
    useState<FinancialForm>({
      subtotal: "0.00",
      discount: "0.00",
      tax: "0.00",
      notes: "",
    });

  const [paymentForm, setPaymentForm] =
    useState<PaymentForm>({
      amount: "",
      payment_method: "cash",
      reference: "",
      payment_date: getTodayDate(),
      notes: "",
    });

  /* ==========================================================
     AUTH + LOAD
  ========================================================== */

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    if (!caseId) {
      return;
    }

    loadFinancialData();
  }, [caseId, router]);

  async function loadFinancialData() {
    try {
      setLoading(true);
      setPageError("");

      const [financialResult, paymentsResult] =
        await Promise.allSettled([
          api.get<Financial>(
            `/cases/${caseId}/financial`
          ),
          api.get<Payment[]>(
            `/cases/${caseId}/payments`
          ),
        ]);

      if (
        financialResult.status === "fulfilled"
      ) {
        setFinancial(
          financialResult.value.data
        );

        setFinancialForm({
          subtotal: String(
            financialResult.value.data.subtotal ?? "0.00"
          ),
          discount: String(
            financialResult.value.data.discount ?? "0.00"
          ),
          tax: String(
            financialResult.value.data.tax ?? "0.00"
          ),
          notes:
            financialResult.value.data.notes || "",
        });
      } else {
        const status =
          financialResult.reason?.response?.status;

        if (status === 401) {
          router.push("/login");
          return;
        }

        if (status !== 404) {
          setPageError(
            getApiErrorMessage(
              financialResult.reason,
              "Unable to load financial information."
            )
          );
        }

        setFinancial(null);
      }

      if (
        paymentsResult.status === "fulfilled"
      ) {
        setPayments(
          paymentsResult.value.data
        );
      } else {
        const status =
          paymentsResult.reason?.response?.status;

        if (status === 401) {
          router.push("/login");
          return;
        }

        if (status !== 404) {
          setPaymentError(
            getApiErrorMessage(
              paymentsResult.reason,
              "Unable to load payments."
            )
          );
        }

        setPayments([]);
      }
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        getApiErrorMessage(
          err,
          "Unable to load financial information."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  /* ==========================================================
     CREATE FINANCIAL RECORD
  ========================================================== */

  async function handleCreateFinancial(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setSavingFinancial(true);
    setFinancialError("");

    try {
      const subtotal = Number(
        financialForm.subtotal || 0
      );

      const discount = Number(
        financialForm.discount || 0
      );

      const tax = Number(
        financialForm.tax || 0
      );

      if (subtotal < 0) {
        setFinancialError(
          "Subtotal cannot be negative."
        );
        return;
      }

      if (discount < 0) {
        setFinancialError(
          "Discount cannot be negative."
        );
        return;
      }

      if (tax < 0) {
        setFinancialError(
          "Tax cannot be negative."
        );
        return;
      }

      const response =
        await api.post<Financial>(
          `/cases/${caseId}/financial`,
          {
            subtotal: subtotal.toFixed(2),
            discount: discount.toFixed(2),
            tax: tax.toFixed(2),
            notes:
              financialForm.notes.trim() ||
              null,
          }
        );

      setFinancial(response.data);

      setFinancialForm({
        subtotal: String(
          response.data.subtotal ?? "0.00"
        ),
        discount: String(
          response.data.discount ?? "0.00"
        ),
        tax: String(
          response.data.tax ?? "0.00"
        ),
        notes:
          response.data.notes || "",
      });

      setShowFinancialForm(false);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setFinancialError(
        getApiErrorMessage(
          err,
          "Unable to create financial record."
        )
      );
    } finally {
      setSavingFinancial(false);
    }
  }

  /* ==========================================================
     UPDATE FINANCIAL RECORD
  ========================================================== */

  async function handleUpdateFinancial(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (!financial) {
      return;
    }

    setSavingFinancial(true);
    setFinancialError("");

    try {
      const subtotal = Number(
        financialForm.subtotal || 0
      );

      const discount = Number(
        financialForm.discount || 0
      );

      const tax = Number(
        financialForm.tax || 0
      );

      if (subtotal < 0) {
        setFinancialError(
          "Subtotal cannot be negative."
        );
        return;
      }

      if (discount < 0) {
        setFinancialError(
          "Discount cannot be negative."
        );
        return;
      }

      if (tax < 0) {
        setFinancialError(
          "Tax cannot be negative."
        );
        return;
      }

      const response =
        await api.patch<Financial>(
          `/cases/financial/${financial.id}`,
          {
            subtotal: subtotal.toFixed(2),
            discount: discount.toFixed(2),
            tax: tax.toFixed(2),
            notes:
              financialForm.notes.trim() ||
              null,
          }
        );

      setFinancial(response.data);

      setShowFinancialForm(false);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setFinancialError(
        getApiErrorMessage(
          err,
          "Unable to update financial record."
        )
      );
    } finally {
      setSavingFinancial(false);
    }
  }

  /* ==========================================================
     RECALCULATE FINANCIAL
  ========================================================== */

  async function handleRecalculate() {
    setRecalculating(true);
    setFinancialError("");

    try {
      const response =
        await api.post<Financial>(
          `/cases/${caseId}/financial/recalculate`
        );

      setFinancial(response.data);

      setFinancialForm({
        subtotal: String(
          response.data.subtotal ?? "0.00"
        ),
        discount: String(
          response.data.discount ?? "0.00"
        ),
        tax: String(
          response.data.tax ?? "0.00"
        ),
        notes:
          response.data.notes || "",
      });

      await loadPayments();
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setFinancialError(
        getApiErrorMessage(
          err,
          "Unable to recalculate financials."
        )
      );
    } finally {
      setRecalculating(false);
    }
  }

  /* ==========================================================
     LOAD PAYMENTS
  ========================================================== */

  async function loadPayments() {
    try {
      const response =
        await api.get<Payment[]>(
          `/cases/${caseId}/payments`
        );

      setPayments(response.data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPaymentError(
        getApiErrorMessage(
          err,
          "Unable to load payments."
        )
      );
    }
  }

  /* ==========================================================
     OPEN CREATE PAYMENT
  ========================================================== */

  function openCreatePayment() {
    setEditingPaymentId(null);

    setPaymentForm({
      amount: "",
      payment_method: "cash",
      reference: "",
      payment_date: getTodayDate(),
      notes: "",
    });

    setPaymentError("");
    setShowPaymentForm(true);
  }

  /* ==========================================================
     OPEN EDIT PAYMENT
  ========================================================== */

  function openEditPayment(
    payment: Payment
  ) {
    setEditingPaymentId(payment.id);

    setPaymentForm({
      amount: String(payment.amount ?? ""),
      payment_method:
        payment.payment_method || "cash",
      reference:
        payment.reference || "",
      payment_date:
        payment.payment_date
          ? payment.payment_date.substring(
              0,
              10
            )
          : getTodayDate(),
      notes:
        payment.notes || "",
    });

    setPaymentError("");
    setShowPaymentForm(true);
  }

  /* ==========================================================
     CREATE / UPDATE PAYMENT
  ========================================================== */

  async function handlePaymentSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setSavingPayment(true);
    setPaymentError("");

    try {
      const amount = Number(
        paymentForm.amount || 0
      );

      if (!Number.isFinite(amount)) {
        setPaymentError(
          "Please enter a valid payment amount."
        );
        return;
      }

      if (amount <= 0) {
        setPaymentError(
          "Payment amount must be greater than zero."
        );
        return;
      }

      const payload = {
        amount: amount.toFixed(2),
        payment_method:
          paymentForm.payment_method,
        reference:
          paymentForm.reference.trim() ||
          null,
        payment_date:
          paymentForm.payment_date,
        notes:
          paymentForm.notes.trim() ||
          null,
      };

      if (editingPaymentId) {
        await api.patch(
          `/cases/payments/${editingPaymentId}`,
          payload
        );
      } else {
        await api.post(
          `/cases/${caseId}/payments`,
          payload
        );
      }

      setShowPaymentForm(false);
      setEditingPaymentId(null);

      setPaymentForm({
        amount: "",
        payment_method: "cash",
        reference: "",
        payment_date: getTodayDate(),
        notes: "",
      });

      await Promise.all([
        loadPayments(),
        refreshFinancial(),
      ]);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPaymentError(
        getApiErrorMessage(
          err,
          editingPaymentId
            ? "Unable to update payment."
            : "Unable to create payment."
        )
      );
    } finally {
      setSavingPayment(false);
    }
  }

  /* ==========================================================
     REFRESH FINANCIAL
  ========================================================== */

  async function refreshFinancial() {
    try {
      const response =
        await api.get<Financial>(
          `/cases/${caseId}/financial`
        );

      setFinancial(response.data);

      setFinancialForm({
        subtotal: String(
          response.data.subtotal ?? "0.00"
        ),
        discount: String(
          response.data.discount ?? "0.00"
        ),
        tax: String(
          response.data.tax ?? "0.00"
        ),
        notes:
          response.data.notes || "",
      });
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setFinancialError(
        getApiErrorMessage(
          err,
          "Unable to refresh financial information."
        )
      );
    }
  }

  /* ==========================================================
     DELETE PAYMENT
  ========================================================== */

  async function handleDeletePayment(
    paymentId: string
  ) {
    const confirmed =
      window.confirm(
        "Are you sure you want to delete this payment? This action cannot be undone."
      );

    if (!confirmed) {
      return;
    }

    setDeletingPayment(paymentId);
    setPaymentError("");

    try {
      await api.delete(
        `/cases/payments/${paymentId}`
      );

      await Promise.all([
        loadPayments(),
        refreshFinancial(),
      ]);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPaymentError(
        getApiErrorMessage(
          err,
          "Unable to delete payment."
        )
      );
    } finally {
      setDeletingPayment(null);
    }
  }

  /* ==========================================================
     LOADING
  ========================================================== */

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Loader2
            size={20}
            className="animate-spin"
          />
          Loading financial information...
        </div>
      </main>
    );
  }

  /* ==========================================================
     PAGE
  ========================================================== */

  return (
    <main className="min-h-screen bg-slate-100">
      {/* ======================================================
          HEADER
      ====================================================== */}

      <header className="border-b bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5 md:px-8">
          <button
            onClick={() =>
              router.push(
                `/cases/${caseId}`
              )
            }
            className="mb-5 flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft size={17} />
            Back to Case
          </button>

          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
                  <CreditCard size={24} />
                </div>

                <div>
                  <h1 className="text-2xl font-bold text-slate-900">
                    Case Financials
                  </h1>

                  <p className="mt-1 text-sm text-slate-500">
                    Manage case charges, payments
                    and outstanding balances.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              {financial && (
                <button
                  onClick={
                    handleRecalculate
                  }
                  disabled={recalculating}
                  className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {recalculating ? (
                    <Loader2
                      size={16}
                      className="animate-spin"
                    />
                  ) : (
                    <RefreshCw size={16} />
                  )}

                  Recalculate
                </button>
              )}

              <button
                onClick={
                  financial
                    ? () => {
                        setFinancialError("");
                        setShowFinancialForm(
                          true
                        );
                      }
                    : () => {
                        setFinancialError("");
                        setShowFinancialForm(
                          true
                        );
                      }
                }
                className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                {financial ? (
                  <>
                    <Pencil size={16} />
                    Edit Financials
                  </>
                ) : (
                  <>
                    <Plus size={16} />
                    Create Financial Record
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ======================================================
          CONTENT
      ====================================================== */}

      <section className="mx-auto max-w-7xl space-y-6 p-6 md:p-8">
        {pageError && (
          <ErrorBox>
            {pageError}
          </ErrorBox>
        )}

        {/* ====================================================
            FINANCIAL SUMMARY
        ==================================================== */}

        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-slate-100 p-2 text-slate-700">
                <Calculator size={20} />
              </div>

              <div>
                <h2 className="font-semibold text-slate-900">
                  Financial Summary
                </h2>

                <p className="text-xs text-slate-500">
                  Current case financial position
                </p>
              </div>
            </div>

            {financial && (
              <StatusBadge
                status={financial.status}
              />
            )}
          </div>

          {!financial ? (
            <div className="mt-6 rounded-xl bg-slate-50 p-8 text-center">
              <CreditCard
                size={32}
                className="mx-auto text-slate-400"
              />

              <h3 className="mt-3 font-semibold text-slate-800">
                No financial record
              </h3>

              <p className="mt-1 text-sm text-slate-500">
                Create a financial record to
                start managing charges and
                payments for this case.
              </p>

              <button
                onClick={() =>
                  setShowFinancialForm(true)
                }
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                <Plus size={16} />
                Create Financial Record
              </button>
            </div>
          ) : (
            <>
              <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MoneyCard
                  label="Total"
                  value={financial.total}
                  icon={
                    <Receipt size={18} />
                  }
                />

                <MoneyCard
                  label="Amount Paid"
                  value={
                    financial.amount_paid
                  }
                  icon={
                    <CheckCircle2 size={18} />
                  }
                />

                <MoneyCard
                  label="Balance"
                  value={financial.balance}
                  icon={
                    <CreditCard size={18} />
                  }
                />

                <MoneyCard
                  label="Credit"
                  value={financial.credit}
                  icon={
                    <Calculator size={18} />
                  }
                />
              </div>

              <div className="mt-6 grid gap-4 border-t pt-6 md:grid-cols-4">
                <FinancialDetail
                  label="Subtotal"
                  value={financial.subtotal}
                />

                <FinancialDetail
                  label="Discount"
                  value={financial.discount}
                />

                <FinancialDetail
                  label="Tax"
                  value={financial.tax}
                />

                <FinancialDetail
                  label="Payments"
                  value={payments.reduce(
                    (total, payment) =>
                      total +
                      Number(
                        payment.amount || 0
                      ),
                    0
                  )}
                />
              </div>

              {financial.notes && (
                <div className="mt-6 border-t pt-6">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                    Financial Notes
                  </p>

                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                    {financial.notes}
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* ====================================================
            PAYMENTS
        ==================================================== */}

        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-slate-100 p-2 text-slate-700">
                <Receipt size={20} />
              </div>

              <div>
                <h2 className="font-semibold text-slate-900">
                  Payments
                </h2>

                <p className="text-xs text-slate-500">
                  Payment history for this case
                </p>
              </div>
            </div>

            <button
              onClick={openCreatePayment}
              disabled={!financial}
              className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus size={16} />
              Add Payment
            </button>
          </div>

          {paymentError && (
            <div className="mt-5">
              <ErrorBox>
                {paymentError}
              </ErrorBox>
            </div>
          )}

          {!financial ? (
            <div className="mt-6 rounded-xl bg-slate-50 p-6 text-center text-sm text-slate-500">
              Create a financial record before
              recording payments.
            </div>
          ) : payments.length === 0 ? (
            <div className="mt-6 rounded-xl bg-slate-50 p-8 text-center">
              <Receipt
                size={32}
                className="mx-auto text-slate-400"
              />

              <p className="mt-3 font-medium text-slate-700">
                No payments recorded
              </p>

              <p className="mt-1 text-sm text-slate-500">
                Add the first payment for this
                case.
              </p>
            </div>
          ) : (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[760px] text-left">
                <thead>
                  <tr className="border-b text-xs uppercase tracking-wide text-slate-400">
                    <th className="px-4 py-3 font-medium">
                      Date
                    </th>

                    <th className="px-4 py-3 font-medium">
                      Amount
                    </th>

                    <th className="px-4 py-3 font-medium">
                      Method
                    </th>

                    <th className="px-4 py-3 font-medium">
                      Reference
                    </th>

                    <th className="px-4 py-3 font-medium">
                      Notes
                    </th>

                    <th className="px-4 py-3 text-right font-medium">
                      Actions
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y">
                  {payments.map(
                    (payment) => (
                      <tr
                        key={payment.id}
                        className="hover:bg-slate-50"
                      >
                        <td className="px-4 py-4 text-sm text-slate-700">
                          {formatDate(
                            payment.payment_date
                          )}
                        </td>

                        <td className="px-4 py-4 text-sm font-semibold text-slate-900">
                          R{" "}
                          {formatMoney(
                            payment.amount
                          )}
                        </td>

                        <td className="px-4 py-4">
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium capitalize text-slate-700">
                            {formatStatus(
                              payment.payment_method
                            )}
                          </span>
                        </td>

                        <td className="px-4 py-4 text-sm text-slate-600">
                          {payment.reference ||
                            "—"}
                        </td>

                        <td className="max-w-[220px] px-4 py-4 text-sm text-slate-500">
                          <span className="block truncate">
                            {payment.notes ||
                              "—"}
                          </span>
                        </td>

                        <td className="px-4 py-4">
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() =>
                                openEditPayment(
                                  payment
                                )
                              }
                              className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                              title="Edit payment"
                            >
                              <Pencil
                                size={16}
                              />
                            </button>

                            <button
                              onClick={() =>
                                handleDeletePayment(
                                  payment.id
                                )
                              }
                              disabled={
                                deletingPayment ===
                                payment.id
                              }
                              className="rounded-lg p-2 text-red-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                              title="Delete payment"
                            >
                              {deletingPayment ===
                              payment.id ? (
                                <Loader2
                                  size={16}
                                  className="animate-spin"
                                />
                              ) : (
                                <Trash2
                                  size={16}
                                />
                              )}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {/* ======================================================
          FINANCIAL FORM MODAL
      ====================================================== */}

      {showFinancialForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between border-b bg-white px-6 py-5">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  {financial
                    ? "Edit Financial Record"
                    : "Create Financial Record"}
                </h3>

                <p className="mt-1 text-xs text-slate-500">
                  Manage charges for this funeral
                  case.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setShowFinancialForm(false)
                }
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={
                financial
                  ? handleUpdateFinancial
                  : handleCreateFinancial
              }
              className="space-y-6 p-6"
            >
              {financialError && (
                <ErrorBox>
                  {financialError}
                </ErrorBox>
              )}

              <div className="grid gap-5 md:grid-cols-3">
                <MoneyInput
                  label="Subtotal"
                  value={
                    financialForm.subtotal
                  }
                  onChange={(value) =>
                    setFinancialForm(
                      (current) => ({
                        ...current,
                        subtotal: value,
                      })
                    )
                  }
                />

                <MoneyInput
                  label="Discount"
                  value={
                    financialForm.discount
                  }
                  onChange={(value) =>
                    setFinancialForm(
                      (current) => ({
                        ...current,
                        discount: value,
                      })
                    )
                  }
                />

                <MoneyInput
                  label="Tax"
                  value={financialForm.tax}
                  onChange={(value) =>
                    setFinancialForm(
                      (current) => ({
                        ...current,
                        tax: value,
                      })
                    )
                  }
                />
              </div>

              <div className="rounded-xl bg-slate-50 p-5">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                  Estimated Total
                </p>

                <p className="mt-2 text-2xl font-bold text-slate-900">
                  R{" "}
                  {formatMoney(
                    Math.max(
                      Number(
                        financialForm.subtotal ||
                          0
                      ) -
                        Number(
                          financialForm.discount ||
                            0
                        ) +
                        Number(
                          financialForm.tax || 0
                        ),
                      0
                    )
                  )}
                </p>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Notes
                </label>

                <textarea
                  value={financialForm.notes}
                  onChange={(event) =>
                    setFinancialForm(
                      (current) => ({
                        ...current,
                        notes:
                          event.target.value,
                      })
                    )
                  }
                  rows={4}
                  placeholder="Financial notes..."
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                />
              </div>

              <div className="flex justify-end gap-3 border-t pt-5">
                <button
                  type="button"
                  onClick={() =>
                    setShowFinancialForm(false)
                  }
                  className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={
                    savingFinancial
                  }
                  className="flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {savingFinancial && (
                    <Loader2
                      size={16}
                      className="animate-spin"
                    />
                  )}

                  {savingFinancial
                    ? "Saving..."
                    : financial
                    ? "Save Changes"
                    : "Create Record"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================
          PAYMENT FORM MODAL
      ====================================================== */}

      {showPaymentForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between border-b bg-white px-6 py-5">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  {editingPaymentId
                    ? "Edit Payment"
                    : "Add Payment"}
                </h3>

                <p className="mt-1 text-xs text-slate-500">
                  Record a payment received for
                  this case.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setShowPaymentForm(false)
                }
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handlePaymentSubmit}
              className="space-y-6 p-6"
            >
              {paymentError && (
                <ErrorBox>
                  {paymentError}
                </ErrorBox>
              )}

              <div className="grid gap-5 md:grid-cols-2">
                <MoneyInput
                  label="Payment Amount"
                  value={paymentForm.amount}
                  onChange={(value) =>
                    setPaymentForm(
                      (current) => ({
                        ...current,
                        amount: value,
                      })
                    )
                  }
                  required
                />

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    Payment Method
                  </label>

                  <select
                    value={
                      paymentForm.payment_method
                    }
                    onChange={(event) =>
                      setPaymentForm(
                        (current) => ({
                          ...current,
                          payment_method:
                            event.target.value,
                        })
                      )
                    }
                    className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                  >
                    <option value="cash">
                      Cash
                    </option>

                    
                    <option value="card">
                      Card
                    </option>
                    <option value="insurance">
                      Insurance
                    </option>

                    <option value="eft">
                      EFT
                    </option>

                    
                    
                    <option value="other">
                      Other
                    </option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    Payment Date
                  </label>

                  <input
                    type="date"
                    value={
                      paymentForm.payment_date
                    }
                    onChange={(event) =>
                      setPaymentForm(
                        (current) => ({
                          ...current,
                          payment_date:
                            event.target.value,
                        })
                      )
                    }
                    required
                    className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    Reference
                  </label>

                  <input
                    type="text"
                    value={
                      paymentForm.reference
                    }
                    onChange={(event) =>
                      setPaymentForm(
                        (current) => ({
                          ...current,
                          reference:
                            event.target.value,
                        })
                      )
                    }
                    placeholder="Receipt / transaction reference"
                    className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                  />
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Notes
                </label>

                <textarea
                  value={paymentForm.notes}
                  onChange={(event) =>
                    setPaymentForm(
                      (current) => ({
                        ...current,
                        notes:
                          event.target.value,
                      })
                    )
                  }
                  rows={4}
                  placeholder="Payment notes..."
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                />
              </div>

              <div className="flex justify-end gap-3 border-t pt-5">
                <button
                  type="button"
                  onClick={() =>
                    setShowPaymentForm(false)
                  }
                  className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={savingPayment}
                  className="flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {savingPayment && (
                    <Loader2
                      size={16}
                      className="animate-spin"
                    />
                  )}

                  {savingPayment
                    ? "Saving..."
                    : editingPaymentId
                    ? "Save Payment"
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

/* ============================================================
   COMPONENTS
============================================================ */

function ErrorBox({
  children,
}: {
  children: string;
}) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {children}
    </div>
  );
}

function StatusBadge({
  status,
}: {
  status: string;
}) {
  const styles: Record<string, string> = {
    draft:
      "bg-slate-100 text-slate-700",
    unpaid:
      "bg-red-50 text-red-700",
    partially_paid:
      "bg-amber-50 text-amber-700",
    paid:
      "bg-emerald-50 text-emerald-700",
    overpaid:
      "bg-purple-50 text-purple-700",
  };

  return (
    <span
      className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
        styles[status] ||
        "bg-slate-100 text-slate-700"
      }`}
    >
      {formatStatus(status)}
    </span>
  );
}

function MoneyCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-slate-50 p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-slate-500">
          {label}
        </p>

        <div className="rounded-lg bg-white p-2 text-slate-600 shadow-sm">
          {icon}
        </div>
      </div>

      <p className="mt-3 text-xl font-bold text-slate-900">
        R {formatMoney(value)}
      </p>
    </div>
  );
}

function FinancialDetail({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-2 text-sm font-semibold text-slate-800">
        R {formatMoney(value)}
      </p>
    </div>
  );
}

function MoneyInput({
  label,
  value,
  onChange,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-700">
        {label}

        {required && (
          <span className="ml-1 text-red-500">
            *
          </span>
        )}
      </label>

      <div className="relative">
        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm text-slate-400">
          R
        </span>

        <input
          type="number"
          min="0"
          step="0.01"
          value={value}
          onChange={(event) =>
            onChange(event.target.value)
          }
          required={required}
          className="w-full rounded-lg border border-slate-300 py-3 pl-9 pr-4 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
        />
      </div>
    </div>
  );
}

/* ============================================================
   HELPERS
============================================================ */

function getTodayDate() {
  const today = new Date();

  const year =
    today.getFullYear();

  const month = String(
    today.getMonth() + 1
  ).padStart(2, "0");

  const day = String(
    today.getDate()
  ).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function formatMoney(
  value: number
) {
  return Number(
    value || 0
  ).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDate(
  value: string
) {
  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return value;
  }

  return date.toLocaleDateString(
    "en-ZA",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }
  );
}

function formatStatus(
  value: string
) {
  return value
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (letter) =>
        letter.toUpperCase()
    );
}
