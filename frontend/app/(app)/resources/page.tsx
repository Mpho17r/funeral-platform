"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Building2,
  CalendarClock,
  CheckCircle2,
  Loader2,
  Pencil,
  Plus,
  Power,
  PowerOff,
  Search,
  TriangleAlert,
  Truck,
  Wrench,
} from "lucide-react";
import Link from "next/link";

import api from "@/lib/api";
import {
  formatDate,
  getApiErrorMessage,
  statusOf,
} from "@/lib/format";
import {
  formatDateTime,
  formatTime,
  isoToLocalInput,
  localInputToIso,
} from "@/lib/datetime";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";

/* ============================================================
   TYPES
============================================================ */

type ResourceType = "vehicle" | "venue" | "equipment";

type Resource = {
  id: string;
  resource_type: ResourceType;
  name: string;
  identifier: string | null;
  capacity: number | null;
  location: string | null;
  is_active: boolean;
  notes: string | null;
};

type Booking = {
  id: string;
  case_id: string;
  resource_id: string;
  starts_at: string;
  ends_at: string;
  purpose: string | null;
  status: string;
};

type Availability = {
  is_available: boolean;
  conflicts: Booking[];
};

type SignalCase = {
  case_id: string;
  case_number: string;
  funeral_date: string;
};

type Signals = {
  window_days: number;
  funerals_without_vehicle: SignalCase[];
  funerals_without_venue: SignalCase[];
  vehicle_bookings_without_driver: number;
};

type FuneralCase = {
  id: string;
  case_number: string;
};

type Dialogue =
  | { kind: "create" }
  | { kind: "edit"; resource: Resource }
  | { kind: "availability"; resource: Resource }
  | { kind: "deactivate"; resource: Resource }
  | null;

/* ============================================================
   CONSTANTS
============================================================ */

const TYPE_META: Record<
  ResourceType,
  { label: string; plural: string; icon: typeof Truck }
> = {
  vehicle: { label: "Vehicle", plural: "Vehicles", icon: Truck },
  venue: { label: "Venue", plural: "Venues", icon: Building2 },
  equipment: {
    label: "Equipment",
    plural: "Equipment",
    icon: Wrench,
  },
};

const FILTERS: { value: "all" | ResourceType; label: string }[] = [
  { value: "all", label: "All" },
  { value: "vehicle", label: "Vehicles" },
  { value: "venue", label: "Venues" },
  { value: "equipment", label: "Equipment" },
];

/* ============================================================
   PAGE
============================================================ */

