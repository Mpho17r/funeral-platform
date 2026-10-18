"use client";

import { FormEvent, useRef, useState } from "react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { roleLabel, useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, Field, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";
import { UserAvatar } from "@/components/UserAvatar";

/** The signed-in person edits how their own name and job title appear. */
export function ProfileDialog({ onClose }: { onClose: () => void }) {
  const { user, avatarUrl, refresh } = useCurrentUser();
  const fileInput = useRef<HTMLInputElement>(null);
  const [photoBusy, setPhotoBusy] = useState(false);

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [jobTitle, setJobTitle] = useState(user?.job_title ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function uploadPhoto(file: File | undefined) {
    if (!file) {
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setError("The picture is larger than 2 MB.");
      return;
    }

    try {
      setPhotoBusy(true);
      setError("");

      const form = new FormData();
      form.append("file", file);

      await api.post("/users/me/avatar", form);
      await refresh();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save the picture."));
    } finally {
      setPhotoBusy(false);

      if (fileInput.current) {
        fileInput.current.value = "";
      }
    }
  }

  async function removePhoto() {
    try {
      setPhotoBusy(true);
      setError("");

      await api.delete("/users/me/avatar");
      await refresh();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not remove the picture."));
    } finally {
      setPhotoBusy(false);
    }
  }

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
    <Dialog title="Edit your profile" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorNote message={error} />}

        <div className="flex items-center gap-4">
          <UserAvatar name={user?.full_name} src={avatarUrl} size={72} />

          <div>
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              onChange={(event) => uploadPhoto(event.target.files?.[0])}
            />

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={photoBusy}
                onClick={() => fileInput.current?.click()}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
              >
                {photoBusy
                  ? "Working…"
                  : avatarUrl
                    ? "Change photo"
                    : "Add a photo"}
              </button>

              {avatarUrl && (
                <button
                  type="button"
                  disabled={photoBusy}
                  onClick={removePhoto}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
                >
                  Remove
                </button>
              )}
            </div>

            <p className="mt-1.5 text-xs text-slate-500">
              PNG, JPEG or WebP, up to 2 MB. A square picture works best.
            </p>
          </div>
        </div>

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
