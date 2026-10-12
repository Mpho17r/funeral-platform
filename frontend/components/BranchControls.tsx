"use client";

import { FormEvent, useState } from "react";
import { ArrowRightLeft, Building } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import type { Branch } from "@/lib/branches";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

/** Filter value meaning "every branch". */
export const ALL_BRANCHES = "all";

/** Filter value meaning "records that have no branch". */
export const NO_BRANCH = "none";

/** Whether a record with this branch passes the chosen filter. */
export function matchesBranch(
  filter: string,
  branchId: string | null | undefined
): boolean {
  if (filter === ALL_BRANCHES) {
    return true;
  }

  if (filter === NO_BRANCH) {
    return !branchId;
  }

  return branchId === filter;
}

/* ============================================================
   FILTER
   Everyone sees every branch. This only narrows the list.
============================================================ */

export function BranchFilter({
  branches,
  value,
  onChange,
  className = "",
}: {
  branches: Branch[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <select
      aria-label="Filter by branch"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={
        className ||
        "rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-slate-900"
      }
    >
      <option value={ALL_BRANCHES}>All branches</option>

      {branches.map((branch) => (
        <option key={branch.id} value={branch.id}>
          {branch.name}
          {branch.is_active ? "" : " (inactive)"}
        </option>
      ))}
    </select>
  );
}

/* ============================================================
   FORM FIELD
   Only active branches can receive new records. Leaving it on the
   default places the record in the creator's own branch.
============================================================ */

export function BranchSelect({
  branches,
  value,
  onChange,
  label = "Branch",
}: {
  branches: Branch[];
  value: string;
  onChange: (value: string) => void;
  label?: string;
}) {
  return (
    <Field
      label={label}
      hint="Defaults to your own branch if you leave it as it is."
    >
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
      >
        <option value="">My branch (default)</option>

        {branches
          .filter((branch) => branch.is_active)
          .map((branch) => (
            <option key={branch.id} value={branch.id}>
              {branch.name}
            </option>
          ))}
      </select>
    </Field>
  );
}

/* ============================================================
   BADGE
============================================================ */

export function BranchBadge({
  branchId,
  byId,
}: {
  branchId: string | null | undefined;
  byId: Map<string, Branch>;
}) {
  const branch = branchId ? byId.get(branchId) : undefined;

  if (!branch) {
    return null;
  }

  return (
    <span
      title={`Branch: ${branch.name}`}
      className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600"
    >
      <Building size={12} />
      {branch.name}
    </span>
  );
}

/* ============================================================
   MOVE BUTTON
============================================================ */

export function MoveButton({
  onClick,
  label = "Move",
}: {
  onClick: () => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
    >
      <ArrowRightLeft size={14} />
      {label}
    </button>
  );
}

/* ============================================================
   TRANSFER DIALOG
   Works for cases, members, resources and staff, which all expose
   POST /<entity>/{id}/transfer with { branch_id }.
============================================================ */

export function TransferDialog({
  path,
  subject,
  currentBranchId,
  branches,
  onClose,
  onMoved,
}: {
  /** e.g. "/cases/<id>/transfer" */
  path: string;
  /** What is being moved, for the title: "Case C-100". */
  subject: string;
  currentBranchId: string | null;
  branches: Branch[];
  onClose: () => void;
  onMoved: (message: string) => void;
}) {
  const options = branches.filter(
    (branch) => branch.is_active && branch.id !== currentBranchId
  );

  const current = branches.find(
    (branch) => branch.id === currentBranchId
  );

  const [target, setTarget] = useState(options[0]?.id ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!target) {
      return;
    }

    setSaving(true);
    setError("");

    try {
      await api.post(path, { branch_id: target });

      const destination = branches.find(
        (branch) => branch.id === target
      );

      onMoved(
        `${subject} moved to ${destination?.name ?? "the new branch"}.`
      );
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not move this record.")
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Move ${subject}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-slate-600">
          {current
            ? `Currently in ${current.name}. `
            : "It is not in a branch yet. "}
          Moving it only changes which branch it belongs to. Nothing
          else about it changes, and the move is recorded in the
          audit trail.
        </p>

        {options.length === 0 ? (
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            There is no other active branch to move it to.
          </p>
        ) : (
          <Field label="Move to">
            <select
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              className={inputClass}
            >
              {options.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.name}
                </option>
              ))}
            </select>
          </Field>
        )}

        {error && <ErrorNote message={error} />}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Move"
          disabled={!target}
        />
      </form>
    </Dialog>
  );
}
