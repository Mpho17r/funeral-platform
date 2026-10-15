"use client";

import { FormEvent, useState } from "react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Subject = {
  id: string;
  first_name: string;
  last_name: string;
  member_number: string;
};

function nameOf(member: Subject) {
  return `${member.first_name} ${member.last_name}`.trim();
}

// ---------------------------------------------------------------
// Archive: takes a member off the active list. Nothing is deleted.
// ---------------------------------------------------------------

export function ArchiveMemberDialog({
  member,
  onClose,
  onDone,
}: {
  member: Subject;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();

    try {
      setSaving(true);
      setError("");

      await api.delete(`/members/${member.id}`, {
        params: reason.trim() ? { reason: reason.trim() } : undefined,
      });

      onDone(`${nameOf(member)} was archived.`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not archive the member."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Archive ${nameOf(member)}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <p className="text-sm text-slate-600">
          The member moves to the Archived list and stops getting
          reminders. Their memberships, payments and claims stay on
          record, and you can restore them at any time.
        </p>

        <Field label="Reason (optional)">
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className={inputClass}
            maxLength={500}
            placeholder="For example: moved away, asked to leave the scheme"
          />
        </Field>

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Archive member"
        />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------
// Anonymise: permanently removes personal details.
// ---------------------------------------------------------------

export function AnonymiseMemberDialog({
  member,
  onClose,
  onDone,
}: {
  member: Subject;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [typed, setTyped] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const matches = typed.trim() === member.member_number;

  async function submit(event: FormEvent) {
    event.preventDefault();

    if (!matches) return;

    try {
      setSaving(true);
      setError("");

      await api.post(`/members/${member.id}/anonymise`, {
        confirm_member_number: typed.trim(),
      });

      onDone(`${member.member_number}: personal details were removed.`);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not remove the personal details."),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      title={`Remove personal details · ${member.member_number}`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <p className="font-semibold">This cannot be undone.</p>
          <p className="mt-1">
            The name, ID number, date of birth, phone, email and address
            of {nameOf(member)}, their covered dependents and
            beneficiaries, and the wording of messages sent to them are
            permanently erased. Payments, contributions and claims are
            kept for your financial records, but no longer name a
            person.
          </p>
        </div>

        <Field
          label={`Type ${member.member_number} to confirm`}
        >
          <input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            className={inputClass}
            autoComplete="off"
          />
        </Field>

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Remove details"
          danger
          disabled={!matches}
        />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------
// Export: everything held about a member, as a JSON file.
// ---------------------------------------------------------------

export async function downloadMemberData(member: Subject) {
  const response = await api.get(`/members/${member.id}/personal-data`);

  const blob = new Blob([JSON.stringify(response.data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `member-${member.member_number}-data.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