export default function ResourcesPage() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [signals, setSignals] = useState<Signals | null>(null);
  const [cases, setCases] = useState<FuneralCase[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [filter, setFilter] = useState<"all" | ResourceType>("all");
  const [showInactive, setShowInactive] = useState(false);

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  // Bumping this refetches everything after a change.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadAll() {
      try {
        const resourcesResponse = await api.get<Resource[]>(
          "/resources",
          { params: { include_inactive: true } }
        );

        if (cancelled) {
          return;
        }

        setResources(resourcesResponse.data);
        setError("");
      } catch (err) {
        if (!cancelled) {
          setError(
            statusOf(err) === 401
              ? "Your session has expired. Please log in again."
              : getApiErrorMessage(err, "Failed to load resources.")
          );
          setLoading(false);
        }

        return;
      }

      // The attention strip and case numbers are extras. If the user
      // may not see them, the page still works without them.
      const [signalsResult, casesResult] = await Promise.allSettled([
        api.get<Signals>("/resource-signals"),
        api.get<FuneralCase[]>("/cases"),
      ]);

      if (cancelled) {
        return;
      }

      setSignals(
        signalsResult.status === "fulfilled"
          ? signalsResult.value.data
          : null
      );
      setCases(
        casesResult.status === "fulfilled"
          ? casesResult.value.data
          : []
      );
      setLoading(false);
    }

    loadAll();

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setReloadKey((current) => current + 1);
  }

  const caseNumber = useMemo(
    () => new Map(cases.map((item) => [item.id, item.case_number])),
    [cases]
  );

  const counts = useMemo(() => {
    const active = resources.filter((item) => item.is_active);
    const result: Record<string, number> = { all: active.length };

    for (const item of active) {
      result[item.resource_type] =
        (result[item.resource_type] ?? 0) + 1;
    }

    return result;
  }, [resources]);

  const inactiveCount = resources.filter(
    (item) => !item.is_active
  ).length;

  const visible = resources.filter(
    (item) =>
      (filter === "all" || item.resource_type === filter) &&
      (showInactive || item.is_active)
  );

  /* ---------------- actions ---------------- */

  function closeDialog() {
    setDialog(null);
    setDialogError("");
  }

  async function runAction(
    request: () => Promise<unknown>,
    done: string
  ) {
    setSaving(true);
    setDialogError("");

    try {
      await request();

      closeDialog();
      setNotice(done);
      reload();
    } catch (err) {
      setDialogError(
        getApiErrorMessage(err, "Something went wrong.")
      );
    } finally {
      setSaving(false);
    }
  }

  /* ---------------- render ---------------- */

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Resources
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Vehicles, venues and equipment you can book for a
            funeral.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link
            href="/resource-bookings"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            <CalendarClock size={18} />
            Schedule
          </Link>

          <button
            type="button"
            onClick={() => {
              setDialogError("");
              setDialog({ kind: "create" });
            }}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800"
          >
            <Plus size={18} />
            Add Resource
          </button>
        </div>
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

      {signals && <AttentionStrip signals={signals} />}

      <div className="flex flex-wrap items-center gap-2">
        <div
          className="flex flex-wrap gap-2"
          role="tablist"
          aria-label="Filter resources by type"
        >
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              role="tab"
              aria-selected={filter === item.value}
              onClick={() => setFilter(item.value)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                filter === item.value
                  ? "bg-slate-900 text-white"
                  : "bg-white text-slate-600 hover:bg-slate-100"
              }`}
            >
              {item.label}
              <span
                className={`ml-1.5 text-xs ${
                  filter === item.value
                    ? "text-slate-300"
                    : "text-slate-400"
                }`}
              >
                {counts[item.value] ?? 0}
              </span>
            </button>
          ))}
        </div>

        {inactiveCount > 0 && (
          <label className="ml-auto flex items-center gap-2 text-sm text-slate-600">
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
          Loading resources…
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center">
          <Truck size={32} className="mx-auto text-gray-400" />
          <p className="mt-3 text-sm font-medium text-gray-700">
            {resources.length === 0
              ? "No resources yet. Add your first vehicle, venue or piece of equipment."
              : "Nothing matches this filter."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((resource) => (
            <ResourceCard
              key={resource.id}
              resource={resource}
              onEdit={() => {
                setDialogError("");
                setDialog({ kind: "edit", resource });
              }}
              onCheck={() => {
                setDialogError("");
                setDialog({ kind: "availability", resource });
              }}
              onToggle={() => {
                setDialogError("");

                if (resource.is_active) {
                  setDialog({ kind: "deactivate", resource });
                } else {
                  runAction(
                    () =>
                      api.post(
                        `/resources/${resource.id}/reactivate`
                      ),
                    `${resource.name} is active again.`
                  );
                }
              }}
            />
          ))}
        </div>
      )}

      {dialog?.kind === "create" && (
        <ResourceDialog
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(body) =>
            runAction(
              () => api.post("/resources", body),
              `${body.name} added.`
            )
          }
        />
      )}

      {dialog?.kind === "edit" && (
        <ResourceDialog
          resource={dialog.resource}
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(body) => {
            // The type is fixed once a resource exists.
            const { resource_type, ...changes } = body;
            void resource_type;

            return runAction(
              () =>
                api.patch(
                  `/resources/${dialog.resource.id}`,
                  changes
                ),
              `${body.name} updated.`
            );
          }}
        />
      )}

      {dialog?.kind === "availability" && (
        <AvailabilityDialog
          resource={dialog.resource}
          caseNumber={caseNumber}
          onClose={closeDialog}
        />
      )}

      {dialog?.kind === "deactivate" && (
        <Dialog
          title={`Deactivate ${dialog.resource.name}?`}
          onClose={closeDialog}
        >
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              runAction(
                () =>
                  api.post(
                    `/resources/${dialog.resource.id}/deactivate`
                  ),
                `${dialog.resource.name} deactivated.`
              );
            }}
          >
            <p className="text-sm text-slate-600">
              It can no longer be booked. Bookings it already has
              are kept, and you can reactivate it at any time.
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

/* ============================================================
   ATTENTION STRIP
   What is missing for upcoming funerals, from /resource-signals.
============================================================ */

function AttentionStrip({ signals }: { signals: Signals }) {
  const nothingMissing =
    signals.funerals_without_vehicle.length === 0 &&
    signals.funerals_without_venue.length === 0 &&
    signals.vehicle_bookings_without_driver === 0;

  if (nothingMissing) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-800">
        <CheckCircle2 size={20} className="shrink-0" />
        Every funeral in the next {signals.window_days} days has
        a vehicle and a venue booked, and every vehicle has a
        driver.
      </div>
    );
  }

  return (
    <section
      aria-label="Needs attention"
      className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4"
    >
      <h2 className="flex items-center gap-2 text-sm font-semibold text-amber-900">
        <TriangleAlert size={18} />
        Needs attention in the next {signals.window_days} days
      </h2>

      <div className="mt-3 space-y-3 text-sm">
        <GapRow
          label="Funerals without a vehicle"
          cases={signals.funerals_without_vehicle}
        />

        <GapRow
          label="Funerals without a venue"
          cases={signals.funerals_without_venue}
        />

        {signals.vehicle_bookings_without_driver > 0 && (
          <p className="text-amber-900">
            <span className="font-medium">
              {signals.vehicle_bookings_without_driver}
            </span>{" "}
            vehicle {signals.vehicle_bookings_without_driver === 1
              ? "booking has"
              : "bookings have"}{" "}
            no driver.{" "}
            <Link
              href="/resource-bookings"
              className="font-medium underline"
            >
              Open the schedule
            </Link>
          </p>
        )}
      </div>
    </section>
  );
}

function GapRow({
  label,
  cases,
}: {
  label: string;
  cases: SignalCase[];
}) {
  if (cases.length === 0) {
    return null;
  }

  return (
    <div>
      <p className="font-medium text-amber-900">{label}</p>

      <div className="mt-1.5 flex flex-wrap gap-2">
        {cases.map((item) => (
          <Link
            key={item.case_id}
            href={`/resource-bookings?case=${item.case_id}`}
            title="Book a resource for this funeral"
            className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-medium text-amber-900 transition hover:bg-amber-100"
          >
            {item.case_number} · {formatDate(item.funeral_date)}
          </Link>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   RESOURCE CARD
============================================================ */

function ResourceCard({
  resource,
  onEdit,
  onCheck,
  onToggle,
}: {
  resource: Resource;
  onEdit: () => void;
  onCheck: () => void;
  onToggle: () => void;
}) {
  const meta = TYPE_META[resource.resource_type];
  const Icon = meta.icon;

  return (
    <article
      className={`flex flex-col rounded-xl border bg-white p-5 shadow-sm ${
        resource.is_active
          ? "border-gray-200"
          : "border-gray-200 opacity-70"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="rounded-lg bg-slate-100 p-2.5 text-slate-600">
          <Icon size={20} />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-base font-semibold text-slate-900">
              {resource.name}
            </h3>

            {!resource.is_active && (
              <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                Inactive
              </span>
            )}
          </div>

          <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-slate-400">
            {meta.label}
            {resource.identifier && ` · ${resource.identifier}`}
          </p>
        </div>
      </div>

      <dl className="mt-4 space-y-1.5 text-sm text-slate-600">
        {resource.capacity !== null && (
          <div className="flex justify-between gap-4">
            <dt className="text-slate-400">Capacity</dt>
            <dd>{resource.capacity}</dd>
          </div>
        )}

        {resource.location && (
          <div className="flex justify-between gap-4">
            <dt className="text-slate-400">Location</dt>
            <dd className="text-right">{resource.location}</dd>
          </div>
        )}
      </dl>

      {resource.notes && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
          {resource.notes}
        </p>
      )}

      <div className="mt-auto flex flex-wrap gap-2 pt-5">
        {resource.is_active && (
          <button
            type="button"
            onClick={onCheck}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <Search size={14} />
            Check availability
          </button>
        )}

        <button
          type="button"
          onClick={onEdit}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <Pencil size={14} />
          Edit
        </button>

        <button
          type="button"
          onClick={onToggle}
          className={`ml-auto inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${
            resource.is_active
              ? "text-red-600 hover:bg-red-50"
              : "text-emerald-700 hover:bg-emerald-50"
          }`}
        >
          {resource.is_active ? (
            <>
              <PowerOff size={14} />
              Deactivate
            </>
          ) : (
            <>
              <Power size={14} />
              Reactivate
            </>
          )}
        </button>
      </div>
    </article>
  );
}

