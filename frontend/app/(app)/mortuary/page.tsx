"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Loader2, Plus, Snowflake } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import {
  LOCATION_KINDS,
  formatDateTime,
  labelOf,
  type Board,
  type MortuaryLocation,
} from "@/lib/mortuary";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";

type LocationForm = {
  name: string;
  kind: string;
  capacity: string;
  notes: string;
};

const emptyForm: LocationForm = {
  name: "",
  kind: "fridge",
  capacity: "",
  notes: "",
};

export default function MortuaryPage() {
  const router = useRouter();

  const [board, setBoard] = useState<Board | null>(null);
  const [allLocations, setAllLocations] = useState<MortuaryLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [placeFilter, setPlaceFilter] = useState("all");

  const [dialog, setDialog] = useState<
    { kind: "new" } | { kind: "edit"; location: MortuaryLocation } | null
  >(null);
  const [form, setForm] = useState<LocationForm>(emptyForm);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");

      const [boardResponse, locationsResponse] = await Promise.all([
        api.get<Board>("/mortuary/board"),
        api.get<MortuaryLocation[]>("/mortuary/locations", {
          params: { include_inactive: true },
        }),
      ]);

      setBoard(boardResponse.data);
      setAllLocations(locationsResponse.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load the mortuary."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function openNew() {
    setForm(emptyForm);
    setDialogError("");
    setDialog({ kind: "new" });
  }

  function openEdit(location: MortuaryLocation) {
    setForm({
      name: location.name,
      kind: location.kind,
      capacity: location.capacity ? String(location.capacity) : "",
      notes: location.notes ?? "",
    });
    setDialogError("");
    setDialog({ kind: "edit", location });
  }

  async function saveLocation(event: FormEvent) {
    event.preventDefault();

    if (!dialog) {
      return;
    }

    setSaving(true);
    setDialogError("");

    const body = {
      name: form.name.trim(),
      kind: form.kind,
      capacity: form.capacity ? Number(form.capacity) : null,
      notes: form.notes.trim() || null,
    };

    try {
      if (dialog.kind === "new") {
        await api.post("/mortuary/locations", body);
        setNotice("Location added.");
      } else {
        await api.patch(
          `/mortuary/locations/${dialog.location.id}`,
          body
        );
        setNotice("Location updated.");
      }

      setDialog(null);
      await load();
    } catch (err) {
      setDialogError(
        getApiErrorMessage(err, "Could not save this location.")
      );
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(location: MortuaryLocation) {
    try {
      setError("");

      await api.post(
        `/mortuary/locations/${location.id}/${
          location.is_active ? "deactivate" : "reactivate"
        }`
      );

      await load();
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not change this location.")
      );
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-slate-500">
        <Loader2 className="animate-spin" size={18} /> Loading…
      </div>
    );
  }

  const entries = (board?.entries ?? []).filter(
    (entry) =>
      placeFilter === "all" ||
      (placeFilter === "none"
        ? entry.location_id === null
        : entry.location_id === placeFilter)
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Snowflake className="text-slate-500" />
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Mortuary</h1>
            <p className="text-sm text-slate-500">
              Who is in your care and where they are right now.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={openNew}
          className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
        >
          <Plus size={16} /> Add location
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

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            In our care
          </p>
          <p className="mt-1 text-2xl font-bold text-slate-900">
            {board?.in_custody ?? 0}
          </p>
        </div>

        <div
          className={`rounded-xl border p-4 ${
            (board?.cooling_overdue ?? 0) > 0
              ? "border-red-300 bg-red-50"
              : ""
          }`}
        >
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Not yet cooled, past 3 hours
          </p>
          <p className="mt-1 text-2xl font-bold text-slate-900">
            {board?.cooling_overdue ?? 0}
          </p>
        </div>
      </div>

      {/* LOCATIONS */}

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          Locations
        </h2>

        {allLocations.length === 0 ? (
          <p className="rounded-xl border p-4 text-sm text-slate-500">
            No locations yet. Add your fridges and cold rooms so the system
            can stop you overfilling them.
          </p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {allLocations.map((location) => {
              const full =
                location.capacity !== null &&
                location.occupied >= location.capacity;

              return (
                <div
                  key={location.id}
                  className={`rounded-xl border p-4 ${
                    location.is_active ? "" : "opacity-60"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-semibold text-slate-900">
                        {location.name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {labelOf(LOCATION_KINDS, location.kind)}
                        {!location.is_active && " · Inactive"}
                      </p>
                    </div>

                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                        full
                          ? "bg-red-100 text-red-700"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {location.occupied}
                      {location.capacity !== null
                        ? ` of ${location.capacity}`
                        : ""}
                      {full ? " · Full" : ""}
                    </span>
                  </div>

                  <div className="mt-3 flex gap-3 text-sm">
                    <button
                      type="button"
                      onClick={() => openEdit(location)}
                      className="font-medium text-slate-700 hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => void toggleActive(location)}
                      className="font-medium text-slate-700 hover:underline"
                    >
                      {location.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* BOARD */}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            In our care
          </h2>

          <select
            aria-label="Filter by location"
            value={placeFilter}
            onChange={(event) => setPlaceFilter(event.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="all">All locations</option>
            <option value="none">No location</option>
            {allLocations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
        </div>

        {entries.length === 0 ? (
          <p className="rounded-xl border p-4 text-sm text-slate-500">
            Nobody is in your care here.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Deceased</th>
                  <th className="px-4 py-3">Tag</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Arrived</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr
                    key={entry.remains_id}
                    className={`border-t ${
                      entry.cooling_overdue ? "bg-red-50" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900">
                        {entry.deceased_full_name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {entry.case_number}
                      </p>
                    </td>
                    <td className="px-4 py-3">{entry.tag_number}</td>
                    <td className="px-4 py-3">
                      {entry.location_name ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      {formatDateTime(entry.received_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {entry.cooling_overdue && (
                          <span className="flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                            <AlertTriangle size={12} /> Not cooled
                          </span>
                        )}
                        {!entry.cooled && !entry.cooling_overdue && (
                          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
                            Cooling due
                          </span>
                        )}
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                            entry.identified
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {entry.identified
                            ? "Identified"
                            : "Not identified"}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() =>
                          router.push(`/cases/${entry.case_id}/remains`)
                        }
                        className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {dialog && (
        <Dialog
          title={dialog.kind === "new" ? "Add location" : "Edit location"}
          onClose={() => !saving && setDialog(null)}
        >
          <form onSubmit={saveLocation} className="space-y-4">
            {dialogError && <ErrorNote message={dialogError} />}

            <Field label="Name">
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className={inputClass}
              />
            </Field>

            <Field label="Type">
              <select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value })}
                className={inputClass}
              >
                {LOCATION_KINDS.map((kind) => (
                  <option key={kind.value} value={kind.value}>
                    {kind.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field
              label="Capacity"
              hint="Number of trays. Leave blank for no limit."
            >
              <input
                type="number"
                min={1}
                value={form.capacity}
                onChange={(e) =>
                  setForm({ ...form, capacity: e.target.value })
                }
                className={inputClass}
              />
            </Field>

            <Field label="Notes">
              <textarea
                rows={2}
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className={inputClass}
              />
            </Field>

            <DialogFooter
              onClose={() => setDialog(null)}
              saving={saving}
              submitLabel="Save"
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}
