"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Loader2,
  Mail,
  Pencil,
  Phone,
  Plus,
  Power,
  PowerOff,
  Search,
  Truck,
} from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage, statusOf } from "@/lib/format";
import type { Supplier } from "@/lib/inventory";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";

type SupplierForm = {
  name: string;
  contact_person: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
};

const emptyForm: SupplierForm = {
  name: "",
  contact_person: "",
  phone: "",
  email: "",
  address: "",
  notes: "",
};

type Dialogue =
  | { kind: "create" }
  | { kind: "edit"; supplier: Supplier }
  | { kind: "deactivate"; supplier: Supplier }
  | null;

function nullIfBlank(value: string): string | null {
  const trimmed = value.trim();

  return trimmed ? trimmed : null;
}

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<SupplierForm>(emptyForm);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await api.get<Supplier[]>("/suppliers", {
          params: { include_inactive: true },
        });

        if (!cancelled) {
          setSuppliers(response.data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            statusOf(err) === 401
              ? "Your session has expired. Please log in again."
              : getApiErrorMessage(err, "Failed to load suppliers.")
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setReloadKey((current) => current + 1);
  }

  function closeDialog() {
    setDialog(null);
    setDialogError("");
  }

  function openCreate() {
    setForm(emptyForm);
    setDialogError("");
    setDialog({ kind: "create" });
  }

  function openEdit(supplier: Supplier) {
    setForm({
      name: supplier.name,
      contact_person: supplier.contact_person ?? "",
      phone: supplier.phone ?? "",
      email: supplier.email ?? "",
      address: supplier.address ?? "",
      notes: supplier.notes ?? "",
    });
    setDialogError("");
    setDialog({ kind: "edit", supplier });
  }

  async function run(
    action: () => Promise<unknown>,
    success: string,
    fallback: string
  ) {
    setSaving(true);
    setDialogError("");

    try {
      await action();

      closeDialog();
      setNotice(success);
      reload();
    } catch (err) {
      const message = getApiErrorMessage(err, fallback);

      if (dialog) {
        setDialogError(message);
      } else {
        setError(message);
      }
    } finally {
      setSaving(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const body = {
      name: form.name.trim(),
      contact_person: nullIfBlank(form.contact_person),
      phone: nullIfBlank(form.phone),
      email: nullIfBlank(form.email),
      address: nullIfBlank(form.address),
      notes: nullIfBlank(form.notes),
    };

    if (dialog?.kind === "edit") {
      run(
        () => api.patch(`/suppliers/${dialog.supplier.id}`, body),
        `${body.name} was updated.`,
        "Could not save the supplier."
      );
    } else {
      run(
        () => api.post("/suppliers", body),
        `${body.name} was added.`,
        "Could not add the supplier."
      );
    }
  }

  const query = search.trim().toLowerCase();

  const visible = suppliers.filter((supplier) => {
    if (!showInactive && !supplier.is_active) {
      return false;
    }

    if (!query) {
      return true;
    }

    return [supplier.name, supplier.contact_person ?? ""]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });

  const inactiveCount = suppliers.filter(
    (supplier) => !supplier.is_active
  ).length;

  function set<K extends keyof SupplierForm>(
    key: K,
    value: SupplierForm[K]
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Suppliers
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            The people you buy coffins, flowers and supplies from.
          </p>
        </div>

        <button
          type="button"
          onClick={openCreate}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800"
        >
          <Plus size={18} />
          Add Supplier
        </button>
      </div>

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      {notice && (
        <Banner tone="success" onDismiss={() => setNotice("")}>
          {notice}
        </Banner>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-md">
          <Search
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search suppliers..."
            aria-label="Search suppliers"
            className="w-full rounded-lg border border-gray-300 bg-white py-3 pl-10 pr-4 text-sm outline-none focus:border-gray-500"
          />
        </div>

        {inactiveCount > 0 && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(event) =>
                setShowInactive(event.target.checked)
              }
              className="h-4 w-4 rounded border-slate-300"
            />
            Show inactive ({inactiveCount})
          </label>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-gray-500">
          <Loader2 size={18} className="animate-spin" />
          Loading suppliers…
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center">
          <Truck size={32} className="mx-auto text-gray-400" />
          <p className="mt-3 text-sm font-medium text-gray-700">
            {suppliers.length === 0
              ? "No suppliers yet. Add your first supplier."
              : "No suppliers match your search."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((supplier) => (
            <div
              key={supplier.id}
              className={`flex flex-col rounded-xl border border-gray-200 bg-white p-5 shadow-sm ${
                supplier.is_active ? "" : "opacity-70"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate font-semibold text-gray-900">
                    {supplier.name}
                  </h2>

                  {supplier.contact_person && (
                    <p className="mt-0.5 text-sm text-gray-500">
                      {supplier.contact_person}
                    </p>
                  )}
                </div>

                {!supplier.is_active && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                    Inactive
                  </span>
                )}
              </div>

              <div className="mt-4 space-y-1.5 text-sm text-gray-600">
                {supplier.phone && (
                  <p className="flex items-center gap-2">
                    <Phone size={14} className="text-gray-400" />
                    {supplier.phone}
                  </p>
                )}

                {supplier.email && (
                  <p className="flex items-center gap-2">
                    <Mail size={14} className="text-gray-400" />
                    <span className="truncate">{supplier.email}</span>
                  </p>
                )}

                {!supplier.phone && !supplier.email && (
                  <p className="text-gray-400">No contact details</p>
                )}
              </div>

              <div className="mt-5 flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => openEdit(supplier)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  <Pencil size={14} />
                  Edit
                </button>

                {supplier.is_active ? (
                  <button
                    type="button"
                    onClick={() => {
                      setDialogError("");
                      setDialog({ kind: "deactivate", supplier });
                    }}
                    className="ml-auto inline-flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-red-600 hover:text-red-700"
                  >
                    <PowerOff size={14} />
                    Deactivate
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() =>
                      run(
                        () =>
                          api.post(
                            `/suppliers/${supplier.id}/reactivate`
                          ),
                        `${supplier.name} is active again.`,
                        "Could not reactivate the supplier."
                      )
                    }
                    className="ml-auto inline-flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-emerald-700 hover:text-emerald-800"
                  >
                    <Power size={14} />
                    Reactivate
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {(dialog?.kind === "create" || dialog?.kind === "edit") && (
        <Dialog
          title={
            dialog.kind === "create" ? "Add Supplier" : "Edit Supplier"
          }
          onClose={closeDialog}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Name">
              <input
                required
                value={form.name}
                onChange={(event) => set("name", event.target.value)}
                className={inputClass}
              />
            </Field>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Contact person">
                <input
                  value={form.contact_person}
                  onChange={(event) =>
                    set("contact_person", event.target.value)
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Phone">
                <input
                  value={form.phone}
                  onChange={(event) =>
                    set("phone", event.target.value)
                  }
                  className={inputClass}
                />
              </Field>
            </div>

            <Field label="Email">
              <input
                type="email"
                value={form.email}
                onChange={(event) => set("email", event.target.value)}
                className={inputClass}
              />
            </Field>

            <Field label="Address">
              <textarea
                rows={2}
                value={form.address}
                onChange={(event) =>
                  set("address", event.target.value)
                }
                className={inputClass}
              />
            </Field>

            <Field label="Notes">
              <textarea
                rows={2}
                value={form.notes}
                onChange={(event) => set("notes", event.target.value)}
                className={inputClass}
              />
            </Field>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel={
                dialog.kind === "create" ? "Add Supplier" : "Save"
              }
            />
          </form>
        </Dialog>
      )}

      {dialog?.kind === "deactivate" && (
        <Dialog title="Deactivate supplier" onClose={closeDialog}>
          <form
            onSubmit={(event) => {
              event.preventDefault();

              run(
                () =>
                  api.post(
                    `/suppliers/${dialog.supplier.id}/deactivate`
                  ),
                `${dialog.supplier.name} was deactivated.`,
                "Could not deactivate the supplier."
              );
            }}
            className="space-y-4"
          >
            <p className="text-sm text-slate-600">
              {dialog.supplier.name} will no longer be offered when
              receiving stock. Past stock records keep their link to
              it, and you can reactivate it at any time.
            </p>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel="Deactivate"
              danger
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}
