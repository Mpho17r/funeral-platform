"use client";

import { FormEvent, useState } from "react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { roleLabel, useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, Field, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

/** The signed-in person edits how their own name and job title appear. */
export function ProfileDialog({ onClose }: { onClose: () => void }) {
  const { user, refresh } = useCurrentUser();

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [jobTitle, setJobTitle] = useState(user?.job_title ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();

    if (!user) {
      return;
    }

    if (!fullName.trim()) {
      setError("Your name cannot be empty.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      await api.patch(`/users/${user.user_id}`, {
        full_name: fullName.trim(),
        job_title: jobTitle.trim() || null,
      });

      await refresh();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save your profile."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Your profile" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <Field label="Name">
          <input
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            className={inputClass}
            autoComplete="name"
            maxLength={150}
          />
        </Field>

        <Field
          label="Job title (optional)"
          hint="Shown beside your name, for example Operations Manager."
        >
          <input
            value={jobTitle}
            onChange={(event) => setJobTitle(event.target.value)}
            className={inputClass}
            placeholder="e.g. Operations Manager"
            maxLength={100}
          />
        </Field>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg bg-slate-50 p-3 text-sm">
          <dt className="text-slate-500">Email</dt>
          <dd className="truncate text-slate-900">{user?.email ?? "—"}</dd>

          <dt className="text-slate-500">Access</dt>
          <dd className="text-slate-900">{roleLabel(user?.role)}</dd>
        </dl>

        <p className="text-xs text-slate-500">
          Your access level is set by an administrator. It controls what you can
          do, not what your title says.
        </p>

        <DialogFooter onClose={onClose} saving={saving} submitLabel="Save" />
      </form>
    </Dialog>
  );
}
