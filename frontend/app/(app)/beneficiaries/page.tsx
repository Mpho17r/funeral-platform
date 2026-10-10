"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Ban,
  Loader2,
  Pencil,
  Plus,
  UserCheck,
  X,
} from "lucide-react";

import api from "@/lib/api";
import {
  formatPercent,
  getApiErrorMessage,
  statusOf,
} from "@/lib/format";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";

/* ============================================================
   TYPES
============================================================ */

type Member = {
  id: string;
  member_number: string;
  first_name: string;
  last_name: string;
};

type Membership = {
  id: string;
  member_id: string;
  membership_number: string;
  status: string;
};

type Beneficiary = {
  id: string;
  membership_id: string;
  first_name: string;
  last_name: string;
  relationship: string;
  id_number: string | null;
  phone: string | null;
  email: string | null;
  share_percent: string;
  is_active: boolean;
  notes: string | null;
};

type Summary = {
  membership_id: string;
  active_beneficiaries: number;
  allocated_percent: string;
  remaining_percent: string;
  is_fully_allocated: boolean;
};

type BeneficiaryForm = {
  first_name: string;
  last_name: string;
  relationship: string;
  share_percent: string;
  id_number: string;
  phone: string;
  email: string;
  notes: string;
};

const emptyForm: BeneficiaryForm = {
  first_name: "",
  last_name: "",
  relationship: "spouse",
  share_percent: "",
  id_number: "",
  phone: "",
  email: "",
  notes: "",
};

const relationships = [
  "spouse",
  "partner",
  "child",
  "parent",
  "sibling",
  "grandparent",
  "grandchild",
  "other",
];

/* ============================================================
   PAGE
============================================================ */