/* ============================================================
   ADD / EDIT DIALOG
============================================================ */

type ResourceBody = {
  resource_type: ResourceType;
  name: string;
  identifier: string | null;
  capacity: number | null;
  location: string | null;
  notes: string | null;
};

function ResourceDialog({
  resource,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  resource?: Resource;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (body: ResourceBody) => void;
}) {
  const [type, setType] = useState<ResourceType>(
    resource?.resource_type ?? "vehicle"
  );
  const [name, setName] = useState(resource?.name ?? "");
  const [identifier, setIdentifier] = useState(
    resource?.identifier ?? ""
  );
  const [capacity, setCapacity] = useState(
    resource?.capacity?.toString() ?? ""
  );
  const [location, setLocation] = useState(
    resource?.location ?? ""
  );
  const [notes, setNotes] = useState(resource?.notes ?? "");

  const editing = Boolean(resource);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    onSubmit({
      resource_type: type,
      name: name.trim(),
      identifier: identifier.trim() || null,
      capacity: capacity === "" ? null : Number(capacity),
      location: location.trim() || null,
      notes: notes.trim() || null,
    });
  }

  return (
    <Dialog
      title={editing ? `Edit ${resource?.name}` : "Add Resource"}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          label="Type"
          hint={
            editing
              ? "The type cannot be changed, because bookings depend on it."
              : undefined
          }
        >
          <select
            value={type}
            disabled={editing}
            onChange={(event) =>
              setType(event.target.value as ResourceType)
            }
            className={`${inputClass} disabled:bg-slate-100 disabled:text-slate-500`}
          >
            {(Object.keys(TYPE_META) as ResourceType[]).map(
              (value) => (
                <option key={value} value={value}>
                  {TYPE_META[value].label}
                </option>
              )
            )}
          </select>
        </Field>

        <Field label="Name">
          <input
            required
            maxLength={200}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Mercedes Vito hearse"
            className={inputClass}
          />
        </Field>

        <Field
          label="Identifier (optional)"
          hint="A registration number, room number or asset tag."
        >
          <input
            maxLength={100}
            value={identifier}
            onChange={(event) =>
              setIdentifier(event.target.value)
            }
            placeholder="CA 123-456"
            className={inputClass}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Capacity (optional)">
            <input
              type="number"
              min={0}
              step={1}
              value={capacity}
              onChange={(event) =>
                setCapacity(event.target.value)
              }
              className={inputClass}
            />
          </Field>

          <Field label="Location (optional)">
            <input
              maxLength={255}
              value={location}
              onChange={(event) =>
                setLocation(event.target.value)
              }
              className={inputClass}
            />
          </Field>
        </div>

        <Field label="Notes (optional)">
          <textarea
            rows={3}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className={inputClass}
          />
        </Field>

        {error && <ErrorNote message={error} />}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel={editing ? "Save changes" : "Add resource"}
          disabled={!name.trim()}
        />
      </form>
    </Dialog>
  );
}

