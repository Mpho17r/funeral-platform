"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Ban,
  Building2,
  CalendarClock,
  CheckCircle2,
  Loader2,
  Pencil,
  Plus,
  TriangleAlert,
  Truck,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import {
  formatStatus,
  getApiErrorMessage,
  statusOf,
} from "@/lib/format";
import {
  dateAtHour,
  dayKey,
  formatDateTime,
  formatDayHeading,
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

type BookingStatus = "booked" | "completed" | "cancelled";

type Resource = {
  id: string;
  resource_type: ResourceType;
  name: string;
  identifier: string | null;
  is_active: boolean;
};

type Booking = {
  id: string;
  case_id: string;
  resource_id: string;
  driver_user_id: string | null;
  starts_at: string;
  ends_at: string;
  purpose: string | null;
  status: BookingStatus;
  notes: string | null;
};

type FuneralCase = {
  id: string;
  case_number: string;
  deceased_full_name: string;
  status: string;
  is_archived: boolean;
  funeral_date: string | null;
};

type StaffUser = {
  id: string;
  full_name: string;
  is_active: boolean;
};

type Availability = {
  is_available: boolean;
  conflicts: Booking[];
};

type Dialogue =
  | { kind: "book" }
  | { kind: "edit"; booking: Booking }
  | { kind: "cancel"; booking: Booking }
  | { kind: "complete"; booking: Booking }
  | null;

type StatusFilter = BookingStatus | "all";

/* ============================================================
   CONSTANTS
============================================================ */

// Cases the backend accepts new bookings for.
const BOOKABLE_CASE_STATUSES = [
  "open",
  "confirmed",
  "in_progress",
];

const TYPE_ICON: Record<ResourceType, typeof Truck> = {
  vehicle: Truck,
  venue: Building2,
  equipment: Wrench,
};

const TYPE_LABEL: Record<ResourceType, string> = {
  vehicle: "Vehicles",
  venue: "Venues",
  equipment: "Equipment",
};

const FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "booked", label: "Upcoming" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "all", label: "All" },
];

const STATUS_STYLE: Record<BookingStatus, string> = {
  booked: "bg-sky-50 text-sky-700",
  completed: "bg-emerald-50 text-emerald-700",
  cancelled: "bg-slate-100 text-slate-500",
};

/* ============================================================
   PAGE
============================================================ */

