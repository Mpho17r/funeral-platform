"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";

import api from "@/lib/api";
import MortuaryBelongingsRegister from "@/components/mortuary/MortuaryBelongingsRegister";
import { getApiErrorMessage, statusOf } from "@/lib/format";
import {
  EVENT_LABELS,
  PROCEDURES,
  RECEIVED_FROM,
  formatDateTime,
  labelOf,
  type MortuaryLocation,
  type RemainsDetail,
} from "@/lib/mortuary";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";

type Action =
  | "intake"
  | "move"
  | "prepare"
  | "identify"
  | "temperature"
  | "note"
  | "release"
  | "edit";

type Form = {
  received_from_type: string;
  received_from: string;
  collected_by_name: string;
  tag_number: string;
  location_id: string;
  handed_over_by_name: string;
  accepted_by_name: string;
  condition_notes: string;
  belongings: string;
  procedure: string;
  temperature_c: string;
  identified_by_name: string;
  identified_relationship: string;
  notes: string;
  confirm_tag_number: string;
  confirm_deceased_identifier: string;
  released_to_name: string;
  released_to_id_number: string;
  released_to_relationship: string;
  override_reason: string;
};

const emptyForm: Form = {
  received_from_type: "home",
  received_from: "",
  collected_by_name: "",
  tag_number: "",
  location_id: "",
  handed_over_by_name: "",
  accepted_by_name: "",
  condition_notes: "",
  belongings: "",
  procedure: "washed",
  temperature_c: "",
  identified_by_name: "",
  identified_relationship: "",
  notes: "",
  confirm_tag_number: "",
  confirm_deceased_identifier: "",
  released_to_name: "",
  released_to_id_number: "",
  released_to_relationship: "",
  override_reason: "",
};

const TITLES: Record<Action, string> = {
  intake: "Take into care",
  move: "Move remains",
  prepare: "Record preparation",
  identify: "Record identification",
  temperature: "Record temperature",
  note: "Add a note",
  release: "Release remains",
  edit: "Edit intake details",
};

const blank = (value: string) => value.trim() || null;