/* ============================================================
   AVAILABILITY DIALOG
============================================================ */

function defaultWindow() {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(start.getHours() + 1);

  const end = new Date(start);
  end.setHours(end.getHours() + 2);

  return {
    start: isoToLocalInput(start.toISOString()),
    end: isoToLocalInput(end.toISOString()),
  };
}

function AvailabilityDialog({
  resource,
  caseNumber,
  onClose,
}: {
  resource: Resource;
  caseNumber: Map<string, string>;
  onClose: () => void;
}) {
  const [initial] = useState(defaultWindow);
  const [start, setStart] = useState(initial.start);
  const [end, setEnd] = useState(initial.end);

  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<Availability | null>(null);
  const [error, setError] = useState("");

  async function handleCheck(event: FormEvent) {
    event.preventDefault();

    const startsAt = localInputToIso(start);
    const endsAt = localInputToIso(end);

    if (!startsAt || !endsAt) {
      setError("Choose a start and an end time.");
      return;
    }

    setChecking(true);
    setError("");
    setResult(null);

    try {
      const response = await api.get<Availability>(
        `/resources/${resource.id}/availability`,
        { params: { starts_at: startsAt, ends_at: endsAt } }
      );

      setResult(response.data);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not check availability.")
      );
    } finally {
      setChecking(false);
    }
  }

  return (
    <Dialog
      title={`Availability · ${resource.name}`}
      onClose={onClose}
    >
      <form onSubmit={handleCheck} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="From">
            <input
              type="datetime-local"
              required
              value={start}
              onChange={(event) => setStart(event.target.value)}
              className={inputClass}
            />
          </Field>

          <Field label="Until">
            <input
              type="datetime-local"
              required
              value={end}
              onChange={(event) => setEnd(event.target.value)}
              className={inputClass}
            />
          </Field>
        </div>

        {error && <ErrorNote message={error} />}

        {result && (
          <div
            role="status"
            className={`rounded-lg border px-4 py-3 text-sm ${
              result.is_available
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-amber-200 bg-amber-50 text-amber-900"
            }`}
          >
            {result.is_available ? (
              <p className="font-medium">
                Free for that time.
              </p>
            ) : result.conflicts.length === 0 ? (
              <p className="font-medium">
                Not available, because this resource is inactive.
              </p>
            ) : (
              <>
                <p className="font-medium">
                  Already booked for part of that time:
                </p>

                <ul className="mt-2 space-y-1">
                  {result.conflicts.map((booking) => (
                    <li key={booking.id}>
                      {formatDateTime(booking.starts_at)} –{" "}
                      {formatTime(booking.ends_at)}
                      {" · "}
                      {caseNumber.get(booking.case_id)
                        ? `Case ${caseNumber.get(booking.case_id)}`
                        : "Another case"}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>

          <button
            type="submit"
            disabled={checking}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
          >
            {checking && (
              <Loader2 size={16} className="animate-spin" />
            )}
            Check availability
          </button>
        </div>
      </form>
    </Dialog>
  );
}