export default function ResourceBookingsPage() {
  const router = useRouter();

  const [bookings, setBookings] = useState<Booking[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [cases, setCases] = useState<FuneralCase[]>([]);

  // null when the user may not list staff. The driver field then
  // simply is not offered.
  const [staff, setStaff] = useState<StaffUser[] | null>(null);

  const [caseFilter, setCaseFilter] =
    useState<string | null>(null);

  const [filter, setFilter] =
    useState<StatusFilter>("booked");

  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [notice, setNotice] = useState("");

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  const [reloadKey, setReloadKey] = useState(0);

  /* ---------------- load ---------------- */

  useEffect(() => {
    let cancelled = false;

    async function loadAll() {
      try {
        // Other screens link here with ?case=<id>.
        const requested = new URLSearchParams(
          window.location.search
        ).get("case");

        const [bookingsResponse, resourcesResponse, casesResponse] =
          await Promise.all([
            api.get<Booking[]>(
              requested
                ? `/cases/${requested}/resource-bookings`
                : "/resource-bookings"
            ),
            api.get<Resource[]>("/resources"),
            api.get<FuneralCase[]>("/cases"),
          ]);

        let staffList: StaffUser[] | null = null;

        try {
          const staffResponse =
            await api.get<StaffUser[]>("/users");

          staffList = staffResponse.data;
        } catch {
          // Listing staff has its own permission.
          staffList = null;
        }

        if (cancelled) {
          return;
        }

        setCaseFilter(requested);
        setBookings(bookingsResponse.data);
        setResources(resourcesResponse.data);
        setCases(casesResponse.data);
        setStaff(staffList);
        setPageError("");
      } catch (err) {
        if (cancelled) {
          return;
        }

        if (statusOf(err) === 401) {
          router.push("/login");
          return;
        }

        setPageError(
          getApiErrorMessage(
            err,
            "Unable to load the schedule."
          )
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadAll();

    return () => {
      cancelled = true;
    };
  }, [reloadKey, router]);

  function reload() {
    setReloadKey((current) => current + 1);
  }

  const resourceById = useMemo(
    () => new Map(resources.map((item) => [item.id, item])),
    [resources]
  );

  const caseById = useMemo(
    () => new Map(cases.map((item) => [item.id, item])),
    [cases]
  );

  const staffName = useMemo(
    () =>
      new Map(
        (staff ?? []).map((item) => [item.id, item.full_name])
      ),
    [staff]
  );

  const counts = useMemo(() => {
    const result: Record<string, number> = {
      all: bookings.length,
    };

    for (const item of bookings) {
      result[item.status] = (result[item.status] ?? 0) + 1;
    }

    return result;
  }, [bookings]);

  const days = useMemo(() => {
    const visible = bookings
      .filter((item) => filter === "all" || item.status === filter)
      .sort(
        (a, b) =>
          new Date(a.starts_at).getTime() -
          new Date(b.starts_at).getTime()
      );

    const grouped = new Map<string, Booking[]>();

    for (const item of visible) {
      const key = dayKey(item.starts_at);
      grouped.set(key, [...(grouped.get(key) ?? []), item]);
    }

    return [...grouped.entries()];
  }, [bookings, filter]);

  const filteredCase = caseFilter
    ? caseById.get(caseFilter)
    : undefined;

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
            Schedule
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Vehicles, venues and equipment booked for funerals.
            Double bookings are blocked.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link
            href="/resources"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            <Truck size={18} />
            Resources
          </Link>

          <button
            type="button"
            onClick={() => {
              setDialogError("");
              setDialog({ kind: "book" });
            }}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800"
          >
            <Plus size={18} />
            Book Resource
          </button>
        </div>
      </div>

      {notice && (
        <Banner tone="success" onDismiss={() => setNotice("")}>
          {notice}
        </Banner>
      )}

      {pageError && (
        <Banner tone="error" onDismiss={() => setPageError("")}>
          {pageError}
        </Banner>
      )}

      {caseFilter && (
        <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
          <span>
            Showing bookings for case{" "}
            <strong>
              {filteredCase?.case_number ?? "this case"}
            </strong>
          </span>

          <Link
            href="/resource-bookings"
            className="inline-flex items-center gap-1 font-medium text-slate-600 underline"
          >
            <X size={14} />
            Show all
          </Link>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setFilter(item.value)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${
              filter === item.value
                ? "bg-slate-900 text-white"
                : "bg-white text-slate-600 hover:bg-slate-100"
            }`}
          >
            {item.label}{" "}
            <span className="text-xs opacity-70">
              {counts[item.value] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" />
          Loading schedule…
        </div>
      ) : days.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <CalendarClock
            size={28}
            className="mx-auto text-slate-400"
          />
          <p className="mt-3 text-sm font-medium text-slate-700">
            Nothing here yet.
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Book a vehicle, venue or equipment for a funeral.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {days.map(([key, items]) => (
            <section key={key}>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {formatDayHeading(key)}
              </h2>

              <div className="space-y-3">
                {items.map((booking) => (
                  <BookingRow
                    key={booking.id}
                    booking={booking}
                    resource={resourceById.get(
                      booking.resource_id
                    )}
                    caseInfo={caseById.get(booking.case_id)}
                    driver={
                      booking.driver_user_id
                        ? staffName.get(booking.driver_user_id) ??
                          "Driver assigned"
                        : null
                    }
                    onEdit={() => {
                      setDialogError("");
                      setDialog({ kind: "edit", booking });
                    }}
                    onComplete={() => {
                      setDialogError("");
                      setDialog({ kind: "complete", booking });
                    }}
                    onCancel={() => {
                      setDialogError("");
                      setDialog({ kind: "cancel", booking });
                    }}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {dialog?.kind === "book" && (
        <BookingDialog
          mode="book"
          resources={resources.filter((item) => item.is_active)}
          cases={cases.filter(
            (item) =>
              !item.is_archived &&
              BOOKABLE_CASE_STATUSES.includes(item.status)
          )}
          staff={staff}
          initialCaseId={caseFilter}
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(caseId, body) =>
            runAction(
              () =>
                api.post(
                  `/cases/${caseId}/resource-bookings`,
                  body
                ),
              "Resource booked."
            )
          }
        />
      )}

      {dialog?.kind === "edit" && (
        <BookingDialog
          mode="edit"
          booking={dialog.booking}
          resources={resources}
          cases={cases}
          staff={staff}
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(_caseId, body) =>
            runAction(
              () =>
                api.patch(
                  `/resource-bookings/${dialog.booking.id}`,
                  {
                    starts_at: body.starts_at,
                    ends_at: body.ends_at,
                    driver_user_id: body.driver_user_id,
                    purpose: body.purpose,
                    notes: body.notes,
                  }
                ),
              "Booking updated."
            )
          }
        />
      )}

      {(dialog?.kind === "cancel" ||
        dialog?.kind === "complete") && (
        <Dialog
          title={
            dialog.kind === "cancel"
              ? "Cancel booking"
              : "Complete booking"
          }
          onClose={closeDialog}
        >
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();

              runAction(
                () =>
                  api.post(
                    `/resource-bookings/${dialog.booking.id}/${dialog.kind}`
                  ),
                dialog.kind === "cancel"
                  ? "Booking cancelled."
                  : "Booking marked as completed."
              );
            }}
          >
            <p className="text-sm text-slate-600">
              {dialog.kind === "cancel"
                ? "The resource becomes free for that time again. A cancelled booking stays in the history."
                : "Mark this booking as done once the funeral service has used the resource."}
            </p>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              danger={dialog.kind === "cancel"}
              submitLabel={
                dialog.kind === "cancel"
                  ? "Cancel booking"
                  : "Mark as completed"
              }
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}

/* ============================================================
   BOOKING ROW
============================================================ */

function BookingRow({
  booking,
  resource,
  caseInfo,
  driver,
  onEdit,
  onComplete,
  onCancel,
}: {
  booking: Booking;
  resource: Resource | undefined;
  caseInfo: FuneralCase | undefined;
  driver: string | null;
  onEdit: () => void;
  onComplete: () => void;
  onCancel: () => void;
}) {
  const Icon = resource ? TYPE_ICON[resource.resource_type] : Truck;

  const sameDay =
    dayKey(booking.starts_at) === dayKey(booking.ends_at);

  const muted = booking.status === "cancelled";

  return (
    <div
      className={`flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 md:flex-row md:items-center md:justify-between ${
        muted ? "opacity-70" : ""
      }`}
    >
      <div className="flex items-start gap-4">
        <div className="rounded-xl bg-slate-100 p-3 text-slate-600">
          <Icon size={20} />
        </div>

        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold text-slate-900">
              {resource?.name ?? "Resource"}
              {resource?.identifier && (
                <span className="ml-2 text-xs font-normal text-slate-500">
                  {resource.identifier}
                </span>
              )}
            </p>

            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[booking.status]}`}
            >
              {formatStatus(booking.status)}
            </span>
          </div>

          <p className="mt-1 text-sm text-slate-600">
            {formatTime(booking.starts_at)} –{" "}
            {sameDay
              ? formatTime(booking.ends_at)
              : formatDateTime(booking.ends_at)}
            {" · "}
            <Link
              href={`/cases/${booking.case_id}`}
              className="underline"
            >
              {caseInfo?.case_number ?? "Case"}
            </Link>
            {caseInfo && ` · ${caseInfo.deceased_full_name}`}
          </p>

          {(booking.purpose || driver) && (
            <p className="mt-1 text-xs text-slate-500">
              {[booking.purpose, driver && `Driver: ${driver}`]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
        </div>
      </div>

      {booking.status === "booked" && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onComplete}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <CheckCircle2 size={14} />
            Complete
          </button>

          <button
            type="button"
            onClick={onEdit}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <Pencil size={14} />
            Edit
          </button>

          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-50"
          >
            <Ban size={14} />
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

/* ============================================================
   BOOK / EDIT DIALOG
============================================================ */

type BookingBody = {
  resource_id: string;
  starts_at: string;
  ends_at: string;
  driver_user_id: string | null;
  purpose: string | null;
  notes: string | null;
};

function BookingDialog({
  mode,
  booking,
  resources,
  cases,
  staff,
  initialCaseId,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  mode: "book" | "edit";
  booking?: Booking;
  resources: Resource[];
  cases: FuneralCase[];
  staff: StaffUser[] | null;
  initialCaseId?: string | null;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (caseId: string, body: BookingBody) => void;
}) {
  const editing = mode === "edit" && booking !== undefined;

  const firstCase =
    cases.find((item) => item.id === initialCaseId) ?? cases[0];

  const [caseId, setCaseId] = useState(
    booking?.case_id ?? firstCase?.id ?? ""
  );

  const [resourceId, setResourceId] = useState(
    booking?.resource_id ?? ""
  );

  const [driverId, setDriverId] = useState(
    booking?.driver_user_id ?? ""
  );

  const [startsAt, setStartsAt] = useState(
    booking
      ? isoToLocalInput(booking.starts_at)
      : firstCase?.funeral_date
        ? dateAtHour(firstCase.funeral_date, 9)
        : ""
  );

  const [endsAt, setEndsAt] = useState(
    booking
      ? isoToLocalInput(booking.ends_at)
      : firstCase?.funeral_date
        ? dateAtHour(firstCase.funeral_date, 12)
        : ""
  );

  const [purpose, setPurpose] = useState(booking?.purpose ?? "");
  const [notes, setNotes] = useState(booking?.notes ?? "");
  const [formError, setFormError] = useState("");

  const [availability, setAvailability] =
    useState<Availability | null>(null);

  const [checking, setChecking] = useState(false);

  const resource = resources.find((item) => item.id === resourceId);

  const isVehicle = resource?.resource_type === "vehicle";

  const startIso = localInputToIso(startsAt);
  const endIso = localInputToIso(endsAt);

  const windowValid =
    startIso !== null &&
    endIso !== null &&
    new Date(endIso).getTime() > new Date(startIso).getTime();

  // Tell the user about a clash while they are still choosing, not
  // only after they press Book.
  useEffect(() => {
    if (!resourceId || !windowValid || !startIso || !endIso) {
      return;
    }

    let cancelled = false;

    const timer = window.setTimeout(async () => {
      setChecking(true);

      try {
        const response = await api.get<Availability>(
          `/resources/${resourceId}/availability`,
          { params: { starts_at: startIso, ends_at: endIso } }
        );

        if (!cancelled) {
          // The booking being edited does not clash with itself.
          setAvailability({
            ...response.data,
            conflicts: response.data.conflicts.filter(
              (item) => item.id !== booking?.id
            ),
          });
        }
      } catch {
        if (!cancelled) {
          setAvailability(null);
        }
      } finally {
        if (!cancelled) {
          setChecking(false);
        }
      }
    }, 400);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [resourceId, windowValid, startIso, endIso, booking?.id]);

  const clash =
    windowValid &&
    availability !== null &&
    availability.conflicts.length > 0;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!caseId) {
      setFormError("Choose a case.");
      return;
    }

    if (!resourceId) {
      setFormError("Choose a resource.");
      return;
    }

    if (!startIso || !endIso) {
      setFormError("Enter a start and an end time.");
      return;
    }

    if (!windowValid) {
      setFormError("The booking must end after it starts.");
      return;
    }

    setFormError("");

    onSubmit(caseId, {
      resource_id: resourceId,
      starts_at: startIso,
      ends_at: endIso,
      driver_user_id: isVehicle && driverId ? driverId : null,
      purpose: purpose.trim() || null,
      notes: notes.trim() || null,
    });
  }

  const grouped = (
    ["vehicle", "venue", "equipment"] as ResourceType[]
  )
    .map((type) => ({
      type,
      items: resources.filter(
        (item) => item.resource_type === type
      ),
    }))
    .filter((group) => group.items.length > 0);

  const activeStaff = (staff ?? []).filter(
    (item) => item.is_active
  );

  return (
    <Dialog
      title={editing ? "Edit booking" : "Book a resource"}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Case">
          <select
            value={caseId}
            disabled={editing}
            onChange={(event) => {
              const next = cases.find(
                (item) => item.id === event.target.value
              );

              setCaseId(event.target.value);

              if (!editing && next?.funeral_date) {
                setStartsAt(dateAtHour(next.funeral_date, 9));
                setEndsAt(dateAtHour(next.funeral_date, 12));
              }
            }}
            className={inputClass}
          >
            {cases.length === 0 && (
              <option value="">No live cases</option>
            )}

            {cases.map((item) => (
              <option key={item.id} value={item.id}>
                {item.case_number} — {item.deceased_full_name}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="Resource"
          hint={
            editing
              ? "The resource cannot be changed. Cancel and book again instead."
              : undefined
          }
        >
          <select
            value={resourceId}
            disabled={editing}
            onChange={(event) => {
              setResourceId(event.target.value);
              setDriverId("");
            }}
            className={inputClass}
          >
            <option value="">Choose a resource…</option>

            {grouped.map((group) => (
              <optgroup
                key={group.type}
                label={TYPE_LABEL[group.type]}
              >
                {group.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                    {item.identifier
                      ? ` (${item.identifier})`
                      : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </Field>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Starts">
            <input
              type="datetime-local"
              value={startsAt}
              onChange={(event) => setStartsAt(event.target.value)}
              className={inputClass}
            />
          </Field>

          <Field label="Ends">
            <input
              type="datetime-local"
              value={endsAt}
              onChange={(event) => setEndsAt(event.target.value)}
              className={inputClass}
            />
          </Field>
        </div>

        {resourceId && windowValid && (
          <div aria-live="polite">
            {checking ? (
              <p className="flex items-center gap-2 text-xs text-slate-500">
                <Loader2 size={12} className="animate-spin" />
                Checking availability…
              </p>
            ) : clash ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <p className="flex items-center gap-2 font-medium">
                  <TriangleAlert size={16} />
                  Already booked for these times
                </p>

                <ul className="mt-1 list-disc pl-6 text-xs">
                  {availability?.conflicts.map((item) => (
                    <li key={item.id}>
                      {formatDateTime(item.starts_at)} –{" "}
                      {formatDateTime(item.ends_at)}
                    </li>
                  ))}
                </ul>
              </div>
            ) : availability?.is_available ? (
              <p className="flex items-center gap-2 text-xs font-medium text-emerald-700">
                <CheckCircle2 size={14} />
                Available for these times
              </p>
            ) : null}
          </div>
        )}

        {isVehicle && activeStaff.length > 0 && (
          <Field
            label="Driver (optional)"
            hint="A driver can only be booked once at a time."
          >
            <select
              value={driverId}
              onChange={(event) => setDriverId(event.target.value)}
              className={inputClass}
            >
              <option value="">No driver yet</option>

              {activeStaff.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.full_name}
                </option>
              ))}
            </select>
          </Field>
        )}

        <Field label="Purpose (optional)">
          <input
            value={purpose}
            maxLength={255}
            onChange={(event) => setPurpose(event.target.value)}
            placeholder="For example: hearse to the cemetery"
            className={inputClass}
          />
        </Field>

        <Field label="Notes (optional)">
          <textarea
            value={notes}
            rows={2}
            onChange={(event) => setNotes(event.target.value)}
            className={inputClass}
          />
        </Field>

        {(formError || error) && (
          <ErrorNote message={formError || error} />
        )}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel={editing ? "Save changes" : "Book"}
        />
      </form>
    </Dialog>
  );
}
