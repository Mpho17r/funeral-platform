"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { formatDateTime } from "@/lib/mortuary";
import { Dialog, DialogFooter, Field, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Belonging = {
  id: string;
  description: string;
  quantity: number;
  condition: string | null;
  storage_location: string;
  received_from: string | null;
  received_by_name: string | null;
  received_at: string;
  status: string;
  returned_to_name: string | null;
  returned_at: string | null;
  transferred_to_location: string | null;
  transferred_at: string | null;
  notes: string | null;
};

type Mode = "create" | "edit" | "return" | "transfer";

type FormState = {
  description: string;
  quantity: string;
  condition: string;
  storage_location: string;
  received_from: string;
  received_by_name: string;
  notes: string;
  returned_to_name: string;
  transferred_to_location: string;
};

const emptyForm: FormState = {
  description: "",
  quantity: "1",
  condition: "",
  storage_location: "",
  received_from: "",
  received_by_name: "",
  notes: "",
  returned_to_name: "",
  transferred_to_location: "",
};

const optional = (value: string) => value.trim() || null;

const modeTitles: Record<Mode, string> = {
  create: "Register a belonging",
  edit: "Edit belonging",
  return: "Record item return",
  transfer: "Transfer item",
};

const statusLabels: Record<string, string> = {
  in_safekeeping: "In safekeeping",
  returned: "Returned",
  transferred: "Transferred",
};

export default function MortuaryBelongingsRegister({
  caseId,
  inCustody,
}: {
  caseId: string;
  inCustody: boolean;
}) {
  const [items, setItems] = useState<Belonging[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mode, setMode] = useState<Mode | null>(null);
  const [selected, setSelected] = useState<Belonging | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [dialogError, setDialogError] = useState("");

  const base = `/cases/${caseId}/remains/belongings`;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await api.get<Belonging[]>(base);
      setItems(response.data);
    } catch {
      setError("Could not load the belongings register. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    void load();
  }, [load]);

  function open(next: Mode, item?: Belonging) {
    setSelected(item ?? null);
    setDialogError("");
    setForm({
      ...emptyForm,
      ...(item
        ? {
            description: item.description,
            quantity: String(item.quantity),
            condition: item.condition ?? "",
            storage_location: item.storage_location,
            received_from: item.received_from ?? "",
            received_by_name: item.received_by_name ?? "",
            notes: item.notes ?? "",
          }
        : {}),
    });
    setMode(next);
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mode) return;

    setSaving(true);
    setDialogError("");

    try {
      if (mode === "create") {
        await api.post(base, {
          description: form.description.trim(),
          quantity: Number(form.quantity),
          condition: optional(form.condition),
          storage_location: form.storage_location.trim(),
          received_from: optional(form.received_from),
          received_by_name: optional(form.received_by_name),
          notes: optional(form.notes),
        });
      } else if (mode === "edit" && selected) {
        await api.patch(`${base}/${selected.id}`, {
          description: form.description.trim(),
          quantity: Number(form.quantity),
          condition: optional(form.condition),
          storage_location: form.storage_location.trim(),
          received_from: optional(form.received_from),
          notes: optional(form.notes),
        });
      } else if (mode === "return" && selected) {
        await api.post(`${base}/${selected.id}/return`, {
          returned_to_name: form.returned_to_name.trim(),
          notes: optional(form.notes),
        });
      } else if (mode === "transfer" && selected) {
        await api.post(`${base}/${selected.id}/transfer`, {
          transferred_to_location: form.transferred_to_location.trim(),
          notes: optional(form.notes),
        });
      }

      setMode(null);
      setSelected(null);
      setNotice(
        mode === "create"
          ? "Belonging registered."
          : mode === "edit"
            ? "Belonging updated."
            : mode === "return"
              ? "Item return recorded."
              : "Item transfer recorded."
      );
      await load();
    } catch (err: unknown) {
      const response = (
        err as { response?: { data?: { detail?: unknown } } }
      ).response;
      const detail = response?.data?.detail;
      setDialogError(
        typeof detail === "string"
          ? detail
          : "Could not save this item. Check your access and the information entered."
      );
    } finally {
      setSaving(false);
    }
  }

  const textInput = (
    key: keyof FormState,
    required = false,
    type = "text"
  ) => (
    <input
      type={type}
      required={required}
      min={type === "number" ? 1 : undefined}
      max={type === "number" ? 10000 : undefined}
      step={type === "number" ? 1 : undefined}
      value={form[key]}
      onChange={(event) => update(key, event.target.value)}
      className={inputClass}
    />
  );

  const textArea = (key: keyof FormState, rows = 2) => (
    <textarea
      rows={rows}
      value={form[key]}
      onChange={(event) => update(key, event.target.value)}
      className={inputClass}
    />
  );

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            Personal belongings register
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Record and track each item separately from the remains custody log.
          </p>
        </div>

        {inCustody && (
          <button
            type="button"
            onClick={() => open("create")}
            className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          >
            Register item
          </button>
        )}
      </div>

      {notice && (
        <div
          role="status"
          className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800"
        >
          {notice}
          <button
            type="button"
            onClick={() => setNotice("")}
            className="ml-2 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
        >
          {error}
          <button
            type="button"
            onClick={() => void load()}
            className="ml-2 underline"
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">Loading belongings…</p>
      ) : items.length === 0 ? (
        <p className="rounded-lg border border-dashed p-5 text-sm text-slate-500">
          No individual belongings have been registered for this case yet.
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const editable =
              inCustody && item.status === "in_safekeeping";

            return (
              <article
                key={item.id}
                className="rounded-lg border border-slate-200 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      {item.description}
                    </h3>
                    <p className="mt-1 text-sm text-slate-600">
                      Quantity: {item.quantity} · Storage: {item.storage_location}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                    {statusLabels[item.status] ?? item.status}
                  </span>
                </div>

                <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-xs uppercase text-slate-500">
                      Condition
                    </dt>
                    <dd className="mt-1 text-slate-800">
                      {item.condition || "Not recorded"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">
                      Received
                    </dt>
                    <dd className="mt-1 text-slate-800">
                      {formatDateTime(item.received_at)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">
                      Received from
                    </dt>
                    <dd className="mt-1 text-slate-800">
                      {item.received_from || "Not recorded"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">
                      Received by
                    </dt>
                    <dd className="mt-1 text-slate-800">
                      {item.received_by_name || "Not recorded"}
                    </dd>
                  </div>
                  {item.returned_to_name && (
                    <div>
                      <dt className="text-xs uppercase text-slate-500">
                        Returned to
                      </dt>
                      <dd className="mt-1 text-slate-800">
                        {item.returned_to_name}
                        {item.returned_at
                          ? ` · ${formatDateTime(item.returned_at)}`
                          : ""}
                      </dd>
                    </div>
                  )}
                  {item.transferred_to_location && (
                    <div>
                      <dt className="text-xs uppercase text-slate-500">
                        Transferred to
                      </dt>
                      <dd className="mt-1 text-slate-800">
                        {item.transferred_to_location}
                        {item.transferred_at
                          ? ` · ${formatDateTime(item.transferred_at)}`
                          : ""}
                      </dd>
                    </div>
                  )}
                </dl>

                {item.notes && (
                  <p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">
                    Notes: {item.notes}
                  </p>
                )}

                {editable && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => open("edit", item)}
                      className="rounded-lg border px-3 py-2 text-sm hover:bg-slate-50"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => open("transfer", item)}
                      className="rounded-lg border px-3 py-2 text-sm hover:bg-slate-50"
                    >
                      Transfer
                    </button>
                    <button
                      type="button"
                      onClick={() => open("return", item)}
                      className="rounded-lg border px-3 py-2 text-sm hover:bg-slate-50"
                    >
                      Record return
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}

      {mode && (
        <Dialog
          title={modeTitles[mode]}
          onClose={() => !saving && setMode(null)}
        >
          <form onSubmit={submit} className="space-y-4">
            {dialogError && <ErrorNote message={dialogError} />}

            {(mode === "create" || mode === "edit") && (
              <>
                <Field label="Item description">
                  {textInput("description", true)}
                </Field>
                <Field label="Quantity">
                  {textInput("quantity", true, "number")}
                </Field>
                <Field label="Condition">
                  {textArea("condition")}
                </Field>
                <Field label="Storage location">
                  {textInput("storage_location", true)}
                </Field>
                <Field label="Received from">
                  {textInput("received_from")}
                </Field>
                {mode === "create" && (
                  <Field label="Received by (full name)">
                    {textInput("received_by_name")}
                  </Field>
                )}
                <Field label="Notes">
                  {textArea("notes")}
                </Field>
              </>
            )}

            {mode === "return" && (
              <>
                <Field label="Returned to (full name)">
                  {textInput("returned_to_name", true)}
                </Field>
                <Field label="Return notes (optional)">
                  {textArea("notes")}
                </Field>
              </>
            )}

            {mode === "transfer" && (
              <>
                <Field label="Destination storage location">
                  {textInput("transferred_to_location", true)}
                </Field>
                <Field label="Transfer notes (optional)">
                  {textArea("notes")}
                </Field>
              </>
            )}

            <DialogFooter
              onClose={() => setMode(null)}
              saving={saving}
              submitLabel={
                mode === "create"
                  ? "Register item"
                  : mode === "edit"
                    ? "Save changes"
                    : mode === "return"
                      ? "Record return"
                      : "Transfer item"
              }
            />
          </form>
        </Dialog>
      )}
    </section>
  );
}