export default function BeneficiariesPage() {
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [members, setMembers] = useState<Member[]>([]);

  const [membershipId, setMembershipId] = useState("");

  // The list is kept together with the membership it belongs to, so
  // switching membership never shows the previous one's shares.
  const [data, setData] = useState<{
    membershipId: string;
    beneficiaries: Beneficiary[];
    summary: Summary;
  } | null>(null);

  const [reloadKey, setReloadKey] = useState(0);

  const [loadingBase, setLoadingBase] = useState(true);

  const [error, setError] = useState("");

  const [editing, setEditing] = useState<Beneficiary | "new" | null>(
    null
  );
  const [deactivating, setDeactivating] =
    useState<Beneficiary | null>(null);

  const [saving, setSaving] = useState(false);
  const [dialogError, setDialogError] = useState("");

  const memberName = useMemo(() => {
    const names = new Map<string, string>();

    for (const member of members) {
      names.set(
        member.id,
        `${member.first_name} ${member.last_name}`
      );
    }

    return names;
  }, [members]);

  function membershipLabel(membership: Membership) {
    const name = memberName.get(membership.member_id);

    return name
      ? `${membership.membership_number} — ${name}`
      : membership.membership_number;
  }

  /* ---------------- load memberships ---------------- */

  useEffect(() => {
    let cancelled = false;

    async function loadBase() {
      try {
        const [membershipsResponse, membersResponse] =
          await Promise.all([
            api.get<Membership[]>("/memberships"),
            api.get<Member[]>("/members"),
          ]);

        if (cancelled) {
          return;
        }

        setMemberships(membershipsResponse.data);
        setMembers(membersResponse.data);

        // Other screens link here with ?membership=<id>.
        const requested = new URLSearchParams(
          window.location.search
        ).get("membership");

        if (
          requested &&
          membershipsResponse.data.some(
            (item) => item.id === requested
          )
        ) {
          setMembershipId(requested);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            statusOf(err) === 401
              ? "Your session has expired. Please log in again."
              : getApiErrorMessage(
                  err,
                  "Failed to load memberships."
                )
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingBase(false);
        }
      }
    }

    loadBase();

    return () => {
      cancelled = true;
    };
  }, []);

  /* ---------------- load beneficiaries ---------------- */

  useEffect(() => {
    if (!membershipId) {
      return;
    }

    let cancelled = false;

    async function loadList() {
      try {
        const [listResponse, summaryResponse] = await Promise.all([
          api.get<Beneficiary[]>(
            `/memberships/${membershipId}/beneficiaries`,
            { params: { include_inactive: true } }
          ),
          api.get<Summary>(
            `/memberships/${membershipId}/beneficiaries/summary`
          ),
        ]);

        if (cancelled) {
          return;
        }

        setData({
          membershipId,
          beneficiaries: listResponse.data,
          summary: summaryResponse.data,
        });
        setError("");
      } catch (err) {
        if (!cancelled) {
          setData(null);
          setError(
            getApiErrorMessage(
              err,
              "Failed to load beneficiaries."
            )
          );
        }
      }
    }

    loadList();

    return () => {
      cancelled = true;
    };
  }, [membershipId, reloadKey]);

  const current =
    data && data.membershipId === membershipId ? data : null;

  const beneficiaries = current?.beneficiaries ?? [];
  const summary = current?.summary ?? null;

  const loadingList = !!membershipId && !current && !error;

  const active = beneficiaries.filter((item) => item.is_active);
  const inactive = beneficiaries.filter((item) => !item.is_active);

  /* ---------------- dialogs ---------------- */

  function closeDialogs() {
    setEditing(null);
    setDeactivating(null);
    setDialogError("");
  }

  async function handleDeactivate() {
    if (!deactivating) {
      return;
    }

    setSaving(true);
    setDialogError("");

    try {
      await api.post(
        `/beneficiaries/${deactivating.id}/deactivate`
      );

      closeDialogs();
      setReloadKey((value) => value + 1);
    } catch (err) {
      setDialogError(
        getApiErrorMessage(err, "Unable to deactivate.")
      );
    } finally {
      setSaving(false);
    }
  }

  /* ============================================================
     RENDER
  ============================================================ */

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Beneficiaries
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Who receives a claim payout, and in what shares.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setDialogError("");
            setEditing("new");
          }}
          disabled={!membershipId}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus size={18} />
          Add Beneficiary
        </button>
      </div>

      {error && (
        <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>

          <button
            type="button"
            onClick={() => setError("")}
            aria-label="Dismiss"
            className="ml-4"
          >
            <X size={18} />
          </button>
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Membership
          </span>

          <select
            value={membershipId}
            onChange={(event) => {
              setError("");
              setMembershipId(event.target.value);
            }}
            disabled={loadingBase}
            className={inputClass}
          >
            <option value="">
              {loadingBase
                ? "Loading memberships…"
                : "Select a membership"}
            </option>

            {memberships.map((membership) => (
              <option key={membership.id} value={membership.id}>
                {membershipLabel(membership)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!membershipId && !loadingBase && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center">
          <UserCheck
            size={32}
            className="mx-auto text-gray-400"
          />
          <p className="mt-3 text-sm font-medium text-gray-700">
            Choose a membership to see its beneficiaries.
          </p>
        </div>
      )}

      {loadingList && (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-gray-500">
          <Loader2 size={18} className="animate-spin" />
          Loading beneficiaries…
        </div>
      )}

      {membershipId && summary && (
        <>
          <AllocationCard summary={summary} />

          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 px-5 py-4">
              <h2 className="text-base font-semibold text-gray-900">
                Active beneficiaries
              </h2>
            </div>

            {active.length === 0 ? (
              <p className="px-5 py-10 text-center text-sm text-gray-500">
                No beneficiaries yet. Without any, a claim payout is
                recorded in full with no split.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-gray-500">
                    <tr>
                      <th className="px-5 py-3 font-medium">Name</th>
                      <th className="px-5 py-3 font-medium">
                        Relationship
                      </th>
                      <th className="px-5 py-3 font-medium">Contact</th>
                      <th className="px-5 py-3 text-right font-medium">
                        Share
                      </th>
                      <th className="px-5 py-3" />
                    </tr>
                  </thead>

                  <tbody>
                    {active.map((beneficiary) => (
                      <tr
                        key={beneficiary.id}
                        className="border-t border-gray-100"
                      >
                        <td className="px-5 py-4 font-medium text-gray-900">
                          {beneficiary.first_name}{" "}
                          {beneficiary.last_name}
                        </td>

                        <td className="px-5 py-4 capitalize text-gray-600">
                          {beneficiary.relationship}
                        </td>

                        <td className="px-5 py-4 text-gray-600">
                          {beneficiary.phone ||
                            beneficiary.email ||
                            "—"}
                        </td>

                        <td className="px-5 py-4 text-right font-semibold text-gray-900">
                          {formatPercent(beneficiary.share_percent)}
                        </td>

                        <td className="px-5 py-4">
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => {
                                setDialogError("");
                                setEditing(beneficiary);
                              }}
                              title="Edit beneficiary"
                              aria-label={`Edit ${beneficiary.first_name}`}
                              className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-900"
                            >
                              <Pencil size={16} />
                            </button>

                            <button
                              type="button"
                              onClick={() => {
                                setDialogError("");
                                setDeactivating(beneficiary);
                              }}
                              title="Deactivate beneficiary"
                              aria-label={`Deactivate ${beneficiary.first_name}`}
                              className="rounded-lg p-2 text-red-500 hover:bg-red-50 hover:text-red-700"
                            >
                              <Ban size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {inactive.length > 0 && (
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-5">
              <h2 className="text-sm font-semibold text-gray-700">
                Deactivated ({inactive.length})
              </h2>

              <p className="mt-1 text-xs text-gray-500">
                Kept for the record. Their share is no longer
                counted.
              </p>

              <ul className="mt-3 divide-y divide-gray-200 text-sm text-gray-500">
                {inactive.map((beneficiary) => (
                  <li
                    key={beneficiary.id}
                    className="flex items-center justify-between py-2"
                  >
                    <span>
                      {beneficiary.first_name}{" "}
                      {beneficiary.last_name}
                      <span className="ml-2 capitalize text-gray-400">
                        {beneficiary.relationship}
                      </span>
                    </span>

                    <span>
                      {formatPercent(beneficiary.share_percent)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {editing && summary && (
        <BeneficiaryDialog
          key={editing === "new" ? "new" : editing.id}
          beneficiary={editing === "new" ? null : editing}
          membershipId={membershipId}
          remaining={
            Number(summary.remaining_percent) +
            (editing === "new"
              ? 0
              : Number(editing.share_percent))
          }
          saving={saving}
          error={dialogError}
          onClose={closeDialogs}
          onSubmit={async (form) => {
            setSaving(true);
            setDialogError("");

            const body = {
              first_name: form.first_name.trim(),
              last_name: form.last_name.trim(),
              relationship: form.relationship,
              share_percent: form.share_percent,
              id_number: form.id_number.trim() || null,
              phone: form.phone.trim() || null,
              email: form.email.trim() || null,
              notes: form.notes.trim() || null,
            };

            try {
              if (editing === "new") {
                await api.post(
                  `/memberships/${membershipId}/beneficiaries`,
                  body
                );
              } else {
                await api.patch(
                  `/beneficiaries/${editing.id}`,
                  body
                );
              }

              closeDialogs();
              setReloadKey((value) => value + 1);
            } catch (err) {
              setDialogError(
                getApiErrorMessage(
                  err,
                  "Unable to save the beneficiary."
                )
              );
            } finally {
              setSaving(false);
            }
          }}
        />
      )}

      {deactivating && (
        <Dialog title="Deactivate beneficiary" onClose={closeDialogs}>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              handleDeactivate();
            }}
            className="space-y-4"
          >
            <p className="text-sm text-slate-600">
              Deactivate{" "}
              <strong>
                {deactivating.first_name} {deactivating.last_name}
              </strong>
              ? Their{" "}
              {formatPercent(deactivating.share_percent)} share is
              freed up for someone else. This cannot be undone, but
              the record is kept.
            </p>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialogs}
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
   ALLOCATION CARD
============================================================ */

function AllocationCard({ summary }: { summary: Summary }) {
  const allocated = Number(summary.allocated_percent);
  const remaining = Number(summary.remaining_percent);

  let tone = "bg-amber-50 text-amber-700";
  let message = `${formatPercent(remaining)} still unallocated`;

  if (summary.active_beneficiaries === 0) {
    tone = "bg-gray-100 text-gray-600";
    message = "No beneficiaries";
  } else if (summary.is_fully_allocated) {
    tone = "bg-emerald-50 text-emerald-700";
    message = "Fully allocated";
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-gray-500">Allocated</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {formatPercent(allocated)}
            <span className="ml-2 text-sm font-medium text-gray-400">
              of 100% across {summary.active_beneficiaries}{" "}
              {summary.active_beneficiaries === 1
                ? "beneficiary"
                : "beneficiaries"}
            </span>
          </p>
        </div>

        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${tone}`}
        >
          {message}
        </span>
      </div>

      <div
        className="mt-4 h-2 overflow-hidden rounded-full bg-gray-100"
        role="progressbar"
        aria-valuenow={allocated}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Share allocated"
      >
        <div
          className={`h-full rounded-full ${
            summary.is_fully_allocated
              ? "bg-emerald-500"
              : "bg-amber-500"
          }`}
          style={{ width: `${Math.min(allocated, 100)}%` }}
        />
      </div>

      {summary.active_beneficiaries > 0 &&
        !summary.is_fully_allocated && (
          <p className="mt-3 text-xs text-gray-500">
            Shares must total exactly 100% before a claim for this
            membership can be paid out.
          </p>
        )}
    </div>
  );
}

/* ============================================================
   ADD / EDIT DIALOG
============================================================ */

function BeneficiaryDialog({
  beneficiary,
  remaining,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  beneficiary: Beneficiary | null;
  membershipId: string;
  remaining: number;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (form: BeneficiaryForm) => void;
}) {
  const [form, setForm] = useState<BeneficiaryForm>(
    beneficiary
      ? {
          first_name: beneficiary.first_name,
          last_name: beneficiary.last_name,
          relationship: beneficiary.relationship,
          share_percent: String(Number(beneficiary.share_percent)),
          id_number: beneficiary.id_number ?? "",
          phone: beneficiary.phone ?? "",
          email: beneficiary.email ?? "",
          notes: beneficiary.notes ?? "",
        }
      : emptyForm
  );

  const share = Number(form.share_percent);
  const overShare = form.share_percent !== "" && share > remaining;

  function update<K extends keyof BeneficiaryForm>(
    key: K,
    value: BeneficiaryForm[K]
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit(form);
  }

  return (
    <Dialog
      title={beneficiary ? "Edit beneficiary" : "Add beneficiary"}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="First name">
            <input
              required
              value={form.first_name}
              onChange={(event) =>
                update("first_name", event.target.value)
              }
              className={inputClass}
            />
          </Field>

          <Field label="Last name">
            <input
              required
              value={form.last_name}
              onChange={(event) =>
                update("last_name", event.target.value)
              }
              className={inputClass}
            />
          </Field>

          <Field label="Relationship">
            <select
              value={form.relationship}
              onChange={(event) =>
                update("relationship", event.target.value)
              }
              className={`${inputClass} capitalize`}
            >
              {relationships.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Share (%)"
            hint={`Up to ${formatPercent(remaining)} available.`}
          >
            <input
              required
              type="number"
              inputMode="decimal"
              min="0.01"
              max="100"
              step="0.01"
              value={form.share_percent}
              onChange={(event) =>
                update("share_percent", event.target.value)
              }
              aria-invalid={overShare}
              className={`${inputClass} ${
                overShare ? "border-red-400" : ""
              }`}
            />
          </Field>

          <Field label="ID number (optional)">
            <input
              value={form.id_number}
              onChange={(event) =>
                update("id_number", event.target.value)
              }
              className={inputClass}
            />
          </Field>

          <Field label="Phone (optional)">
            <input
              value={form.phone}
              onChange={(event) =>
                update("phone", event.target.value)
              }
              className={inputClass}
            />
          </Field>
        </div>

        <Field label="Email (optional)">
          <input
            type="email"
            value={form.email}
            onChange={(event) =>
              update("email", event.target.value)
            }
            className={inputClass}
          />
        </Field>

        <Field label="Notes (optional)">
          <textarea
            rows={2}
            value={form.notes}
            onChange={(event) =>
              update("notes", event.target.value)
            }
            className={inputClass}
          />
        </Field>

        {overShare && (
          <ErrorNote
            message={`That is more than the ${formatPercent(
              remaining
            )} still available for this membership.`}
          />
        )}

        {error && <ErrorNote message={error} />}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel={beneficiary ? "Save changes" : "Add beneficiary"}
          disabled={overShare}
        />
      </form>
    </Dialog>
  );
}

function ErrorNote({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {message}
    </p>
  );
}
