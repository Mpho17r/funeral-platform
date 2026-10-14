"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Plus, Truck } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage, statusOf } from "@/lib/format";
import { isoToLocalInput, localInputToIso } from "@/lib/datetime";
import {
  ARRANGEMENT_STATUS,
  COLLECTION_STATUS,
  PICKUP_TYPES,
  VENUE_TYPES,
  dateTimeInSouthAfrica,
  labelOf,
  type Arrangement,
  type Collection,
  type DriverOption,
  type VehicleOption,
} from "@/lib/arrangements";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";

type PlanForm = {
  wake_at: string;
  wake_venue: string;
  wake_address: string;
  service_at: string;
  service_venue_type: string;
  service_venue: string;
  service_address: string;
  officiant: string;
  departure_at: string;
  departure_point: string;
  committal_at: string;
  committal_place: string;
  committal_section: string;
  grave_number: string;
  grave_confirmed: boolean;
  notes: string;
};

const emptyPlan: PlanForm = {
  wake_at: "",
  wake_venue: "",
  wake_address: "",
  service_at: "",
  service_venue_type: "",
  service_venue: "",
  service_address: "",
  officiant: "",
  departure_at: "",
  departure_point: "",
  committal_at: "",
  committal_place: "",
  committal_section: "",
  grave_number: "",
  grave_confirmed: false,
  notes: "",
};

type CollectionForm = {
  scheduled_at: string;
  pickup_type: string;
  pickup_address: string;
  pickup_contact_name: string;
  pickup_contact_phone: string;
  vehicle_resource_id: string;
  driver_user_id: string;
  notes: string;
};

const emptyCollection: CollectionForm = {
  scheduled_at: "",
  pickup_type: "home",
  pickup_address: "",
  pickup_contact_name: "",
  pickup_contact_phone: "",
  vehicle_resource_id: "",
  driver_user_id: "",
  notes: "",
};

type Dialogue =
  | { kind: "plan" }
  | {
      kind: "arrangement-move";
      target: "confirmed" | "completed" | "cancelled" | "draft";
    }
  | { kind: "collection"; collection: Collection | null }
  | {
      kind: "collection-move";
      collection: Collection;
      target: "collected" | "cancelled";
    }
  | null;

const blank = (value: string) => value.trim() || null;

function planFromArrangement(a: Arrangement): PlanForm {
  const local = (value: string | null) =>
    value ? isoToLocalInput(value) : "";

  return {
    wake_at: local(a.wake_at),
    wake_venue: a.wake_venue ?? "",
    wake_address: a.wake_address ?? "",
    service_at: local(a.service_at),
    service_venue_type: a.service_venue_type ?? "",
    service_venue: a.service_venue ?? "",
    service_address: a.service_address ?? "",
    officiant: a.officiant ?? "",
    departure_at: local(a.departure_at),
    departure_point: a.departure_point ?? "",
    committal_at: local(a.committal_at),
    committal_place: a.committal_place ?? "",
    committal_section: a.committal_section ?? "",
    grave_number: a.grave_number ?? "",
    grave_confirmed: a.grave_confirmed,
    notes: a.notes ?? "",
  };
}

