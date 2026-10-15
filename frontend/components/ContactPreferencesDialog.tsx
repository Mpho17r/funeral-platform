"use client";

import { FormEvent, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import {
  CHANNELS,
  CHANNEL_LABELS,
  type Channel,
  type Preference,
} from "@/lib/communications";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

export function ContactPreferencesDialog({
  memberId,
  memberName,
  onClose,
  onSaved,
}: {
  memberId: string;
  memberName: string;
  onClose: () => void;
  onSaved?: (preference: Preference) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [channel, setChannel] = useState<Channel>("whatsapp");
  const [optedOut, setOptedOut] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await api.get<Preference>(
          `/members/${memberId}/communication-preferences`,
        );

        if (!cancelled) {
          setChannel(response.data.preferred_channel);
          setOptedOut(response.data.opted_out);
          setReason(response.data.opt_out_reason ?? "");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            getApiErrorMessage(
              err,
              "Could not load the contact preferences.",
            ),
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [memberId]);

  async function submit(event: FormEvent) {
    event.preventDefault();

    try {
      setSaving(true);
      setError("");

      const response = await api.patch<Preference>(
        `/members/${memberId}/communication-preferences`,
        {
          preferred_channel: channel,
          opted_out: optedOut,
          opt_out_reason: optedOut ? reason : null,
        },
      );

      onSaved?.(response.data);
      onClose();
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Could not save the contact preferences.",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={`Contact preferences · ${memberName}`} onClose={onClose}>
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <ErrorNote message={error} />}

          <Field
            label="Preferred way to be contacted"
            hint="If we do not have the contact detail for this, we use whichever one works."
          >
            <select
              value={channel}
              onChange={(event) =>
                setChannel(event.target.value as Channel)
              }
              className={inputClass}
            >
              {CHANNELS.map((value) => (
                <option key={value} value={value}>
                  {CHANNEL_LABELS[value]}
                </option>
              ))}
            </select>
          </Field>

          <label className="flex items-start gap-3 rounded-lg border border-slate-200 p-3">
            <input
              type="checkbox"
              checked={optedOut}
              onChange={(event) => setOptedOut(event.target.checked)}
              className="mt-1"
            />
            <span>
              <span className="block text-sm font-medium text-slate-900">
                Does not want to receive messages
              </span>
              <span className="block text-xs text-slate-500">
                No reminders are queued for this member, and staff
                cannot write them a message.
              </span>
            </span>
          </label>

          {optedOut && (
            <Field label="Reason (optional)">
              <input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className={inputClass}
                placeholder="For example: asked on the phone"
              />
            </Field>
          )}

          <DialogFooter
            onClose={onClose}
            saving={saving}
            submitLabel="Save"
          />
        </form>
      )}
    </Dialog>
  );
}
