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

const MIN_LENGTH = 8;

function checkNew(password: string, again: string): string {
  if (password.length < MIN_LENGTH) {
    return `The new password must be at least ${MIN_LENGTH} characters.`;
  }

  if (password !== again) {
    return "The two new passwords do not match.";
  }

  return "";
}

// ---------------------------------------------------------------
// Your own password. The server ends every earlier session and
// hands back a fresh sign-in, which has to replace the stored one.
// ---------------------------------------------------------------

export function ChangePasswordDialog({
  onClose,
  onDone,
}: {
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();

    const problem = checkNew(next, again);

    if (problem) {
      setError(problem);
      return;
    }

    try {
      setSaving(true);
      setError("");

      const response = await api.post<{ access_token: string }>(
        "/auth/change-password",
        {
          current_password: current,
          new_password: next,
        },
      );

      try {
        localStorage.setItem(
          "access_token",
          response.data.access_token,
        );
      } catch {
        /* Storage blocked: the next request asks for a sign-in. */
      }

      onDone(
        "Your password was changed. You were signed out on other devices.",
      );
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not change the password."),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Change your password" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <Field label="Current password">
          <input
            type="password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            className={inputClass}
            autoComplete="current-password"
            required
          />
        </Field>

        <Field
          label="New password"
          hint={`At least ${MIN_LENGTH} characters.`}
        >
          <input
            type="password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
            className={inputClass}
            autoComplete="new-password"
            required
          />
        </Field>

        <Field label="New password again">
          <input
            type="password"
            value={again}
            onChange={(event) => setAgain(event.target.value)}
            className={inputClass}
            autoComplete="new-password"
            required
          />
        </Field>

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Change password"
        />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------
// An administrator setting someone else's password.
// ---------------------------------------------------------------

export function ResetPasswordDialog({
  userId,
  userName,
  onClose,
  onDone,
}: {
  userId: string;
  userName: string;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();

    const problem = checkNew(next, again);

    if (problem) {
      setError(problem);
      return;
    }

    try {
      setSaving(true);
      setError("");

      await api.post(`/users/${userId}/reset-password`, {
        new_password: next,
      });

      onDone(
        `A new password was set for ${userName}. They are signed out everywhere and any lock is lifted.`,
      );
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not reset the password."),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Reset password · ${userName}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <p className="text-sm text-slate-600">
          Choose a new password and give it to {userName} yourself.
          They are signed out on every device and should change it
          after signing in.
        </p>

        <Field
          label="New password"
          hint={`At least ${MIN_LENGTH} characters.`}
        >
          <input
            type="password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
            className={inputClass}
            autoComplete="new-password"
            required
          />
        </Field>

        <Field label="New password again">
          <input
            type="password"
            value={again}
            onChange={(event) => setAgain(event.target.value)}
            className={inputClass}
            autoComplete="new-password"
            required
          />
        </Field>

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Set password"
        />
      </form>
    </Dialog>
  );
}
