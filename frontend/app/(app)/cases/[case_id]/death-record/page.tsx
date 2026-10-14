"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Circle,
  Loader2,
  MinusCircle,
  Pencil,
  Plus,
} from "lucide-react";

import api from "@/lib/api";
import { formatDate, getApiErrorMessage, statusOf } from "@/lib/format";
import {
  DISPOSALS,
  FORENSIC_STATUSES,
  ID_TYPES,
  MANNERS,
  UNNATURAL_CAUSES,
  PLACE_TYPES,
  labelFor,
  type DeathRecord,
  type Paperwork,
  type PaperworkItem,
} from "@/lib/deathRecord";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";

/* ============================================================
   FORM
============================================================ */

type RecordForm = {
  deceased_id_type: string;
  deceased_id_number: string;
  time_of_death: string;
  place_of_death_type: string;
  place_of_death: string;
  manner_of_death: string;
  unnatural_cause: string;
  cause_of_death: string;
  certifier_name: string;
  forensic_status: string;
  police_case_number: string;
  infectious_remains: boolean;
  disposal_method: string;
  informant_name: string;
  informant_relationship: string;
  informant_phone: string;
  informant_id_number: string;
  notes: string;
};

const emptyForm: RecordForm = {
  deceased_id_type: "sa_id",
  deceased_id_number: "",
  time_of_death: "",
  place_of_death_type: "",
  place_of_death: "",
  manner_of_death: "pending",
  unnatural_cause: "",
  cause_of_death: "",
  certifier_name: "",
  forensic_status: "not_applicable",
  police_case_number: "",
  infectious_remains: false,
  disposal_method: "burial",
  informant_name: "",
  informant_relationship: "",
  informant_phone: "",
  informant_id_number: "",
  notes: "",
};

function formFromRecord(record: DeathRecord): RecordForm {
  return {
    deceased_id_type: record.deceased_id_type,
    deceased_id_number: record.deceased_id_number ?? "",
    // The API sends HH:MM:SS; the time input wants HH:MM.
    time_of_death: record.time_of_death?.slice(0, 5) ?? "",
    place_of_death_type: record.place_of_death_type ?? "",
    place_of_death: record.place_of_death ?? "",
    manner_of_death: record.manner_of_death,
    unnatural_cause: record.unnatural_cause ?? "",
    cause_of_death: record.cause_of_death ?? "",
    certifier_name: record.certifier_name ?? "",
    forensic_status: record.forensic_status,
    police_case_number: record.police_case_number ?? "",
    infectious_remains: record.infectious_remains,
    disposal_method: record.disposal_method,
    informant_name: record.informant_name ?? "",
    informant_relationship: record.informant_relationship ?? "",
    informant_phone: record.informant_phone ?? "",
    informant_id_number: record.informant_id_number ?? "",
    notes: record.notes ?? "",
  };
}

/** Blank text becomes null, so a cleared field is really cleared. */
function payloadFrom(form: RecordForm) {
  const text = (value: string) => value.trim() || null;

  return {
    deceased_id_type: form.deceased_id_type,
    deceased_id_number: text(form.deceased_id_number),
    time_of_death: form.time_of_death || null,
    place_of_death_type: form.place_of_death_type || null,
    place_of_death: text(form.place_of_death),
    manner_of_death: form.manner_of_death,
    // Only an unnatural death has a cause; the API rejects one otherwise.
    unnatural_cause:
      form.manner_of_death === "unnatural"
        ? form.unnatural_cause || null
        : null,
    cause_of_death: text(form.cause_of_death),
    certifier_name: text(form.certifier_name),
    forensic_status: form.forensic_status,
    police_case_number: text(form.police_case_number),
    infectious_remains: form.infectious_remains,
    disposal_method: form.disposal_method,
    informant_name: text(form.informant_name),
    informant_relationship: text(form.informant_relationship),
    informant_phone: text(form.informant_phone),
    informant_id_number: text(form.informant_id_number),
    notes: text(form.notes),
  };
}