export default function ArrangementPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = String(params.case_id);

  const [arrangement, setArrangement] = useState<Arrangement | null>(null);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [vehicles, setVehicles] = useState<VehicleOption[]>([]);
  const [drivers, setDrivers] = useState<DriverOption[] | null>(null);
  const [caseLabel, setCaseLabel] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [plan, setPlan] = useState<PlanForm>(emptyPlan);
  const [collectionForm, setCollectionForm] =
    useState<CollectionForm>(emptyCollection);
  const [reason, setReason] = useState("");
  const [collectedAt, setCollectedAt] = useState("");
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");

      const [caseResponse, collectionsResponse] = await Promise.all([
        api.get<{ case_number: string; deceased_full_name: string }>(
          `/cases/${caseId}`
        ),
        api
          .get<Collection[]>(`/cases/${caseId}/collections`)
          .catch(() => ({ data: [] as Collection[] })),
      ]);

      setCaseLabel(
        `${caseResponse.data.deceased_full_name} · ${caseResponse.data.case_number}`
      );
      setCollections(collectionsResponse.data);

      try {
        const response = await api.get<Arrangement>(
          `/cases/${caseId}/arrangement`
        );

        setArrangement(response.data);
      } catch (err) {
        if (statusOf(err) !== 404) {
          throw err;
        }

        setArrangement(null);
      }

      const [resourcesResponse, usersResponse] = await Promise.all([
        api
          .get<
            {
              id: string;
              name: string;
              resource_type: string;
              is_active: boolean;
            }[]
          >("/resources")
          .catch(() => ({ data: [] })),
        api
          .get<{ id: string; full_name: string; is_active: boolean }[]>(
            "/users"
          )
          .catch(() => null),
      ]);

      setVehicles(
        resourcesResponse.data
          .filter((r) => r.resource_type === "vehicle" && r.is_active)
          .map((r) => ({ id: r.id, name: r.name }))
      );
      setDrivers(
        usersResponse
          ? usersResponse.data
              .filter((u) => u.is_active)
              .map((u) => ({ id: u.id, full_name: u.full_name }))
          : null
      );
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load the arrangements."));
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function closeDialog() {
    setDialog(null);
    setDialogError("");
    setReason("");
    setCollectedAt("");
  }

  function openPlan() {
    setPlan(arrangement ? planFromArrangement(arrangement) : emptyPlan);
    setDialogError("");
    setDialog({ kind: "plan" });
  }

  function openCollection(collection: Collection | null) {
    setCollectionForm(
      collection
        ? {
            scheduled_at: isoToLocalInput(collection.scheduled_at),
            pickup_type: collection.pickup_type,
            pickup_address: collection.pickup_address ?? "",
            pickup_contact_name: collection.pickup_contact_name ?? "",
            pickup_contact_phone: collection.pickup_contact_phone ?? "",
            vehicle_resource_id: collection.vehicle_resource_id ?? "",
            driver_user_id: collection.driver_user_id ?? "",
            notes: collection.notes ?? "",
          }
        : emptyCollection
    );
    setDialogError("");
    setDialog({ kind: "collection", collection });
  }

  async function run(work: () => Promise<void>, fallback: string) {
    setSaving(true);
    setDialogError("");

    try {
      await work();
      closeDialog();
      await load();
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

  async function savePlan(event: FormEvent) {
    event.preventDefault();

    const body = {
      wake_at: localInputToIso(plan.wake_at),
      wake_venue: blank(plan.wake_venue),
      wake_address: blank(plan.wake_address),
      service_at: localInputToIso(plan.service_at),
      service_venue_type: plan.service_venue_type || null,
      service_venue: blank(plan.service_venue),
      service_address: blank(plan.service_address),
      officiant: blank(plan.officiant),
      departure_at: localInputToIso(plan.departure_at),
      departure_point: blank(plan.departure_point),
      committal_at: localInputToIso(plan.committal_at),
      committal_place: blank(plan.committal_place),
      committal_section: blank(plan.committal_section),
      grave_number: blank(plan.grave_number),
      grave_confirmed: plan.grave_confirmed,
      notes: blank(plan.notes),
    };

    await run(async () => {
      if (arrangement) {
        await api.patch(`/cases/${caseId}/arrangement`, body);
        setNotice("Arrangements updated.");
      } else {
        await api.post(`/cases/${caseId}/arrangement`, body);
        setNotice("Arrangements saved as a draft.");
      }
    }, "Could not save the arrangements.");
  }

  async function moveArrangement(event: FormEvent) {
    event.preventDefault();

    if (dialog?.kind !== "arrangement-move") {
      return;
    }

    const target = dialog.target;

    await run(async () => {
      await api.post(`/cases/${caseId}/arrangement/transition`, {
        status: target,
        reason: blank(reason),
      });
      setNotice(
        {
          confirmed: "Arrangements confirmed.",
          completed: "Funeral marked as completed.",
          cancelled: "Arrangements cancelled.",
          draft: "Arrangements moved back to draft.",
        }[target]
      );
    }, "Could not change the status.");
  }

  async function saveCollection(event: FormEvent) {
    event.preventDefault();

    if (dialog?.kind !== "collection") {
      return;
    }

    const scheduled = localInputToIso(collectionForm.scheduled_at);

    if (!scheduled) {
      setDialogError("Choose when the collection should happen.");

      return;
    }

    const existing = dialog.collection;
    const body = {
      scheduled_at: scheduled,
      pickup_type: collectionForm.pickup_type,
      pickup_address: blank(collectionForm.pickup_address),
      pickup_contact_name: blank(collectionForm.pickup_contact_name),
      pickup_contact_phone: blank(collectionForm.pickup_contact_phone),
      vehicle_resource_id: collectionForm.vehicle_resource_id || null,
      driver_user_id: collectionForm.driver_user_id || null,
      notes: blank(collectionForm.notes),
    };

    await run(async () => {
      if (existing) {
        await api.patch(
          `/cases/${caseId}/collections/${existing.id}`,
          body
        );
        setNotice("Collection updated.");
      } else {
        await api.post(`/cases/${caseId}/collections`, body);
        setNotice("Collection scheduled.");
      }
    }, "Could not save the collection.");
  }

  async function moveCollection(event: FormEvent) {
    event.preventDefault();

    if (dialog?.kind !== "collection-move") {
      return;
    }

    const { collection, target } = dialog;

    await run(async () => {
      await api.post(
        `/cases/${caseId}/collections/${collection.id}/transition`,
        {
          status: target,
          reason: blank(reason),
          collected_at:
            target === "collected" ? localInputToIso(collectedAt) : null,
        }
      );
      setNotice(
        target === "collected"
          ? "Collection recorded. Take the deceased into care next."
          : "Collection cancelled."
      );
    }, "Could not change the collection.");
  }

  async function quickMove(
    collection: Collection,
    target: "en_route" | "scheduled"
  ) {
    try {
      setError("");
      await api.post(
        `/cases/${caseId}/collections/${collection.id}/transition`,
        { status: target }
      );
      setNotice(
        target === "en_route"
          ? "Collection sent out."
          : "Collection moved back to scheduled."
      );
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not change the collection."));
    }
  }

  const vehicleName = (id: string | null) =>
    vehicles.find((v) => v.id === id)?.name ?? null;
  const driverName = (id: string | null) =>
    drivers?.find((d) => d.id === id)?.full_name ?? null;

  const editable =
    arrangement &&
    (arrangement.status === "draft" || arrangement.status === "confirmed");
  const hasOpenCollection = collections.some(
    (c) => c.status === "scheduled" || c.status === "en_route"
  );

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-slate-500">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <button
        type="button"
        onClick={() => router.push(`/cases/${caseId}`)}
        className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft size={16} /> Back to case
      </button>

      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          Funeral arrangements
        </h1>
        <p className="text-sm text-slate-500">{caseLabel}</p>
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

      {/* ---------------- COLLECTIONS ---------------- */}

      <section className="space-y-3 rounded-xl border p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Collection
            </h2>
            <p className="text-sm text-slate-500">
              Fetching the deceased from where they died.
            </p>
          </div>

          {!hasOpenCollection && (
            <button
              type="button"
              onClick={() => openCollection(null)}
              className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              <Plus size={16} /> Schedule collection
            </button>
          )}
        </div>

        {collections.length === 0 && (
          <p className="text-sm text-slate-500">
            No collection has been scheduled.
          </p>
        )}

        {collections.map((collection) => {
          const open =
            collection.status === "scheduled" ||
            collection.status === "en_route";
          const style = COLLECTION_STATUS[collection.status];

          return (
            <div
              key={collection.id}
              className="rounded-lg border bg-white p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    {dateTimeInSouthAfrica(collection.scheduled_at)} ·{" "}
                    {labelOf(PICKUP_TYPES, collection.pickup_type)}
                  </p>

                  {collection.pickup_address && (
                    <p className="mt-1 text-sm text-slate-600">
                      {collection.pickup_address}
                    </p>
                  )}

                  {(collection.pickup_contact_name ||
                    collection.pickup_contact_phone) && (
                    <p className="mt-1 text-sm text-slate-600">
                      {[
                        collection.pickup_contact_name,
                        collection.pickup_contact_phone,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  )}

                  {(vehicleName(collection.vehicle_resource_id) ||
                    driverName(collection.driver_user_id)) && (
                    <p className="mt-1 flex items-center gap-1.5 text-sm text-slate-600">
                      <Truck size={14} />
                      {[
                        vehicleName(collection.vehicle_resource_id),
                        driverName(collection.driver_user_id),
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  )}

                  {collection.collected_at && (
                    <p className="mt-1 text-sm text-slate-600">
                      Collected{" "}
                      {dateTimeInSouthAfrica(collection.collected_at)}
                    </p>
                  )}

                  {collection.cancel_reason && (
                    <p className="mt-1 text-sm text-slate-600">
                      Cancelled: {collection.cancel_reason}
                    </p>
                  )}
                </div>

                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${style.style}`}
                >
                  {style.label}
                </span>
              </div>

              {open && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {collection.status === "scheduled" && (
                    <ActionButton
                      onClick={() => quickMove(collection, "en_route")}
                    >
                      Send out
                    </ActionButton>
                  )}

                  {collection.status === "en_route" && (
                    <ActionButton
                      onClick={() => quickMove(collection, "scheduled")}
                    >
                      Call back
                    </ActionButton>
                  )}

                  <ActionButton
                    onClick={() => {
                      setCollectedAt("");
                      setDialogError("");
                      setDialog({
                        kind: "collection-move",
                        collection,
                        target: "collected",
                      });
                    }}
                  >
                    Mark collected
                  </ActionButton>

                  <ActionButton
                    onClick={() => openCollection(collection)}
                  >
                    Edit
                  </ActionButton>

                  <ActionButton
                    danger
                    onClick={() => {
                      setReason("");
                      setDialogError("");
                      setDialog({
                        kind: "collection-move",
                        collection,
                        target: "cancelled",
                      });
                    }}
                  >
                    Cancel
                  </ActionButton>
                </div>
              )}
            </div>
          );
        })}
      </section>

      {/* ---------------- ARRANGEMENT ---------------- */}

      <section className="space-y-4 rounded-xl border p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Wake, service and burial
            </h2>
            <p className="text-sm text-slate-500">
              When and where each part of the funeral happens.
            </p>
          </div>

          {arrangement ? (
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${ARRANGEMENT_STATUS[arrangement.status].style}`}
            >
              {ARRANGEMENT_STATUS[arrangement.status].label}
            </span>
          ) : (
            <button
              type="button"
              onClick={openPlan}
              className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Plan the funeral
            </button>
          )}
        </div>

        {!arrangement && (
          <p className="text-sm text-slate-500">
            No funeral arrangements have been made yet.
          </p>
        )}

        {arrangement && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <Block
                title="Wake"
                when={arrangement.wake_at}
                lines={[arrangement.wake_venue, arrangement.wake_address]}
              />
              <Block
                title="Service"
                when={arrangement.service_at}
                lines={[
                  arrangement.service_venue_type
                    ? labelOf(VENUE_TYPES, arrangement.service_venue_type)
                    : null,
                  arrangement.service_venue,
                  arrangement.service_address,
                  arrangement.officiant
                    ? `Officiant: ${arrangement.officiant}`
                    : null,
                ]}
              />
              <Block
                title="Cortege leaves"
                when={arrangement.departure_at}
                lines={[arrangement.departure_point]}
              />
              <Block
                title="Burial or cremation"
                when={arrangement.committal_at}
                lines={[
                  arrangement.committal_place,
                  arrangement.committal_section,
                  arrangement.grave_number
                    ? `Grave ${arrangement.grave_number}${
                        arrangement.grave_confirmed
                          ? " (confirmed)"
                          : " (not yet confirmed)"
                      }`
                    : arrangement.grave_confirmed
                      ? "Grave confirmed"
                      : null,
                ]}
              />
            </div>

            {arrangement.notes && (
              <p className="text-sm text-slate-700">{arrangement.notes}</p>
            )}

            {arrangement.cancel_reason && (
              <p className="text-sm text-slate-600">
                Cancelled: {arrangement.cancel_reason}
              </p>
            )}

            <div className="flex flex-wrap gap-2">
              {editable && (
                <ActionButton onClick={openPlan}>Edit</ActionButton>
              )}

              {arrangement.status === "draft" && (
                <ActionButton
                  primary
                  onClick={() => {
                    setDialogError("");
                    setDialog({
                      kind: "arrangement-move",
                      target: "confirmed",
                    });
                  }}
                >
                  Confirm with the family
                </ActionButton>
              )}

              {arrangement.status === "confirmed" && (
                <>
                  <ActionButton
                    primary
                    onClick={() => {
                      setDialogError("");
                      setDialog({
                        kind: "arrangement-move",
                        target: "completed",
                      });
                    }}
                  >
                    Mark funeral completed
                  </ActionButton>

                  <ActionButton
                    onClick={() => {
                      setDialogError("");
                      setDialog({
                        kind: "arrangement-move",
                        target: "draft",
                      });
                    }}
                  >
                    Back to draft
                  </ActionButton>
                </>
              )}

              {arrangement.status === "cancelled" && (
                <ActionButton
                  onClick={() => {
                    setDialogError("");
                    setDialog({
                      kind: "arrangement-move",
                      target: "draft",
                    });
                  }}
                >
                  Reopen as draft
                </ActionButton>
              )}

              {editable && (
                <ActionButton
                  danger
                  onClick={() => {
                    setReason("");
                    setDialogError("");
                    setDialog({
                      kind: "arrangement-move",
                      target: "cancelled",
                    });
                  }}
                >
                  Cancel funeral
                </ActionButton>
              )}
            </div>
          </>
        )}
      </section>

      {/* ---------------- DIALOGS ---------------- */}

      {dialog?.kind === "plan" && (
        <Dialog
          title={arrangement ? "Edit arrangements" : "Plan the funeral"}
          onClose={closeDialog}
          wide
        >
          <form onSubmit={savePlan} className="space-y-5">
            <fieldset className="space-y-3">
              <legend className="mb-1 text-sm font-semibold text-slate-900">
                Wake
              </legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Wake time">
                  <input
                    type="datetime-local"
                    value={plan.wake_at}
                    onChange={(e) =>
                      setPlan({ ...plan, wake_at: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
                <Field label="Wake venue">
                  <input
                    value={plan.wake_venue}
                    onChange={(e) =>
                      setPlan({ ...plan, wake_venue: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
              </div>
              <Field label="Wake address">
                <input
                  value={plan.wake_address}
                  onChange={(e) =>
                    setPlan({ ...plan, wake_address: e.target.value })
                  }
                  className={inputClass}
                />
              </Field>
            </fieldset>

            <fieldset className="space-y-3">
              <legend className="mb-1 text-sm font-semibold text-slate-900">
                Service
              </legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Service time">
                  <input
                    type="datetime-local"
                    value={plan.service_at}
                    onChange={(e) =>
                      setPlan({ ...plan, service_at: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
                <Field label="Service held at">
                  <select
                    value={plan.service_venue_type}
                    onChange={(e) =>
                      setPlan({
                        ...plan,
                        service_venue_type: e.target.value,
                      })
                    }
                    className={inputClass}
                  >
                    <option value="">Not set</option>
                    {VENUE_TYPES.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Venue name">
                  <input
                    value={plan.service_venue}
                    onChange={(e) =>
                      setPlan({ ...plan, service_venue: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
                <Field label="Officiant">
                  <input
                    value={plan.officiant}
                    onChange={(e) =>
                      setPlan({ ...plan, officiant: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
              </div>
              <Field label="Venue address">
                <input
                  value={plan.service_address}
                  onChange={(e) =>
                    setPlan({ ...plan, service_address: e.target.value })
                  }
                  className={inputClass}
                />
              </Field>
            </fieldset>

            <fieldset className="space-y-3">
              <legend className="mb-1 text-sm font-semibold text-slate-900">
                Cortege and burial or cremation
              </legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Cortege leaves at">
                  <input
                    type="datetime-local"
                    value={plan.departure_at}
                    onChange={(e) =>
                      setPlan({ ...plan, departure_at: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
                <Field label="Cortege leaves from">
                  <input
                    value={plan.departure_point}
                    onChange={(e) =>
                      setPlan({ ...plan, departure_point: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
                <Field label="Burial or cremation time">
                  <input
                    type="datetime-local"
                    value={plan.committal_at}
                    onChange={(e) =>
                      setPlan({ ...plan, committal_at: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
                <Field label="Cemetery or crematorium">
                  <input
                    value={plan.committal_place}
                    onChange={(e) =>
                      setPlan({ ...plan, committal_place: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
                <Field label="Section">
                  <input
                    value={plan.committal_section}
                    onChange={(e) =>
                      setPlan({
                        ...plan,
                        committal_section: e.target.value,
                      })
                    }
                    className={inputClass}
                  />
                </Field>
                <Field label="Grave number">
                  <input
                    value={plan.grave_number}
                    onChange={(e) =>
                      setPlan({ ...plan, grave_number: e.target.value })
                    }
                    className={inputClass}
                  />
                </Field>
              </div>

              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={plan.grave_confirmed}
                  onChange={(e) =>
                    setPlan({ ...plan, grave_confirmed: e.target.checked })
                  }
                />
                The grave has been confirmed with the cemetery
              </label>
            </fieldset>

            <Field label="Notes">
              <textarea
                rows={3}
                value={plan.notes}
                onChange={(e) =>
                  setPlan({ ...plan, notes: e.target.value })
                }
                className={inputClass}
              />
            </Field>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel={arrangement ? "Save changes" : "Save draft"}
            />
          </form>
        </Dialog>
      )}

      {dialog?.kind === "arrangement-move" && (
        <Dialog
          title={
            {
              confirmed: "Confirm the arrangements",
              completed: "Mark the funeral completed",
              cancelled: "Cancel the funeral",
              draft:
                arrangement?.status === "cancelled"
                  ? "Reopen the arrangements"
                  : "Move back to draft",
            }[dialog.target]
          }
          onClose={closeDialog}
        >
          <form onSubmit={moveArrangement} className="space-y-4">
            <p className="text-sm text-slate-600">
              {
                {
                  confirmed:
                    "Confirm only once the family has agreed the time and place of the burial or cremation.",
                  completed:
                    "Use this after the burial or cremation has taken place. A completed funeral can no longer be changed.",
                  cancelled:
                    "The funeral date is cleared from the case. You can reopen the arrangements later.",
                  draft:
                    "The family's confirmation is removed until it is confirmed again.",
                }[dialog.target]
              }
            </p>

            {dialog.target === "cancelled" && (
              <Field label="Reason">
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className={inputClass}
                  required
                />
              </Field>
            )}

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              danger={dialog.target === "cancelled"}
              disabled={dialog.target === "cancelled" && !reason.trim()}
              submitLabel={
                {
                  confirmed: "Confirm",
                  completed: "Mark completed",
                  cancelled: "Cancel funeral",
                  draft:
                    arrangement?.status === "cancelled"
                      ? "Reopen"
                      : "Back to draft",
                }[dialog.target]
              }
            />
          </form>
        </Dialog>
      )}

      {dialog?.kind === "collection" && (
        <Dialog
          title={
            dialog.collection ? "Edit collection" : "Schedule a collection"
          }
          onClose={closeDialog}
        >
          <form onSubmit={saveCollection} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Collect at">
                <input
                  type="datetime-local"
                  required
                  value={collectionForm.scheduled_at}
                  onChange={(e) =>
                    setCollectionForm({
                      ...collectionForm,
                      scheduled_at: e.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>
              <Field label="Collect from">
                <select
                  value={collectionForm.pickup_type}
                  onChange={(e) =>
                    setCollectionForm({
                      ...collectionForm,
                      pickup_type: e.target.value,
                    })
                  }
                  className={inputClass}
                >
                  {PICKUP_TYPES.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <Field label="Address or ward">
              <input
                value={collectionForm.pickup_address}
                onChange={(e) =>
                  setCollectionForm({
                    ...collectionForm,
                    pickup_address: e.target.value,
                  })
                }
                className={inputClass}
              />
            </Field>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Contact person">
                <input
                  value={collectionForm.pickup_contact_name}
                  onChange={(e) =>
                    setCollectionForm({
                      ...collectionForm,
                      pickup_contact_name: e.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>
              <Field label="Contact phone">
                <input
                  value={collectionForm.pickup_contact_phone}
                  onChange={(e) =>
                    setCollectionForm({
                      ...collectionForm,
                      pickup_contact_phone: e.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>
              <Field label="Vehicle">
                <select
                  value={collectionForm.vehicle_resource_id}
                  onChange={(e) =>
                    setCollectionForm({
                      ...collectionForm,
                      vehicle_resource_id: e.target.value,
                    })
                  }
                  className={inputClass}
                >
                  <option value="">Not assigned</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </Field>

              {drivers && (
                <Field label="Driver">
                  <select
                    value={collectionForm.driver_user_id}
                    onChange={(e) =>
                      setCollectionForm({
                        ...collectionForm,
                        driver_user_id: e.target.value,
                      })
                    }
                    className={inputClass}
                  >
                    <option value="">Not assigned</option>
                    {drivers.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.full_name}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
            </div>

            <Field label="Notes">
              <textarea
                rows={2}
                value={collectionForm.notes}
                onChange={(e) =>
                  setCollectionForm({
                    ...collectionForm,
                    notes: e.target.value,
                  })
                }
                className={inputClass}
              />
            </Field>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel={dialog.collection ? "Save changes" : "Schedule"}
            />
          </form>
        </Dialog>
      )}

      {dialog?.kind === "collection-move" && (
        <Dialog
          title={
            dialog.target === "collected"
              ? "Record the collection"
              : "Cancel the collection"
          }
          onClose={closeDialog}
        >
          <form onSubmit={moveCollection} className="space-y-4">
            {dialog.target === "collected" ? (
              <Field
                label="Collected at"
                hint="Leave empty to use the current time."
              >
                <input
                  type="datetime-local"
                  value={collectedAt}
                  onChange={(e) => setCollectedAt(e.target.value)}
                  className={inputClass}
                />
              </Field>
            ) : (
              <Field label="Reason">
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className={inputClass}
                  required
                />
              </Field>
            )}

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              danger={dialog.target === "cancelled"}
              disabled={dialog.target === "cancelled" && !reason.trim()}
              submitLabel={
                dialog.target === "collected"
                  ? "Record collection"
                  : "Cancel collection"
              }
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}

function ActionButton({
  onClick,
  children,
  primary = false,
  danger = false,
}: {
  onClick: () => void;
  children: React.ReactNode;
  primary?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-3 py-2 text-sm font-medium ${
        primary
          ? "border-slate-900 bg-slate-900 text-white hover:bg-slate-800"
          : danger
            ? "border-red-200 bg-white text-red-700 hover:bg-red-50"
            : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
      }`}
    >
      {children}
    </button>
  );
}

function Block({
  title,
  when,
  lines,
}: {
  title: string;
  when: string | null;
  lines: (string | null)[];
}) {
  const shown = lines.filter(Boolean) as string[];

  return (
    <div className="rounded-lg border p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">
        {title}
      </p>
      <p className="mt-1 font-semibold text-slate-900">
        {when ? dateTimeInSouthAfrica(when) : "Not set"}
      </p>
      {shown.map((line) => (
        <p key={line} className="text-sm text-slate-600">
          {line}
        </p>
      ))}
    </div>
  );
}
