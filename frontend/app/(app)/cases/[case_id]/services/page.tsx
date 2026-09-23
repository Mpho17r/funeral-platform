"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  HeartHandshake,
  Loader2,
  Plus,
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

type CaseService = {
  id: string;
  business_id: string;
  case_id: string;
  service_type: string;
  service_name: string;
  description: string | null;
  status: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  scheduled_date: string | null;
  provider: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type ServiceForm = {
  service_type: string;
  service_name: string;
  description: string;
  status: string;
  quantity: string;
  unit_price: string;
  scheduled_date: string;
  provider: string;
  notes: string;
};

/* ============================================================
   HELPERS
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
          return item.msg;
        }

        return "Invalid request.";
      })
      .join(" ");
  }

  if (typeof err?.message === "string") {
    return err.message;
  }

  return fallback;
}

function formatMoney(value: number | string) {
  return Number(value || 0).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDate(value: string | null) {
  if (!value) {
    return "Not scheduled";
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

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase()
    );
}

function getStatusClass(status: string) {
  switch (status) {
    case "confirmed":
      return "bg-emerald-50 text-emerald-700";

    case "completed":
      return "bg-blue-50 text-blue-700";

    case "cancelled":
      return "bg-red-50 text-red-700";

    case "pending":
    default:
      return "bg-amber-50 text-amber-700";
  }
}

function isValidUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value
  );
}

/* ============================================================
   MAIN PAGE
============================================================ */

export default function ServicesPage() {
  const router = useRouter();
  const params = useParams();

  const caseId = String(params.case_id || "");

  const [services, setServices] = useState<CaseService[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(
    null
  );

  const [pageError, setPageError] = useState("");
  const [formError, setFormError] = useState("");

  const [showForm, setShowForm] = useState(false);

  const [form, setForm] = useState<ServiceForm>({
    service_type: "",
    service_name: "",
    description: "",
    status: "pending",
    quantity: "1",
    unit_price: "",
    scheduled_date: "",
    provider: "",
    notes: "",
  });

  /* ==========================================================
     AUTH + INITIAL LOAD
  ========================================================== */

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    if (!caseId) {
      setPageError("Case ID is missing from the URL.");
      setLoading(false);
      return;
    }

    if (!isValidUuid(caseId)) {
      setPageError(
        "Invalid case ID. Please open Services from an actual funeral case."
      );
      setLoading(false);
      return;
    }

    loadServices();
  }, [caseId, router]);

  /* ==========================================================
     LOAD SERVICES
  ========================================================== */

  async function loadServices() {
    try {
      setLoading(true);
      setPageError("");

      const response = await api.get<CaseService[]>(
        `/cases/${caseId}/services`
      );

      setServices(response.data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        getApiErrorMessage(
          err,
          "Unable to load case services."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  /* ==========================================================
     FORM HELPERS
  ========================================================== */

  function updateForm(
    field: keyof ServiceForm,
    value: string
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function resetForm() {
    setForm({
      service_type: "",
      service_name: "",
      description: "",
      status: "pending",
      quantity: "1",
      unit_price: "",
      scheduled_date: "",
      provider: "",
      notes: "",
    });

    setFormError("");
  }

  function openForm() {
    resetForm();
    setShowForm(true);
  }

  function closeForm() {
    if (saving) {
      return;
    }

    setShowForm(false);
    resetForm();
  }

  /* ==========================================================
     CREATE SERVICE
  ========================================================== */

  async function handleCreateService(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setSaving(true);
    setFormError("");

    try {
      const quantity = Number(form.quantity || 1);
      const unitPrice = Number(form.unit_price || 0);

      if (!form.service_type.trim()) {
        setFormError("Service type is required.");
        return;
      }

      if (!form.service_name.trim()) {
        setFormError("Service name is required.");
        return;
      }

      if (!Number.isInteger(quantity) || quantity < 1) {
        setFormError(
          "Quantity must be a whole number greater than 0."
        );
        return;
      }

      if (unitPrice < 0) {
        setFormError(
          "Unit price cannot be negative."
        );
        return;
      }

      const payload = {
        service_type: form.service_type.trim(),
        service_name: form.service_name.trim(),
        description:
          form.description.trim() || null,
        status: form.status,
        quantity,
        unit_price: unitPrice.toFixed(2),
        scheduled_date:
          form.scheduled_date || null,
        provider:
          form.provider.trim() || null,
        notes: form.notes.trim() || null,
      };

      await api.post<CaseService>(
        `/cases/${caseId}/services`,
        payload
      );

      setShowForm(false);
      resetForm();

      await loadServices();
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setFormError(
        getApiErrorMessage(
          err,
          "Unable to create service."
        )
      );
    } finally {
      setSaving(false);
    }
  }

  /* ==========================================================
     DELETE SERVICE
  ========================================================== */

  async function handleDeleteService(
    serviceId: string
  ) {
    const confirmed = window.confirm(
      "Are you sure you want to delete this service?"
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingId(serviceId);
      setPageError("");

      await api.delete(
        `/cases/services/${serviceId}`
      );

      setServices((current) =>
        current.filter(
          (service) => service.id !== serviceId
        )
      );
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        getApiErrorMessage(
          err,
          "Unable to delete service."
        )
      );
    } finally {
      setDeletingId(null);
    }
  }

  /* ==========================================================
     SUMMARY CALCULATIONS
  ========================================================== */

  const summary = useMemo(() => {
    const total = services.length;

    const pending = services.filter(
      (service) => service.status === "pending"
    ).length;

    const confirmed = services.filter(
      (service) => service.status === "confirmed"
    ).length;

    const completed = services.filter(
      (service) => service.status === "completed"
    ).length;

    const value = services.reduce(
      (sum, service) =>
        sum + Number(service.total_price || 0),
      0
    );

    return {
      total,
      pending,
      confirmed,
      completed,
      value,
    };
  }, [services]);

  /* ==========================================================
     LOADING STATE
  ========================================================== */

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Loader2
            size={20}
            className="animate-spin"
          />
          Loading services...
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
            type="button"
            onClick={() =>
              router.push(`/cases/${caseId}`)
            }
            className="mb-5 flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft size={17} />
            Back to Case
          </button>

          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-slate-900 p-3 text-white">
                  <HeartHandshake size={22} />
                </div>

                <div>
                  <h1 className="text-2xl font-bold text-slate-900">
                    Services
                  </h1>

                  <p className="mt-1 text-sm text-slate-500">
                    Manage services and arrangements for
                    this funeral case.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={loadServices}
                className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <RefreshCw size={16} />
                Refresh
              </button>

              <button
                type="button"
                onClick={openForm}
                className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                <Plus size={17} />
                Add Service
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ======================================================
          CONTENT
      ====================================================== */}

      <section className="mx-auto max-w-7xl p-6 md:p-8">
        {/* PAGE ERROR */}

        {pageError && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-700">
              {pageError}
            </p>
          </div>
        )}

        {/* SUMMARY CARDS */}

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <SummaryCard
            title="Total Services"
            value={summary.total}
            description="Services on this case"
            icon={<HeartHandshake size={20} />}
          />

          <SummaryCard
            title="Pending"
            value={summary.pending}
            description="Awaiting confirmation"
            icon={<Loader2 size={20} />}
          />

          <SummaryCard
            title="Confirmed"
            value={summary.confirmed}
            description="Confirmed services"
            icon={<CheckCircle2 size={20} />}
          />

          <SummaryCard
            title="Service Value"
            value={`R ${formatMoney(summary.value)}`}
            description="Total service value"
            icon={<HeartHandshake size={20} />}
          />
        </div>

        {/* SERVICES CARD */}

        <div className="mt-8 rounded-2xl border bg-white shadow-sm">
          <div className="border-b px-6 py-5">
            <h2 className="text-lg font-bold text-slate-900">
              Case Services
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Services and arrangements associated with
              this case.
            </p>
          </div>

          {services.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-500">
                <HeartHandshake size={25} />
              </div>

              <h3 className="mt-5 text-base font-semibold text-slate-900">
                No services yet
              </h3>

              <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                Add the funeral services and arrangements
                required for this case.
              </p>

              <button
                type="button"
                onClick={openForm}
                className="mt-6 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                <Plus size={17} />
                Add First Service
              </button>
            </div>
          ) : (
            <div className="divide-y">
              {services.map((service) => (
                <div
                  key={service.id}
                  className="p-6"
                >
                  <div className="flex flex-col justify-between gap-5 lg:flex-row">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="text-base font-bold text-slate-900">
                          {service.service_name}
                        </h3>

                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                          {formatStatus(
                            service.service_type
                          )}
                        </span>

                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${getStatusClass(
                            service.status
                          )}`}
                        >
                          {formatStatus(
                            service.status
                          )}
                        </span>
                      </div>

                      {service.description && (
                        <p className="mt-3 text-sm text-slate-600">
                          {service.description}
                        </p>
                      )}

                      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <InfoItem
                          label="Quantity"
                          value={String(
                            service.quantity
                          )}
                        />

                        <InfoItem
                          label="Unit Price"
                          value={`R ${formatMoney(
                            service.unit_price
                          )}`}
                        />

                        <InfoItem
                          label="Total"
                          value={`R ${formatMoney(
                            service.total_price
                          )}`}
                        />

                        <InfoItem
                          label="Scheduled"
                          value={formatDate(
                            service.scheduled_date
                          )}
                        />
                      </div>

                      {service.provider && (
                        <div className="mt-4">
                          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                            Provider
                          </p>

                          <p className="mt-1 text-sm font-medium text-slate-700">
                            {service.provider}
                          </p>
                        </div>
                      )}

                      {service.notes && (
                        <div className="mt-4 rounded-lg bg-slate-50 p-4">
                          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                            Notes
                          </p>

                          <p className="mt-1 text-sm text-slate-600">
                            {service.notes}
                          </p>
                        </div>
                      )}
                    </div>

                    <div className="flex items-start">
                      <button
                        type="button"
                        disabled={
                          deletingId === service.id
                        }
                        onClick={() =>
                          handleDeleteService(
                            service.id
                          )
                        }
                        className="flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {deletingId === service.id ? (
                          <Loader2
                            size={15}
                            className="animate-spin"
                          />
                        ) : (
                          <Trash2 size={15} />
                        )}

                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ======================================================
          ADD SERVICE MODAL
      ====================================================== */}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b px-6 py-5">
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  Add Service
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  Add a service or arrangement to this
                  funeral case.
                </p>
              </div>

              <button
                type="button"
                onClick={closeForm}
                disabled={saving}
                className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-50"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleCreateService}
              className="space-y-6 p-6"
            >
              {formError && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                  <p className="text-sm font-medium text-red-700">
                    {formError}
                  </p>
                </div>
              )}

              <div className="grid gap-5 md:grid-cols-2">
                <FormField
                  label="Service Type"
                  value={form.service_type}
                  onChange={(value) =>
                    updateForm(
                      "service_type",
                      value
                    )
                  }
                  placeholder="e.g. Transport"
                  required
                />

                <FormField
                  label="Service Name"
                  value={form.service_name}
                  onChange={(value) =>
                    updateForm(
                      "service_name",
                      value
                    )
                  }
                  placeholder="e.g. Hearse"
                  required
                />

                <FormSelect
                  label="Status"
                  value={form.status}
                  onChange={(value) =>
                    updateForm(
                      "status",
                      value
                    )
                  }
                  options={[
                    {
                      value: "pending",
                      label: "Pending",
                    },
                    {
                      value: "confirmed",
                      label: "Confirmed",
                    },
                    {
                      value: "completed",
                      label: "Completed",
                    },
                    {
                      value: "cancelled",
                      label: "Cancelled",
                    },
                  ]}
                />

                <FormField
                  label="Quantity"
                  type="number"
                  min="1"
                  value={form.quantity}
                  onChange={(value) =>
                    updateForm(
                      "quantity",
                      value
                    )
                  }
                  required
                />

                <FormField
                  label="Unit Price"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.unit_price}
                  onChange={(value) =>
                    updateForm(
                      "unit_price",
                      value
                    )
                  }
                  placeholder="0.00"
                />

                <FormField
                  label="Scheduled Date"
                  type="date"
                  value={form.scheduled_date}
                  onChange={(value) =>
                    updateForm(
                      "scheduled_date",
                      value
                    )
                  }
                />

                <FormField
                  label="Provider"
                  value={form.provider}
                  onChange={(value) =>
                    updateForm(
                      "provider",
                      value
                    )
                  }
                  placeholder="e.g. Makhado Transport"
                />
              </div>

              <TextAreaField
                label="Description"
                value={form.description}
                onChange={(value) =>
                  updateForm(
                    "description",
                    value
                  )
                }
                placeholder="Describe the service..."
              />

              <TextAreaField
                label="Notes"
                value={form.notes}
                onChange={(value) =>
                  updateForm(
                    "notes",
                    value
                  )
                }
                placeholder="Additional notes..."
              />

              <div className="flex justify-end gap-3 border-t pt-5">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={saving}
                  className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving && (
                    <Loader2
                      size={16}
                      className="animate-spin"
                    />
                  )}

                  {saving
                    ? "Saving..."
                    : "Save Service"}
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
   SUMMARY CARD
============================================================ */

function SummaryCard({
  icon,
  title,
  value,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  value: string | number;
  description: string;
}) {
  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500">
          {title}
        </p>

        <div className="rounded-lg bg-slate-100 p-2 text-slate-700">
          {icon}
        </div>
      </div>

      <p className="mt-4 text-2xl font-bold text-slate-900">
        {value}
      </p>

      <p className="mt-1 text-xs text-slate-500">
        {description}
      </p>
    </div>
  );
}

/* ============================================================
   INFO ITEM
============================================================ */

function InfoItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-slate-800">
        {value}
      </p>
    </div>
  );
}

/* ============================================================
   FORM FIELD
============================================================ */

function FormField({
  label,
  value,
  onChange,
  placeholder,
  required = false,
  type = "text",
  min,
  step,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  type?: "text" | "number" | "date";
  min?: string;
  step?: string;
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

      <input
        type={type}
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
        placeholder={placeholder}
        required={required}
        min={min}
        step={step}
        className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
      />
    </div>
  );
}

/* ============================================================
   SELECT
============================================================ */

function FormSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: {
    value: string;
    label: string;
  }[];
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </label>

      <select
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
        className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
      >
        {options.map((option) => (
          <option
            key={option.value}
            value={option.value}
          >
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/* ============================================================
   TEXTAREA
============================================================ */

function TextAreaField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </label>

      <textarea
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
        placeholder={placeholder}
        rows={4}
        className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
      />
    </div>
  );
}