export default function RemainsPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = String(params.case_id);

  const [detail, setDetail] = useState<RemainsDetail | null>(null);
  const [locations, setLocations] = useState<MortuaryLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [action, setAction] = useState<Action | null>(null);
  const [form, setForm] = useState<Form>(emptyForm);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");

      const locationsResponse = await api
        .get<MortuaryLocation[]>("/mortuary/locations")
        .catch(() => ({ data: [] as MortuaryLocation[] }));

      setLocations(locationsResponse.data);

      try {
        const response = await api.get<RemainsDetail>(
          `/cases/${caseId}/remains`
        );

        setDetail(response.data);
      } catch (err) {
        if (statusOf(err) !== 404) {
          throw err;
        }

        setDetail(null);
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load the remains record."));
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function open(next: Action) {
    const remains = detail?.remains;

    setForm({
      ...emptyForm,
      ...(next === "edit" && remains
        ? {
            received_from_type: remains.received_from_type,
            received_from: remains.received_from ?? "",
            collected_by_name: remains.collected_by_name ?? "",
            condition_notes: remains.condition_notes ?? "",
            belongings: remains.belongings ?? "",
          }
        : {}),
    });
    setDialogError("");
    setAction(next);
  }

  function nameOf(id: string | null) {
    return locations.find((l) => l.id === id)?.name ?? "another location";
  }

  async function submit(event: FormEvent) {
    event.preventDefault();

    if (!action) {
      return;
    }

    setSaving(true);
    setDialogError("");

    const base = `/cases/${caseId}/remains`;

    try {
      if (action === "intake") {
        await api.post(base, {
          received_from_type: form.received_from_type,
          received_from: blank(form.received_from),
          collected_by_name: blank(form.collected_by_name),
          tag_number: blank(form.tag_number),
          location_id: form.location_id || null,
          condition_notes: blank(form.condition_notes),
          belongings: blank(form.belongings),
        });
      } else if (action === "edit") {
        await api.patch(base, {
          received_from_type: form.received_from_type,
          received_from: blank(form.received_from),
          collected_by_name: blank(form.collected_by_name),
          condition_notes: blank(form.condition_notes),
          belongings: blank(form.belongings),
        });
      } else if (action === "release") {
        await api.post(`${base}/release`, {
          confirm_tag_number: form.confirm_tag_number,
          confirm_deceased_identifier: form.confirm_deceased_identifier,
          released_to_name: form.released_to_name,
          released_to_id_number: form.released_to_id_number,
          released_to_relationship: blank(form.released_to_relationship),
          override_reason: blank(form.override_reason),
        });
      } else {
        await api.post(`${base}/events`, {
          event_type:
            action === "move"
              ? "moved"
              : action === "prepare"
                ? "prepared"
                : action === "identify"
                  ? "identified"
                  : action,
          to_location_id: action === "move" ? form.location_id : undefined,
          handed_over_by_name:
            action === "move" ? form.handed_over_by_name.trim() : undefined,
          accepted_by_name:
            action === "move" ? form.accepted_by_name.trim() : undefined,
          procedure: action === "prepare" ? form.procedure : undefined,
          temperature_c:
            action === "temperature" ? form.temperature_c : undefined,
          identified_by_name:
            action === "identify" ? blank(form.identified_by_name) : undefined,
          identified_relationship:
            action === "identify"
              ? blank(form.identified_relationship)
              : undefined,
          notes: blank(form.notes),
        });
      }

      setAction(null);
      setNotice(
        action === "release" ? "Remains released." : "Saved."
      );
      await load();
    } catch (err) {
      setDialogError(getApiErrorMessage(err, "Could not save this."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-slate-500">
        <Loader2 className="animate-spin" size={18} /> Loading…
      </div>
    );
  }

  const remains = detail?.remains;
  const inCustody = remains?.status === "in_custody";
  const blockers = detail?.release_blockers ?? [];
  const activeLocations = locations.filter((l) => l.is_active);

  const text = (key: keyof Form, rows = 2) => (
    <textarea
      rows={rows}
      value={form[key]}
      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      className={inputClass}
    />
  );

  const line = (key: keyof Form, required = false) => (
    <input
      required={required}
      value={form[key]}
      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      className={inputClass}
    />
  );

  const locationSelect = (required: boolean) => (
    <select
      required={required}
      value={form.location_id}
      onChange={(e) => setForm({ ...form, location_id: e.target.value })}
      className={inputClass}
    >
      <option value="">{required ? "Choose a location" : "Not placed yet"}</option>
      {activeLocations.map((l) => (
        <option key={l.id} value={l.id}>
          {l.name}
          {l.capacity !== null ? ` (${l.occupied} of ${l.capacity})` : ""}
        </option>
      ))}
    </select>
  );

  const receivedSelect = (
    <select
      value={form.received_from_type}
      onChange={(e) =>
        setForm({ ...form, received_from_type: e.target.value })
      }
      className={inputClass}
    >
      {RECEIVED_FROM.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <button
        type="button"
        onClick={() => router.push(`/cases/${caseId}`)}
        className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft size={16} /> Back to case
      </button>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Remains and custody
          </h1>
          <p className="text-sm text-slate-500">
            Who has the deceased, where, and who they are released to.
          </p>
        </div>

        {!remains && (
          <button
            type="button"
            onClick={() => open("intake")}
            className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
          >
            Take into care
          </button>
        )}
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

      {!remains && !error && (
        <p className="rounded-xl border p-6 text-sm text-slate-500">
          The deceased have not been taken into care yet.
        </p>
      )}

      {remains && detail && (
        <>
          {inCustody && detail.cooling.cooling_overdue && (
            <div
              role="alert"
              className="flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
            >
              <AlertTriangle size={16} />
              Not yet in a cold place, and more than 3 hours have passed
              since arrival.
            </div>
          )}

          <section className="rounded-xl border p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Tag number
                </p>
                <p className="text-xl font-bold text-slate-900">
                  {remains.tag_number}
                </p>
              </div>

              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  inCustody
                    ? "bg-blue-100 text-blue-700"
                    : "bg-slate-200 text-slate-700"
                }`}
              >
                {inCustody ? "In our care" : "Released"}
              </span>
            </div>

            <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
              <Item
                label="Location"
                value={
                  remains.current_location_id
                    ? nameOf(remains.current_location_id)
                    : "—"
                }
              />
              <Item
                label="Arrived"
                value={formatDateTime(remains.received_at)}
              />
              <Item
                label="Received from"
                value={`${labelOf(RECEIVED_FROM, remains.received_from_type)}${
                  remains.received_from ? `: ${remains.received_from}` : ""
                }`}
              />
              <Item label="Collected by" value={remains.collected_by_name} />
              <Item
                label="Cooled"
                value={
                  remains.cooled_at
                    ? formatDateTime(remains.cooled_at)
                    : "Not yet"
                }
              />
              <Item
                label="Identified"
                value={
                  remains.identified_at
                    ? `${remains.identified_by_name ?? ""} ${
                        remains.identified_relationship
                          ? `(${remains.identified_relationship}) `
                          : ""
                      }${formatDateTime(remains.identified_at)}`
                    : "Not yet"
                }
              />
              <Item label="Condition" value={remains.condition_notes} />
              <Item label="Belongings" value={remains.belongings} />
              {!inCustody && (
                <>
                  <Item
                    label="Released to"
                    value={`${remains.released_to_name ?? ""}${
                      remains.released_to_relationship
                        ? ` (${remains.released_to_relationship})`
                        : ""
                    }`}
                  />
                  <Item
                    label="Released"
                    value={
                      remains.released_at
                        ? formatDateTime(remains.released_at)
                        : null
                    }
                  />
                  {remains.release_override_reason && (
                    <Item
                      label="Released with paperwork missing, reason"
                      value={remains.release_override_reason}
                    />
                  )}
                </>
              )}
            </dl>

            {inCustody && (
              <div className="mt-5 flex flex-wrap gap-2">
                {(
                  [
                    ["move", "Move"],
                    ["prepare", "Preparation"],
                    ["identify", "Identify"],
                    ["temperature", "Temperature"],
                    ["note", "Add note"],
                    ["edit", "Edit details"],
                  ] as [Action, string][]
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => open(key)}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
                  >
                    {label}
                  </button>
                ))}

                <button
                  type="button"
                  onClick={() => open("release")}
                  className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                >
                  Release
                </button>
              </div>
            )}
          </section>

          {inCustody && blockers.length > 0 && (
            <section className="rounded-xl border border-amber-300 bg-amber-50 p-4">
              <p className="text-sm font-semibold text-amber-800">
                Before these remains can be released
              </p>
              <ul className="mt-2 list-disc pl-5 text-sm text-amber-800">
                {blockers.map((blocker) => (
                  <li key={blocker}>{blocker}</li>
                ))}
              </ul>
            </section>
          )}

          <MortuaryBelongingsRegister
            caseId={caseId}
            inCustody={inCustody}
          />

          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-900">
              Custody log
            </h2>

            <ol className="space-y-2">
              {[...detail.events].reverse().map((event) => (
                <li key={event.id} className="rounded-lg border p-3 text-sm">
                  <div className="flex justify-between gap-3">
                    <span className="font-medium text-slate-900">
                      {EVENT_LABELS[event.event_type] ?? event.event_type}
                      {event.procedure &&
                        `: ${labelOf(PROCEDURES, event.procedure)}`}
                      {event.temperature_c !== null &&
                        `: ${event.temperature_c}°C`}
                      {event.to_location_id &&
                        ` to ${nameOf(event.to_location_id)}`}
                    </span>
                    <span className="text-slate-500">
                      {formatDateTime(event.occurred_at)}
                    </span>
                  </div>
                  {event.event_type === "moved" && (
                    <p className="mt-1 text-slate-600">
                      Handed over by: {event.handed_over_by_name || "Not recorded"}
                      {" · "}
                      Accepted by: {event.accepted_by_name || "Not recorded"}
                    </p>
                  )}
                  {event.notes && (
                    <p className="mt-1 text-slate-600">{event.notes}</p>
                  )}
                </li>
              ))}
            </ol>
          </section>
        </>
      )}

      {action && (
        <Dialog
          title={TITLES[action]}
          onClose={() => !saving && setAction(null)}
        >
          <form onSubmit={submit} className="space-y-4">
            {dialogError && <ErrorNote message={dialogError} />}

            {(action === "intake" || action === "edit") && (
              <>
                <Field label="Received from">{receivedSelect}</Field>
                <Field label="Place or person received from">
                  {line("received_from")}
                </Field>
                <Field label="Collected by">{line("collected_by_name")}</Field>
                {action === "intake" && (
                  <>
                    <Field
                      label="Tag number"
                      hint="Leave blank to use the case number."
                    >
                      {line("tag_number")}
                    </Field>
                    <Field label="Location">{locationSelect(false)}</Field>
                  </>
                )}
                <Field label="Condition on arrival">
                  {text("condition_notes")}
                </Field>
                <Field label="Belongings received">{text("belongings")}</Field>
              </>
            )}

            {action === "move" && (
              <>
                <Field label="Move to">{locationSelect(true)}</Field>
                <Field label="Handed over by (full name)">
                  {line("handed_over_by_name", true)}
                </Field>
                <Field label="Accepted by (full name)">
                  {line("accepted_by_name", true)}
                </Field>
              </>
            )}

            {action === "prepare" && (
              <Field label="Procedure">
                <select
                  value={form.procedure}
                  onChange={(e) =>
                    setForm({ ...form, procedure: e.target.value })
                  }
                  className={inputClass}
                >
                  {PROCEDURES.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
            )}

            {action === "identify" && (
              <>
                <Field label="Identified by">
                  {line("identified_by_name", true)}
                </Field>
                <Field label="Relationship to the deceased">
                  {line("identified_relationship")}
                </Field>
              </>
            )}

            {action === "temperature" && (
              <Field label="Temperature (°C)">
                <input
                  required
                  type="number"
                  step="0.1"
                  value={form.temperature_c}
                  onChange={(e) =>
                    setForm({ ...form, temperature_c: e.target.value })
                  }
                  className={inputClass}
                />
              </Field>
            )}

            {(action === "move" ||
              action === "prepare" ||
              action === "identify" ||
              action === "temperature" ||
              action === "note") && (
              <Field label={action === "note" ? "Note" : "Notes (optional)"}>
                <textarea
                  required={action === "note"}
                  rows={2}
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  className={inputClass}
                />
              </Field>
            )}

            {action === "release" && (
              <>
                {blockers.length > 0 && (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
                    <p className="font-semibold">Outstanding</p>
                    <ul className="mt-1 list-disc pl-5">
                      {blockers.map((b) => (
                        <li key={b}>{b}</li>
                      ))}
                    </ul>
                    <p className="mt-2">
                      A manager can release anyway by giving a reason below.
                    </p>
                  </div>
                )}

                <Field
                  label="Type the tag number again"
                  hint="Read it off the tag on the body, not from this screen."
                >
                  {line("confirm_tag_number", true)}
                </Field>
                <Field
                  label="Surname or ID number on the tag"
                  hint="A second check: read it off the body's own tag or wristband."
                >
                  {line("confirm_deceased_identifier", true)}
                </Field>
                <Field label="Released to (full name)">
                  {line("released_to_name", true)}
                </Field>
                <Field
                  label="Their ID number"
                  hint="Required, so it is always clear who took the remains."
                >
                  {line("released_to_id_number", true)}
                </Field>
                <Field label="Relationship to the deceased">
                  {line("released_to_relationship")}
                </Field>

                {blockers.length > 0 && (
                  <Field label="Reason for releasing anyway (managers only)">
                    {text("override_reason")}
                  </Field>
                )}
              </>
            )}

            <DialogFooter
              onClose={() => setAction(null)}
              saving={saving}
              submitLabel={action === "release" ? "Release" : "Save"}
              danger={action === "release"}
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}

function Item({
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
      <dd className="mt-1 text-slate-900">{value?.trim() || "—"}</dd>
    </div>
  );
}