type Dialogue =
  | { kind: "record" }
  | { kind: "obtain"; item: PaperworkItem }
  | { kind: "custom" }
  | null;

/* ============================================================
   SMALL PIECES
============================================================ */

function Select({
  value,
  onChange,
  options,
  blank,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  blank?: string;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={inputClass}
    >
      {blank !== undefined && <option value="">{blank}</option>}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-slate-900">{value || "—"}</dd>
    </div>
  );
}

function StatusIcon({ status }: { status: PaperworkItem["status"] }) {
  if (status === "obtained") {
    return <CheckCircle2 size={20} className="text-emerald-600" />;
  }

  if (status === "not_applicable") {
    return <MinusCircle size={20} className="text-slate-400" />;
  }

  return <Circle size={20} className="text-amber-500" />;
}

const STATUS_LABEL: Record<PaperworkItem["status"], string> = {
  pending: "Outstanding",
  obtained: "Obtained",
  not_applicable: "Not needed",
};

/* ============================================================
   PAGE
============================================================ */

export default function DeathRecordPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = String(params.case_id);

  const [record, setRecord] = useState<DeathRecord | null>(null);
  const [paperwork, setPaperwork] = useState<Paperwork | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState<RecordForm>(emptyForm);
  const [reference, setReference] = useState("");
  const [obtainedOn, setObtainedOn] = useState("");
  const [itemNotes, setItemNotes] = useState("");
  const [customLabel, setCustomLabel] = useState("");
  const [customRequired, setCustomRequired] = useState(false);

  const loadPaperwork = useCallback(async () => {
    const response = await api.get<Paperwork>(
      `/cases/${caseId}/paperwork`
    );

    setPaperwork(response.data);
  }, [caseId]);

  const load = useCallback(async () => {
    try {
      setError("");

      try {
        const response = await api.get<DeathRecord>(
          `/cases/${caseId}/death-record`
        );

        setRecord(response.data);
      } catch (err) {
        // No death record yet is normal for a new case.
        if (statusOf(err) !== 404) {
          throw err;
        }

        setRecord(null);
      }

      await loadPaperwork();
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not load the death record.")
      );
    } finally {
      setLoading(false);
    }
  }, [caseId, loadPaperwork]);

  useEffect(() => {
    // The fetch is async, so state is only set after the response.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function closeDialog() {
    if (!saving) {
      setDialog(null);
      setDialogError("");
    }
  }

  function openRecord() {
    setForm(record ? formFromRecord(record) : emptyForm);
    setDialogError("");
    setDialog({ kind: "record" });
  }

  function openObtain(item: PaperworkItem) {
    setReference(item.reference_number ?? "");
    setObtainedOn(
      item.obtained_on ?? new Date().toISOString().slice(0, 10)
    );
    setItemNotes(item.notes ?? "");
    setDialogError("");
    setDialog({ kind: "obtain", item });
  }

  function openCustom() {
    setCustomLabel("");
    setCustomRequired(false);
    setDialogError("");
    setDialog({ kind: "custom" });
  }

  async function run(work: () => Promise<void>, fallback: string) {
    setSaving(true);
    setDialogError("");

    try {
      await work();

      return true;
    } catch (err) {
      setDialogError(getApiErrorMessage(err, fallback));

      return false;
    } finally {
      setSaving(false);
    }
  }

  async function saveRecord(event: FormEvent) {
    event.preventDefault();

    const ok = await run(async () => {
      const body = payloadFrom(form);

      if (record) {
        const response = await api.patch<DeathRecord>(
          `/cases/${caseId}/death-record`,
          body
        );

        setRecord(response.data);
      } else {
        const response = await api.post<DeathRecord>(
          `/cases/${caseId}/death-record`,
          body
        );

        setRecord(response.data);
      }

      // The manner of death and way of laying to rest decide which
      // papers are needed, so top up the checklist. It only adds.
      const checklist = await api.post<Paperwork>(
        `/cases/${caseId}/paperwork/standard`
      );

      setPaperwork(checklist.data);
    }, "Could not save the death details.");

    if (ok) {
      setDialog(null);
      setNotice("Death details saved.");
    }
  }

  async function updateItem(
    item: PaperworkItem,
    body: Record<string, unknown>,
    message: string
  ) {
    try {
      setError("");

      await api.patch(`/cases/${caseId}/paperwork/${item.id}`, body);
      await loadPaperwork();
      setNotice(message);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not update this item."));
    }
  }

  async function saveObtained(event: FormEvent) {
    event.preventDefault();

    if (dialog?.kind !== "obtain") {
      return;
    }

    const item = dialog.item;

    const ok = await run(async () => {
      await api.patch(`/cases/${caseId}/paperwork/${item.id}`, {
        status: "obtained",
        reference_number: reference.trim() || null,
        obtained_on: obtainedOn || null,
        notes: itemNotes.trim() || null,
      });

      await loadPaperwork();
    }, "Could not update this item.");

    if (ok) {
      setDialog(null);
      setNotice(`${item.label} marked as obtained.`);
    }
  }

  async function saveCustom(event: FormEvent) {
    event.preventDefault();

    const ok = await run(async () => {
      await api.post(`/cases/${caseId}/paperwork`, {
        label: customLabel.trim(),
        required: customRequired,
      });

      await loadPaperwork();
    }, "Could not add this item.");

    if (ok) {
      setDialog(null);
      setNotice("Item added to the checklist.");
    }
  }

  async function addStandard() {
    try {
      setError("");

      const response = await api.post<Paperwork>(
        `/cases/${caseId}/paperwork/standard`
      );

      setPaperwork(response.data);
      setNotice("Standard checklist added.");
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not add the standard checklist.")
      );
    }
  }

  /* ---------------- render ---------------- */

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 p-16 text-sm text-slate-500">
        <Loader2 size={18} className="animate-spin" />
        Loading death record…
      </div>
    );
  }

  const summary = paperwork?.summary;
  const items = paperwork?.items ?? [];

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div>
        <button
          type="button"
          onClick={() => router.push(`/cases/${caseId}`)}
          className="mb-3 inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft size={16} />
          Back to case
        </button>

        <h1 className="text-2xl font-bold text-slate-900">
          Death record and paperwork
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          The details of the death, and the papers needed before the
          funeral can go ahead.
        </p>
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

      {summary && summary.required_total > 0 && (
        <div
          className={`flex items-start gap-3 rounded-xl border p-4 ${
            summary.ready
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-amber-200 bg-amber-50 text-amber-900"
          }`}
        >
          {summary.ready ? (
            <CheckCircle2 size={20} className="mt-0.5 shrink-0" />
          ) : (
            <AlertTriangle size={20} className="mt-0.5 shrink-0" />
          )}

          <div className="text-sm">
            <p className="font-semibold">
              {summary.ready
                ? "All required paperwork is in place."
                : `${summary.required_done} of ${summary.required_total} required items done.`}
            </p>

            {!summary.ready && (
              <p className="mt-1">
                Still needed: {summary.outstanding.join(", ")}.
              </p>
            )}
          </div>
        </div>
      )}

      {/* DEATH DETAILS */}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">
            Death details
          </h2>

          <button
            type="button"
            onClick={openRecord}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            {record ? <Pencil size={14} /> : <Plus size={14} />}
            {record ? "Edit" : "Add details"}
          </button>
        </div>

        {record ? (
          <dl className="grid gap-5 px-5 py-5 sm:grid-cols-2 lg:grid-cols-3">
            <Detail
              label="Identity document"
              value={
                record.deceased_id_number
                  ? `${labelFor(ID_TYPES, record.deceased_id_type)}: ${record.deceased_id_number}`
                  : labelFor(ID_TYPES, record.deceased_id_type)
              }
            />
            <Detail
              label="Manner of death"
              value={labelFor(MANNERS, record.manner_of_death)}
            />
            {record.manner_of_death === "unnatural" && (
              <Detail
                label="Unnatural cause"
                value={labelFor(
                  UNNATURAL_CAUSES,
                  record.unnatural_cause ?? ""
                )}
              />
            )}
            <Detail
              label="Cause of death"
              value={record.cause_of_death}
            />
            <Detail
              label="Time of death"
              value={record.time_of_death?.slice(0, 5)}
            />
            <Detail
              label="Place of death"
              value={[
                labelFor(PLACE_TYPES, record.place_of_death_type),
                record.place_of_death,
              ]
                .filter((part) => part && part !== "—")
                .join(", ")}
            />
            <Detail
              label="Certified by"
              value={record.certifier_name}
            />
            <Detail
              label="Forensic status"
              value={labelFor(FORENSIC_STATUSES, record.forensic_status)}
            />
            <Detail
              label="Police case number"
              value={record.police_case_number}
            />
            <Detail
              label="Laid to rest by"
              value={labelFor(DISPOSALS, record.disposal_method)}
            />
            <Detail
              label="Informant"
              value={[
                record.informant_name,
                record.informant_relationship,
              ]
                .filter(Boolean)
                .join(" · ")}
            />
            <Detail
              label="Informant phone"
              value={record.informant_phone}
            />
            <Detail
              label="Infectious remains"
              value={record.infectious_remains ? "Yes" : "No"}
            />
          </dl>
        ) : (
          <p className="px-5 py-10 text-center text-sm text-slate-500">
            No death details have been recorded for this case yet.
          </p>
        )}
      </section>

      {/* CHECKLIST */}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">
            Paperwork checklist
          </h2>

          <button
            type="button"
            onClick={openCustom}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <Plus size={14} />
            Add item
          </button>
        </div>

        {items.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-slate-500">
              No checklist yet.{" "}
              {record
                ? "Add the standard papers for this case."
                : "Add the death details first, and the standard papers are added for you."}
            </p>

            {record && (
              <button
                type="button"
                onClick={addStandard}
                className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
              >
                Add standard checklist
              </button>
            )}
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((item) => (
              <li
                key={item.id}
                className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between"
              >
                <div className="flex items-start gap-3">
                  <StatusIcon status={item.status} />

                  <div>
                    <p className="text-sm font-medium text-slate-900">
                      {item.label}
                      {item.required && (
                        <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                          Required
                        </span>
                      )}
                    </p>

                    <p className="mt-0.5 text-xs text-slate-500">
                      {STATUS_LABEL[item.status]}
                      {item.obtained_on &&
                        ` · ${formatDate(item.obtained_on)}`}
                      {item.reference_number &&
                        ` · Ref ${item.reference_number}`}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  {item.status !== "obtained" && (
                    <button
                      type="button"
                      onClick={() => openObtain(item)}
                      className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
                    >
                      Mark obtained
                    </button>
                  )}

                  {item.status !== "not_applicable" && (
                    <button
                      type="button"
                      onClick={() =>
                        updateItem(
                          item,
                          { status: "not_applicable" },
                          `${item.label} marked as not needed.`
                        )
                      }
                      className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Not needed
                    </button>
                  )}

                  {item.status !== "pending" && (
                    <button
                      type="button"
                      onClick={() =>
                        updateItem(
                          item,
                          { status: "pending" },
                          `${item.label} is outstanding again.`
                        )
                      }
                      className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Reopen
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* DIALOGS */}

      {dialog?.kind === "record" && (
        <Dialog
          title={record ? "Edit death details" : "Add death details"}
          onClose={closeDialog}
        >
          <form onSubmit={saveRecord} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Identity document">
                <Select
                  value={form.deceased_id_type}
                  onChange={(value) =>
                    setForm({ ...form, deceased_id_type: value })
                  }
                  options={ID_TYPES}
                />
              </Field>

              <Field label="Document number">
                <input
                  value={form.deceased_id_number}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      deceased_id_number: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Manner of death">
                <Select
                  value={form.manner_of_death}
                  onChange={(value) =>
                    setForm({ ...form, manner_of_death: value })
                  }
                  options={MANNERS}
                />
              </Field>

              {form.manner_of_death === "unnatural" && (
                <Field label="Unnatural cause">
                  <Select
                    value={form.unnatural_cause}
                    onChange={(value) =>
                      setForm({ ...form, unnatural_cause: value })
                    }
                    options={UNNATURAL_CAUSES}
                  />
                </Field>
              )}

              <Field label="Forensic status">
                <Select
                  value={form.forensic_status}
                  onChange={(value) =>
                    setForm({ ...form, forensic_status: value })
                  }
                  options={FORENSIC_STATUSES}
                />
              </Field>

              <Field label="Time of death">
                <input
                  type="time"
                  value={form.time_of_death}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      time_of_death: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Place of death">
                <Select
                  value={form.place_of_death_type}
                  onChange={(value) =>
                    setForm({ ...form, place_of_death_type: value })
                  }
                  options={PLACE_TYPES}
                  blank="Not recorded"
                />
              </Field>

              <Field label="Where exactly">
                <input
                  value={form.place_of_death}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      place_of_death: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Cause of death">
                <input
                  value={form.cause_of_death}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      cause_of_death: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Certified by">
                <input
                  value={form.certifier_name}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      certifier_name: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Police case number">
                <input
                  value={form.police_case_number}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      police_case_number: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Laid to rest by">
                <Select
                  value={form.disposal_method}
                  onChange={(value) =>
                    setForm({ ...form, disposal_method: value })
                  }
                  options={DISPOSALS}
                />
              </Field>

              <label className="flex items-center gap-2 pt-7 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.infectious_remains}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      infectious_remains: event.target.checked,
                    })
                  }
                  className="h-4 w-4 rounded border-slate-300"
                />
                Infectious remains
              </label>

              <Field label="Informant name">
                <input
                  value={form.informant_name}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      informant_name: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Relationship to the deceased">
                <input
                  value={form.informant_relationship}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      informant_relationship: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Informant phone">
                <input
                  value={form.informant_phone}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      informant_phone: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Informant ID number">
                <input
                  value={form.informant_id_number}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      informant_id_number: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>
            </div>

            <Field label="Notes">
              <textarea
                rows={3}
                value={form.notes}
                onChange={(event) =>
                  setForm({ ...form, notes: event.target.value })
                }
                className={inputClass}
              />
            </Field>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel="Save details"
            />
          </form>
        </Dialog>
      )}

      {dialog?.kind === "obtain" && (
        <Dialog
          title={`Mark obtained: ${dialog.item.label}`}
          onClose={closeDialog}
        >
          <form onSubmit={saveObtained} className="space-y-4">
            <Field label="Reference number">
              <input
                value={reference}
                onChange={(event) => setReference(event.target.value)}
                className={inputClass}
              />
            </Field>

            <Field label="Date obtained">
              <input
                type="date"
                value={obtainedOn}
                onChange={(event) => setObtainedOn(event.target.value)}
                className={inputClass}
              />
            </Field>

            <Field label="Notes">
              <textarea
                rows={2}
                value={itemNotes}
                onChange={(event) => setItemNotes(event.target.value)}
                className={inputClass}
              />
            </Field>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel="Mark obtained"
            />
          </form>
        </Dialog>
      )}

      {dialog?.kind === "custom" && (
        <Dialog title="Add checklist item" onClose={closeDialog}>
          <form onSubmit={saveCustom} className="space-y-4">
            <Field label="What is needed">
              <input
                value={customLabel}
                onChange={(event) => setCustomLabel(event.target.value)}
                className={inputClass}
              />
            </Field>

            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={customRequired}
                onChange={(event) =>
                  setCustomRequired(event.target.checked)
                }
                className="h-4 w-4 rounded border-slate-300"
              />
              Required before the funeral
            </label>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel="Add item"
              disabled={!customLabel.trim()}
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}
